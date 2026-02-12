import json
import os
import re
import time
import hashlib
import logging
import random
import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

from playwright.sync_api import sync_playwright

try:
    # OpenAI Python SDK (v1+)
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore


# -----------------------------
# Config
# -----------------------------
SOURCE = "asahi_ohaasa"
SOURCE_URL = os.getenv("OHAASA_URL", "https://www.asahi.co.jp/ohaasa/week/horoscope/")

OUTPUT_PATH = Path("public/fortune.json")

CACHE_PATH = Path("scripts/cache/openai_cache.json")
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

TIMEOUT_MS = 30000

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = (os.getenv("OPENAI_MODEL", "gpt-5-mini") or "gpt-5-mini").strip()

# STRICT_OPENAI=1이면 키 없거나 호출 실패 시 스크립트 실패(Exit 1).
# STRICT_OPENAI=0이면 OpenAI가 실패해도 스크래핑 결과를 저장하고 status=partial로 둠.
STRICT_OPENAI = os.getenv("STRICT_OPENAI", "1").strip() == "1"


# -----------------------------
# Sign mapping
# -----------------------------
# JP -> key
SIGN_KEY_MAP = {
    "おひつじ座": "aries",
    "牡羊座": "aries",
    "おうし座": "taurus",
    "牡牛座": "taurus",
    "ふたご座": "gemini",
    "双子座": "gemini",
    "かに座": "cancer",
    "蟹座": "cancer",
    "しし座": "leo",
    "獅子座": "leo",
    "おとめ座": "virgo",
    "乙女座": "virgo",
    "てんびん座": "libra",
    "天秤座": "libra",
    "さそり座": "scorpio",
    "蠍座": "scorpio",
    "いて座": "sagittarius",
    "射手座": "sagittarius",
    "やぎ座": "capricorn",
    "山羊座": "capricorn",
    "みずがめ座": "aquarius",
    "水瓶座": "aquarius",
    "うお座": "pisces",
    "魚座": "pisces",
}

# key -> ko
SIGN_KO_MAP = {
    "aries": "양자리",
    "taurus": "황소자리",
    "gemini": "쌍둥이자리",
    "cancer": "게자리",
    "leo": "사자자리",
    "virgo": "처녀자리",
    "libra": "천칭자리",
    "scorpio": "전갈자리",
    "sagittarius": "사수자리",
    "capricorn": "염소자리",
    "aquarius": "물병자리",
    "pisces": "물고기자리",
}

CATEGORY_KEYS = ["total", "love", "study", "money", "health"]
AI_CARD_TITLES = ["총운", "연애운", "학업운", "금전운", "건강운"]


# -----------------------------
# Score bands (rank -> range)
# -----------------------------
RANK_SCORE_BANDS = {
    1: (95, 100),
    2: (90, 94),
    3: (85, 89),
    4: (80, 84),
    5: (75, 79),
    6: (70, 74),
    7: (65, 69),
    8: (60, 64),
    9: (55, 59),
    10: (50, 54),
    11: (45, 49),
    12: (40, 44),
}

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


# -----------------------------
# Time helpers (KST)
# -----------------------------
def get_kst_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).astimezone(
        datetime.timezone(datetime.timedelta(hours=9))
    )

def kst_date_string() -> str:
    return get_kst_now().date().isoformat()

def kst_iso_string() -> str:
    return get_kst_now().isoformat()


# -----------------------------
# Cache (OpenAI)
# -----------------------------
def load_cache() -> Dict[str, Any]:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(cache: Dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def cache_key(date_kst: str, sign_key: str, message_jp: str) -> str:
    raw = f"{date_kst}|{sign_key}|{message_jp}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


# -----------------------------
# Scores (rank-based deterministic)
# -----------------------------
def seed_for(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest, 16)

def clamp_score(value: int) -> int:
    return max(0, min(100, value))

def score_from_rank(rank: int, seed_base: int) -> int:
    lo, hi = RANK_SCORE_BANDS.get(rank, (40, 60))
    rng = random.Random(seed_base)
    return rng.randint(lo, hi)

def generate_scores(rank: int, date_key: str, sign_key: str) -> Dict[str, int]:
    base_seed = seed_for(f"{date_key}|{sign_key}|overall")
    overall = score_from_rank(rank, base_seed)

    scores: Dict[str, int] = {"overall": overall}
    for cat in CATEGORY_KEYS:
        offset_seed = seed_for(f"{date_key}|{sign_key}|{cat}")
        delta = random.Random(offset_seed).randint(-8, 8)
        scores[cat] = clamp_score(overall + delta)

    scores["total"] = scores.get("total", overall)
    return scores


# -----------------------------
# Scraping (known-good selectors)
# -----------------------------
def scrape_with_playwright() -> Tuple[str, List[Dict[str, str]]]:
    """
    list root: ul.oa_horoscope_list > li
    rank: .horo_rank
    sign: .horo_name
    message: .horo_txt
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ja-JP",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        # wait until list rendered
        page.wait_for_selector("ul.oa_horoscope_list li", timeout=TIMEOUT_MS)

        # optional date label
        date_text = ""
        try:
            date_text = page.locator(".oa_horoscope_date").inner_text(timeout=2000).strip()
        except Exception:
            date_text = ""

        items = page.locator("ul.oa_horoscope_list li")
        count = items.count()
        results: List[Dict[str, str]] = []

        for i in range(count):
            li = items.nth(i)

            rank_raw = li.locator(".horo_rank").inner_text().strip()
            rank = int(re.sub(r"\D+", "", rank_raw) or "0")

            sign_jp = li.locator(".horo_name").inner_text().strip()
            msg_jp = li.locator(".horo_txt").inner_text().strip()

            if rank and sign_jp:
                results.append({"rank": str(rank), "sign_jp": sign_jp, "message_jp": msg_jp})

        context.close()
        browser.close()
        return date_text, results


# -----------------------------
# OpenAI (Responses API via SDK)
# -----------------------------
SYSTEM_KO = (
    "너는 한국어 운세 콘텐츠 편집자이자 번역가다.\n"
    "- 입력은 일본어 원문 운세(message_jp), 별자리(sign_key/sign_ko), 점수(scores)이다.\n"
    "- 출력은 반드시 JSON만 출력한다. 코드블록/설명/추가 텍스트 금지.\n"
    "- 과장하지 말고 실용적인 조언 중심. 자연스러운 한국어.\n"
)

JSON_SCHEMA = {
    "name": "ohaasa_ai_bundle",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "message_ko": {"type": "string"},
            "ai": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "summary": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "headline": {"type": "string"},
                            "one_liner": {"type": "string"},
                        },
                        "required": ["headline", "one_liner"],
                    },
                    "cards": {
                        "type": "array",
                        "minItems": 5,
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "title": {"type": "string"},
                                "body": {"type": "string"},
                                "tip": {"type": "string"},
                                "warning": {"type": "string"},
                            },
                            "required": ["title", "body", "tip", "warning"],
                        },
                    },
                    "lucky_points": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "color_name": {"type": "string"},
                            "color_hex": {"type": "string"},
                            "number": {"type": "integer"},
                            "item": {"type": "string"},
                            "keyword": {"type": "string"},
                            "reasons": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["color_name", "color_hex", "number", "item", "keyword"],
                    },
                },
                "required": ["summary", "cards", "lucky_points"],
            },
        },
        "required": ["message_ko", "ai"],
    },
}

def build_text_format(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    OpenAI Responses API JSON Schema format.
    Some SDK/runtime combinations require `text.format.name` and `text.format.schema`
    at the top level (instead of nested in `json_schema`).
    """
    return {
        "type": "json_schema",
        "name": str(schema.get("name", "ohaasa_ai_bundle")),
        "schema": schema.get("schema", {}),
    }


def _normalize_hex(s: str, fallback: str = "#111111") -> str:
    if not isinstance(s, str):
        return fallback
    s = s.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", s):
        return s.upper()
    return fallback

def _clamp_int(x: Any, lo: int, hi: int, fallback: int) -> int:
    try:
        v = int(x)
        return max(lo, min(hi, v))
    except Exception:
        return fallback

def _ensure_cards(cards: Any) -> List[Dict[str, str]]:
    by_title: Dict[str, Dict[str, str]] = {}
    if isinstance(cards, list):
        for c in cards:
            if isinstance(c, dict):
                t = str(c.get("title", "")).strip()
                if t:
                    by_title[t] = {
                        "title": t,
                        "body": str(c.get("body", "")).strip(),
                        "tip": str(c.get("tip", "")).strip(),
                        "warning": str(c.get("warning", "")).strip(),
                    }

    out: List[Dict[str, str]] = []
    for t in AI_CARD_TITLES:
        c = by_title.get(t, {})
        out.append({
            "title": t,
            "body": c.get("body", "") or "",
            "tip": c.get("tip", "") or "",
            "warning": c.get("warning", "") or "",
        })
    return out

def openai_generate_bundle(
    client: Any,
    date_kst: str,
    sign_key: str,
    sign_ko: str,
    message_jp: str,
    scores: Dict[str, int],
    cache: Dict[str, Any],
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    One call: message_ko translation + ai.summary/cards/lucky_points generation.
    Cache by date_kst + sign_key + message_jp.
    Retries JSON parse failure once.
    """
    ck = cache_key(date_kst, sign_key, message_jp)
    if ck in cache:
        return cache[ck].get("message_ko"), cache[ck].get("ai")

    inp = {
        "date_kst": date_kst,
        "sign_key": sign_key,
        "sign_ko": sign_ko,
        "scores": scores,
        "message_jp": message_jp,
        "constraints": {
            "cards_titles": AI_CARD_TITLES,
            "lucky_number_range": [1, 9],
            "color_hex_format": "#RRGGBB",
        },
    }

    payload = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "system", "content": SYSTEM_KO},
            {"role": "user", "content": json.dumps(inp, ensure_ascii=False)},
        ],
        "text": {"format": build_text_format(JSON_SCHEMA)},
    }

    last_err: Optional[Exception] = None
    for attempt in range(2):
        try:
            resp = client.responses.create(**payload)

            # SDK 버전에 따라 output_text가 있을 수도, 없을 수도 있어 방어적으로 처리
            text = getattr(resp, "output_text", None)
            if not text:
                text = ""
                out = getattr(resp, "output", None)
                if isinstance(out, list):
                    for item in out:
                        content = item.get("content") if isinstance(item, dict) else None
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and c.get("type") in ("output_text", "text"):
                                    t = c.get("text")
                                    if isinstance(t, str) and t.strip():
                                        text = t.strip()
                                        break
                        if text:
                            break

            if not isinstance(text, str) or not text.strip():
                raise ValueError("No JSON text from OpenAI response")

            obj = json.loads(text.strip())

            message_ko = str(obj.get("message_ko", "")).strip()
            ai = obj.get("ai", {}) if isinstance(obj.get("ai"), dict) else {}

            # Post-fix
            ai["cards"] = _ensure_cards(ai.get("cards"))

            lp = ai.get("lucky_points", {}) if isinstance(ai.get("lucky_points"), dict) else {}
            lp["number"] = _clamp_int(lp.get("number"), 1, 9, 7)
            lp["color_hex"] = _normalize_hex(str(lp.get("color_hex", "")), "#111111")
            lp["color_name"] = str(lp.get("color_name", "")).strip() or "포인트 컬러"
            lp["item"] = str(lp.get("item", "")).strip() or "메모"
            lp["keyword"] = str(lp.get("keyword", "")).strip() or "정리"
            ai["lucky_points"] = lp

            cache[ck] = {"message_ko": message_ko, "ai": ai, "ts": kst_iso_string()}
            return message_ko, ai

        except Exception as e:
            last_err = e
            time.sleep(0.8)

    if STRICT_OPENAI:
        raise RuntimeError(f"OpenAI generation failed: {last_err}")

    logging.warning("OpenAI generation failed (fallback to JP only): %s", last_err)
    return None, None


# -----------------------------
# Output helpers
# -----------------------------
def build_payload(date_kst: str, rankings: List[Dict[str, Any]], status: str, error_message: str) -> Dict[str, Any]:
    return {
        "source": SOURCE,
        "date_kst": date_kst,
        "updated_at_kst": kst_iso_string(),
        "status": status,
        "error_message": error_message,
        "rankings": rankings,
    }

def write_payload(payload: Dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUTPUT_PATH)


# -----------------------------
# Main
# -----------------------------
def main() -> None:
    date_kst = kst_date_string()

    try:
        _, parsed = scrape_with_playwright()
    except Exception as e:
        logging.error("Scraping failed: %s", e)
        write_payload(build_payload(date_kst, [], status="error", error_message=str(e)))
        raise SystemExit(1)

    if len(parsed) < 12:
        msg = f"Rankings incomplete: found {len(parsed)} items"
        logging.error(msg)
        write_payload(build_payload(date_kst, [], status="error", error_message=msg))
        raise SystemExit(1)

    # OpenAI 준비
    cache = load_cache()
    client = None

    if OpenAI is None:
        if STRICT_OPENAI:
            msg = "OpenAI SDK is not installed"
            logging.error(msg)
            write_payload(build_payload(date_kst, [], status="error", error_message=msg))
            raise SystemExit(1)
        logging.warning("OpenAI SDK missing: will output JP only")
    else:
        if not OPENAI_API_KEY:
            if STRICT_OPENAI:
                msg = "OPENAI_API_KEY is not set"
                logging.error(msg)
                write_payload(build_payload(date_kst, [], status="error", error_message=msg))
                raise SystemExit(1)
            logging.warning("OPENAI_API_KEY missing: will output JP only")
        else:
            client = OpenAI(api_key=OPENAI_API_KEY)

    rankings_out: List[Dict[str, Any]] = []
    openai_failed = False

    for item in parsed:
        rank = int(item["rank"])
        sign_jp = item["sign_jp"]
        message_jp = item.get("message_jp", "")

        # sign_key는 unknown이어도 기록(랭킹 비워지는 사고 방지)
        sign_key = SIGN_KEY_MAP.get(sign_jp, "unknown")
        sign_ko = SIGN_KO_MAP.get(sign_key, "알 수 없음")

        scores = generate_scores(rank, date_kst, sign_key)

        message_ko: Optional[str] = None
        ai: Optional[Dict[str, Any]] = None

        if client is not None:
            try:
                message_ko, ai = openai_generate_bundle(
                    client=client,
                    date_kst=date_kst,
                    sign_key=sign_key,
                    sign_ko=sign_ko,
                    message_jp=message_jp,
                    scores={
                        "overall": scores["overall"],
                        "total": scores["total"],
                        "love": scores["love"],
                        "study": scores["study"],
                        "money": scores["money"],
                        "health": scores["health"],
                    },
                    cache=cache,
                )
            except Exception as e:
                openai_failed = True
                if STRICT_OPENAI:
                    logging.error("OpenAI failed: %s", e)
                    write_payload(build_payload(date_kst, [], status="error", error_message=str(e)))
                    raise SystemExit(1)

        if client is not None and (message_ko is None or ai is None):
            openai_failed = True

        rankings_out.append(
            {
                "rank": rank,
                "sign_key": sign_key,
                "sign_jp": sign_jp,
                "sign_ko": sign_ko,
                "message_jp": message_jp,
                "message_ko": message_ko,
                "scores": {
                    "overall": scores["overall"],
                    "total": scores["total"],
                    "love": scores["love"],
                    "study": scores["study"],
                    "money": scores["money"],
                    "health": scores["health"],
                },
                "ai": ai,
            }
        )

    rankings_out.sort(key=lambda x: x["rank"])
    save_cache(cache)

    status = "partial" if openai_failed else "ok"
    error_message = "OpenAI generation partially failed" if openai_failed else ""
    write_payload(build_payload(date_kst, rankings_out, status=status, error_message=error_message))

    logging.info("Wrote %s with %d rankings (status=%s)", OUTPUT_PATH, len(rankings_out), status)


if __name__ == "__main__":
    main()
