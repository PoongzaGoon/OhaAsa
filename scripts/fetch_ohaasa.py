#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import hashlib
import datetime
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# -----------------------------
# Config
# -----------------------------
OHAASA_URL = "https://www.asahi.co.jp/ohaasa/week/horoscope/"
OUTPUT_PATH = os.path.join("public", "fortune.json")
ERROR_OUTPUT_PATH = os.path.join("public", "fortune.error.json")
CACHE_PATH = os.path.join("scripts", "cache", "openai_cache.json")

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"

# If scraping result is suspiciously small, fail workflow to avoid committing garbage
MIN_RANKINGS = 12

# Playwright timeouts (ms)
NAV_TIMEOUT = 60_000
SEL_TIMEOUT = 90_000

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# -----------------------------
# Helpers
# -----------------------------
def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def now_kst_iso() -> str:
    # KST = UTC+9 (no DST)
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).replace(microsecond=0).isoformat() + "+09:00"


def today_kst_date() -> str:
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date().isoformat()


def stable_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json(path: str, obj: Dict[str, Any]) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def save_json_atomic(path: str, obj: Dict[str, Any]) -> None:
    ensure_dir(os.path.dirname(path))
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def validate_rankings_output(rankings: List[Dict[str, Any]]) -> Tuple[bool, str]:
    if len(rankings) != 12:
        return False, f"rankings_length_invalid: expected 12 got {len(rankings)}"

    ranks: List[int] = []
    for item in rankings:
        try:
            rank = int(item.get("rank"))
        except Exception:
            return False, f"invalid_rank_type: {item.get('rank')}"
        ranks.append(rank)

    expected = set(range(1, 13))
    found = set(ranks)
    if found != expected:
        return False, f"rank_set_invalid: found={sorted(found)} expected={sorted(expected)}"

    return True, ""


# -----------------------------
# Scraping
# -----------------------------
@dataclass
class RankingItem:
    sign_key: str
    rank: int
    sign_jp: str
    message_jp: str

    # These may be filled later
    sign_ko: str = ""
    message_ko: str = ""
    scores: Optional[Dict[str, int]] = None
    ai: Optional[Dict[str, Any]] = None


def slugify_sign_key(jp_name: str) -> str:
    # Simple stable key from JP sign name
    # e.g. "おひつじ座" -> "jp_おひつじ座"
    # (You can replace with your canonical mapping later)
    return "jp_" + jp_name.strip()


def scrape_ohaasa_rankings() -> List[RankingItem]:
    items: List[RankingItem] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="ja-JP",
            extra_http_headers={
                "Accept-Language": "ja,en-US;q=0.8,en;q=0.6,ko;q=0.4",
            },
        )
        page = context.new_page()

        # Navigate
        eprint(f"[INFO] goto url={OHAASA_URL}")
        page.goto(OHAASA_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        eprint(f"[INFO] landed url={page.url}")

        # Redirect guard (your log showed it ended at asahi.com)
        if "asahi.co.jp/ohaasa/week/horoscope" not in page.url:
            raise RuntimeError(f"Unexpected redirect: landed on {page.url}")

        # Wait for list to appear
        try:
            eprint("[INFO] waiting selector=ul.oa_horoscope_list > li")
            page.wait_for_selector("ul.oa_horoscope_list > li", timeout=SEL_TIMEOUT)
        except PlaywrightTimeoutError as te:
            # Dump a little debug info
            raise RuntimeError(
                "Scrape timeout: 'ul.oa_horoscope_list > li' not found. "
                f"Current URL: {page.url}"
            ) from te

        lis = page.query_selector_all("ul.oa_horoscope_list > li")
        eprint(f"[INFO] scraped li count={len(lis)}")
        for li in lis:
            # rank
            rank_txt = (li.query_selector(".horo_rank").inner_text() if li.query_selector(".horo_rank") else "").strip()
            # sign name
            sign_txt = (li.query_selector(".horo_name").inner_text() if li.query_selector(".horo_name") else "").strip()
            # message
            msg_txt = (li.query_selector(".horo_txt").inner_text() if li.query_selector(".horo_txt") else "").strip()

            if not (rank_txt and sign_txt and msg_txt):
                continue

            # Some pages include "1位" style
            rank_num = int("".join([c for c in rank_txt if c.isdigit()]) or "0")
            if rank_num <= 0:
                continue

            sign_key = slugify_sign_key(sign_txt)
            items.append(RankingItem(sign_key=sign_key, rank=rank_num, sign_jp=sign_txt, message_jp=msg_txt))

        context.close()
        browser.close()

    # Sort by rank
    items.sort(key=lambda x: x.rank)
    return items


def scrape_scores_for_sign(_sign_key: str) -> Dict[str, int]:
    # Placeholder until you implement score scraping from detail pages
    return {"total": 50, "love": 50, "study": 50, "money": 50, "health": 50}


# -----------------------------
# OpenAI (Responses API) - one call per sign
# -----------------------------
def build_ai_bundle_schema() -> Dict[str, Any]:
    """
    Enforces JSON output with:
    {
      "message_ko": "...",
      "ai": {
        "summary": { "title": "...", "body": "..."},
        "cards": [ {category, score, headline, detail, tip, warning}, ...5 ],
        "lucky_points": {color_name,color_hex,number,item,keyword,reasons}
      }
    }
    """
    card = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": ["total", "love", "study", "money", "health"]},
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "headline": {"type": "string"},
            "detail": {"type": "string"},
            "tip": {"type": "string"},
            "warning": {"type": "string"},
        },
        "required": ["category", "score", "headline", "detail", "tip", "warning"],
        "additionalProperties": False,
    }

    lucky = {
        "type": "object",
        "properties": {
            "color_name": {"type": "string"},
            "color_hex": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
            "number": {"type": "integer", "minimum": 1, "maximum": 9},
            "item": {"type": "string"},
            "keyword": {"type": "string"},
            "reasons": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 4,
            },
        },
        "required": ["color_name", "color_hex", "number", "item", "keyword", "reasons"],
        "additionalProperties": False,
    }

    schema = {
        "type": "object",
        "properties": {
            "message_ko": {"type": "string"},
            "ai": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "body": {"type": "string"},
                        },
                        "required": ["title", "body"],
                        "additionalProperties": False,
                    },
                    "cards": {
                        "type": "array",
                        "items": card,
                        "minItems": 5,
                        "maxItems": 5,
                    },
                    "lucky_points": lucky,
                },
                "required": ["summary", "cards", "lucky_points"],
                "additionalProperties": False,
            },
        },
        "required": ["message_ko", "ai"],
        "additionalProperties": False,
    }
    return schema


def openai_generate_bundle(
    *,
    model: str,
    date_kst: str,
    sign_jp: str,
    message_jp: str,
    scores: Dict[str, int],
    cache: Dict[str, Any],
) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    cache_key = stable_hash(f"{date_kst}|{sign_jp}|{message_jp}")
    if cache_key in cache:
        return cache[cache_key]

    schema = build_ai_bundle_schema()

    system_instructions = (
        "너는 한국어 운세 콘텐츠 에디터다.\n"
        "- 입력은 일본어 별자리명(sign_jp)과 일본어 운세문(message_jp), 점수(scores)다.\n"
        "- 반드시 JSON만 출력한다 (설명/코드블록 금지).\n"
        "- message_ko: message_jp의 자연스러운 한국어 번역 (의미 보존, 과한 의역 금지).\n"
        "- ai.summary: 화면 상단 요약(짧고 선명).\n"
        "- ai.cards: total/love/study/money/health 5개를 각각 1개씩, category로 매칭.\n"
        "  score는 입력 scores의 값을 그대로 사용.\n"
        "  headline/detail/tip/warning은 서로 중복되지 않게.\n"
        "- ai.lucky_points: 색/숫자/아이템/키워드를 정하고 reasons는 1~4개.\n"
        "- 금지: 혐오/차별/폭력 조장, 과도한 선정성, 의학적 확답.\n"
    )

    user_prompt = (
        f"date_kst: {date_kst}\n"
        f"sign_jp: {sign_jp}\n"
        f"message_jp: {message_jp}\n"
        f"scores: {json.dumps(scores, ensure_ascii=False)}\n"
        "위 입력을 기반으로 스키마에 맞는 JSON을 생성해."
    )

    payload: Dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_instructions}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "ohaasa_ai_bundle",
                "schema": schema,
                "strict": True,
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    def do_request() -> Dict[str, Any]:
        r = requests.post(OPENAI_ENDPOINT, headers=headers, data=json.dumps(payload), timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text}")
        data = r.json()

        # Responses API returns output content; easiest is to read output_text
        # Find first output_text in response.output[]
        out_text = None
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    out_text = c.get("text")
                    break
            if out_text:
                break
        if not out_text:
            raise RuntimeError(f"OpenAI response missing output_text: {json.dumps(data)[:1000]}")
        return json.loads(out_text)

    # 1 retry on JSON parse or transient issues
    last_err: Optional[Exception] = None
    for attempt in range(2):
        try:
            bundle = do_request()
            cache[cache_key] = bundle
            return bundle
        except Exception as e:
            last_err = e
            time.sleep(1.2)

    raise RuntimeError(f"OpenAI generation failed: {last_err}")


# -----------------------------
# Post-processing guards
# -----------------------------
def normalize_hex(s: str) -> str:
    s = (s or "").strip()
    if not s.startswith("#"):
        s = "#" + s
    if len(s) == 4:  # #abc -> #aabbcc
        s = "#" + "".join([ch * 2 for ch in s[1:]])
    if len(s) != 7:
        return "#999999"
    # force hex chars
    ok = "0123456789abcdefABCDEF"
    if any(ch not in ok for ch in s[1:]):
        return "#999999"
    return s


def clamp_int(v: Any, lo: int, hi: int, default: int) -> int:
    try:
        x = int(v)
        return max(lo, min(hi, x))
    except Exception:
        return default


def fix_bundle(bundle: Dict[str, Any], scores: Dict[str, int]) -> Dict[str, Any]:
    # Ensure score is exactly input scores and exactly 5 cards
    ai = bundle.get("ai", {})
    cards = ai.get("cards", [])
    by_cat = {c.get("category"): c for c in cards if isinstance(c, dict)}

    fixed_cards: List[Dict[str, Any]] = []
    for cat in ["total", "love", "study", "money", "health"]:
        c = by_cat.get(cat, {})
        fixed_cards.append(
            {
                "category": cat,
                "score": clamp_int(scores.get(cat, 50), 0, 100, 50),
                "headline": str(c.get("headline", "")).strip() or "오늘의 흐름",
                "detail": str(c.get("detail", "")).strip() or "무난하게 흘러갈 가능성이 큽니다.",
                "tip": str(c.get("tip", "")).strip() or "작게라도 바로 실행해보세요.",
                "warning": str(c.get("warning", "")).strip() or "무리한 확신은 피하세요.",
            }
        )

    lucky = ai.get("lucky_points", {}) if isinstance(ai.get("lucky_points", {}), dict) else {}
    lucky_fixed = {
        "color_name": str(lucky.get("color_name", "")).strip() or "산뜻한 블루",
        "color_hex": normalize_hex(str(lucky.get("color_hex", "#4A90E2"))),
        "number": clamp_int(lucky.get("number", 7), 1, 9, 7),
        "item": str(lucky.get("item", "")).strip() or "작은 메모",
        "keyword": str(lucky.get("keyword", "")).strip() or "정리",
        "reasons": [str(x).strip() for x in (lucky.get("reasons") or []) if str(x).strip()] or ["집중력을 유지하는 데 도움"],
    }

    summary = ai.get("summary", {}) if isinstance(ai.get("summary", {}), dict) else {}
    summary_fixed = {
        "title": str(summary.get("title", "")).strip() or "오늘의 운세 요약",
        "body": str(summary.get("body", "")).strip() or "흐름을 읽고, 작게 움직이면 성과가 따라옵니다.",
    }

    return {
        "message_ko": str(bundle.get("message_ko", "")).strip() or "",
        "ai": {"summary": summary_fixed, "cards": fixed_cards, "lucky_points": lucky_fixed},
    }


# -----------------------------
# Main
# -----------------------------
def main() -> int:
    date_kst = today_kst_date()
    updated_at_kst = now_kst_iso()

    # Cache load
    ensure_dir(os.path.dirname(CACHE_PATH))
    cache = load_json(CACHE_PATH) or {}

    # Scrape
    try:
        rankings = scrape_ohaasa_rankings()
    except Exception as e:
        eprint(f"[ERROR] scrape failed: {e}")
        out = {
            "source": "asahi_ohaasa",
            "date_kst": date_kst,
            "updated_at_kst": updated_at_kst,
            "status": "error",
            "error_message": f"scrape_failed: {e}",
            "rankings": [],
        }
        save_json(ERROR_OUTPUT_PATH, out)
        return 1

    if len(rankings) < MIN_RANKINGS:
        eprint(f"[ERROR] scrape too small: got {len(rankings)} items")
        out = {
            "source": "asahi_ohaasa",
            "date_kst": date_kst,
            "updated_at_kst": updated_at_kst,
            "status": "error",
            "error_message": f"scrape_incomplete: got {len(rankings)} items",
            "rankings": [],
        }
        save_json(ERROR_OUTPUT_PATH, out)
        return 1

    # Enrich per sign
    enriched: List[Dict[str, Any]] = []
    for r in rankings:
        scores = scrape_scores_for_sign(r.sign_key)

        # OpenAI bundle (one call)
        try:
            raw_bundle = openai_generate_bundle(
                model=DEFAULT_MODEL,
                date_kst=date_kst,
                sign_jp=r.sign_jp,
                message_jp=r.message_jp,
                scores=scores,
                cache=cache,
            )
            bundle = fix_bundle(raw_bundle, scores)
            r.message_ko = bundle["message_ko"]
            r.ai = bundle["ai"]
        except Exception as e:
            # If OpenAI fails, still keep scraping output but mark ai as missing
            eprint(f"[WARN] OpenAI failed for {r.sign_jp} (rank {r.rank}): {e}")
            r.message_ko = ""
            r.ai = None

        enriched.append(
            {
                "sign_key": r.sign_key,
                "rank": r.rank,
                "sign_jp": r.sign_jp,
                "sign_ko": r.sign_ko,  # optional mapping later
                "message_jp": r.message_jp,
                "message_ko": r.message_ko,
                "scores": scores,
                "ai": r.ai,
            }
        )

    # Save cache
    save_json(CACHE_PATH, cache)

    # If *all* ai generation failed, treat as error (prevents silent garbage)
    if all(item.get("ai") is None for item in enriched):
        eprint("[ERROR] OpenAI failed for all signs")
        save_json(ERROR_OUTPUT_PATH, {
            "source": "asahi_ohaasa",
            "date_kst": date_kst,
            "updated_at_kst": updated_at_kst,
            "status": "error",
            "error_message": "openai_failed_all",
            "rankings": [],
        })
        return 1

    valid, validation_error = validate_rankings_output(enriched)
    if not valid:
        eprint(f"[ERROR] output validation failed: {validation_error}")
        save_json(ERROR_OUTPUT_PATH, {
            "source": "asahi_ohaasa",
            "date_kst": date_kst,
            "updated_at_kst": updated_at_kst,
            "status": "error",
            "error_message": validation_error,
            "rankings": [],
        })
        return 1

    # Final output (atomic replace only after validation)
    out = {
        "source": "asahi_ohaasa",
        "date_kst": date_kst,
        "updated_at_kst": updated_at_kst,
        "status": "ok",
        "error_message": "",
        "rankings": sorted(enriched, key=lambda item: int(item.get("rank", 999))),
    }
    save_json_atomic(OUTPUT_PATH, out)

    print("[OK] fortune.json generated:", OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
