import os
import re
import json
import time
import hashlib
from datetime import datetime, timezone, timedelta

from playwright.sync_api import sync_playwright
from openai import OpenAI

# -----------------------------
# Paths
# -----------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT_DIR, "public", "fortune.json")
CACHE_DIR = os.path.join(ROOT_DIR, "scripts", "cache")
AI_CACHE_PATH = os.path.join(CACHE_DIR, "openai_cache.json")

# -----------------------------
# OpenAI config
# -----------------------------
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")


# -----------------------------
# Utils
# -----------------------------
def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def kst_now():
    return datetime.now(timezone(timedelta(hours=9)))


def kst_today_str():
    return kst_now().strftime("%Y-%m-%d")


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def clamp_int(n, lo, hi, default):
    try:
        n = int(n)
    except Exception:
        return default
    return max(lo, min(hi, n))


def normalize_hex(hex_str: str, fallback="#8B7BFF"):
    hex_str = (hex_str or "").strip()
    if re.match(r"^#[0-9A-Fa-f]{6}$", hex_str):
        return hex_str.upper()
    return fallback


def safe_print(msg: str):
    # Actions 로그에서 한글 깨짐 방지 겸용
    try:
        print(msg, flush=True)
    except Exception:
        pass


# -----------------------------
# Zodiac mapping (JP -> key/KO)
# -----------------------------
JP_TO_KEY = {
    "おひつじ座": "aries",
    "おうし座": "taurus",
    "ふたご座": "gemini",
    "かに座": "cancer",
    "しし座": "leo",
    "おとめ座": "virgo",
    "てんびん座": "libra",
    "さそり座": "scorpio",
    "いて座": "sagittarius",
    "やぎ座": "capricorn",
    "みずがめ座": "aquarius",
    "うお座": "pisces",
}

JP_TO_KO = {
    "おひつじ座": "양자리",
    "おうし座": "황소자리",
    "ふたご座": "쌍둥이자리",
    "かに座": "게자리",
    "しし座": "사자자리",
    "おとめ座": "처녀자리",
    "てんびん座": "천칭자리",
    "さそり座": "전갈자리",
    "いて座": "사수자리",
    "やぎ座": "염소자리",
    "みずがめ座": "물병자리",
    "うお座": "물고기자리",
}


def jp_sign_to_key(sign_jp: str) -> str:
    return JP_TO_KEY.get(sign_jp, "unknown")


def jp_sign_to_ko(sign_jp: str) -> str:
    return JP_TO_KO.get(sign_jp, "알 수 없음")


# -----------------------------
# Scraping
# -----------------------------
def scrape_ohaasa_rankings() -> list:
    """
    리스트 루트: ul.oa_horoscope_list > li
    랭크: .horo_rank
    별자리명: .horo_name
    멘트: .horo_txt

    return: [{rank, sign_key, sign_jp, message_jp, scores}, ...]  (12개 기대)
    """
    url = "https://www.asahi.co.jp/ohaasa/horoscope/"
    items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(500)

        li_nodes = page.query_selector_all("ul.oa_horoscope_list > li")
        for li in li_nodes:
            rank_el = li.query_selector(".horo_rank")
            name_el = li.query_selector(".horo_name")
            txt_el = li.query_selector(".horo_txt")
            if not (rank_el and name_el and txt_el):
                continue

            rank_str = normalize_whitespace(rank_el.inner_text())
            sign_jp = normalize_whitespace(name_el.inner_text())
            message_jp = normalize_whitespace(txt_el.inner_text())

            try:
                rank = int(re.sub(r"[^\d]", "", rank_str))
            except Exception:
                continue

            sign_key = jp_sign_to_key(sign_jp)

            # 점수는 지금 “실제 크롤링 미구현”이라 placeholder 유지 (원복 안정화 목적)
            scores = scrape_scores_for_sign_placeholder()

            items.append(
                {
                    "rank": rank,
                    "sign_key": sign_key,
                    "sign_jp": sign_jp,
                    "message_jp": message_jp,
                    "scores": scores,
                }
            )

        browser.close()

    items.sort(key=lambda x: x["rank"])
    return items


def scrape_scores_for_sign_placeholder() -> dict:
    # 기존(과거)처럼 일단 고정값으로 유지. (나중에 상세페이지 로직 추가하면 여기만 갈아끼우면 됨)
    return {"total": 50, "love": 50, "study": 50, "money": 50, "health": 50}


# -----------------------------
# OpenAI Responses API helpers
# -----------------------------
def extract_output_text(resp) -> str:
    """
    Responses API: resp.output[] 안의 message/content[]에서 output_text 추출
    """
    if hasattr(resp, "output") and resp.output:
        for item in resp.output:
            if getattr(item, "type", None) == "message":
                content = getattr(item, "content", None) or []
                for part in content:
                    if getattr(part, "type", None) == "output_text":
                        return part.text
    if hasattr(resp, "output_text"):
        return resp.output_text
    raise RuntimeError("Failed to extract output_text from OpenAI response.")


def build_ai_bundle_schema():
    """
    중요:
    - strict json_schema에서는 'properties'에 있는 키는 전부 required에 포함되어야 함.
    - nested object들도 동일.
    """
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["message_ko", "ai"],
        "properties": {
            "message_ko": {"type": "string"},
            "ai": {
                "type": "object",
                "additionalProperties": False,
                "required": ["summary", "cards", "lucky_points"],
                "properties": {
                    "summary": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["vibe", "one_liner", "focus"],
                        "properties": {
                            "vibe": {"type": "string"},
                            "one_liner": {"type": "string"},
                            "focus": {"type": "string"},
                        },
                    },
                    "cards": {
                        "type": "array",
                        "minItems": 5,
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "category",
                                "title",
                                "vibe",
                                "score",
                                "headline",
                                "detail",
                                "tip",
                                "warning",
                            ],
                            "properties": {
                                "category": {
                                    "type": "string",
                                    "enum": ["good", "love", "study", "money", "health"],
                                },
                                "title": {"type": "string"},
                                "vibe": {"type": "string"},
                                "score": {"type": "integer"},
                                "headline": {"type": "string"},
                                "detail": {"type": "string"},
                                "tip": {"type": "string"},
                                "warning": {"type": "string"},
                            },
                        },
                    },
                    "lucky_points": {
                        "type": "object",
                        "additionalProperties": False,
                        # ⭐ reasons가 properties에 있으면 required에도 반드시 포함해야 400이 안 남
                        "required": ["color_name", "color_hex", "number", "item", "keyword", "reasons"],
                        "properties": {
                            "color_name": {"type": "string"},
                            "color_hex": {"type": "string"},
                            "number": {"type": "integer"},
                            "item": {"type": "string"},
                            "keyword": {"type": "string"},
                            "reasons": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 3,
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    }


def openai_generate_ai_bundle(
    client: OpenAI,
    *,
    date_kst: str,
    sign_key: str,
    sign_jp: str,
    message_jp: str,
    scores: dict,
    cache: dict,
) -> dict:
    """
    한 번 호출로:
    - message_ko 번역
    - ai.summary/cards/lucky_points 생성
    캐시: date_kst + sign_key + message_jp 해시
    """
    message_jp = normalize_whitespace(message_jp)
    cache_key = sha1(f"{date_kst}|{sign_key}|{message_jp}")
    if cache_key in cache:
        return cache[cache_key]

    schema = build_ai_bundle_schema()

    # 점수는 "입력 그대로 유지" 강제
    score_by_category = {
        "good": int(scores["total"]),
        "love": int(scores["love"]),
        "study": int(scores["study"]),
        "money": int(scores["money"]),
        "health": int(scores["health"]),
    }

    system_prompt = (
        "너는 한국어 운세 콘텐츠 작가이자 로컬라이저다.\n"
        "입력은 일본어 원문 운세와 점수(총운/연애/학업/금전/건강)다.\n\n"
        "규칙(절대 준수):\n"
        "1) 출력은 JSON만. 다른 텍스트 금지.\n"
        "2) 점수(score)는 입력값을 그대로 사용(절대 변경 금지).\n"
        "3) 문체: 담백/실용. 과장/공포/확정(투자·의학 단정) 금지.\n"
        "4) cards는 정확히 5개, category는 good/love/study/money/health를 각각 1회.\n"
        "5) tip/warning은 각각 1문장, 짧고 실행 가능하게.\n"
        "6) lucky_points.number: 1~9 정수, color_hex: #RRGGBB.\n"
        "7) lucky_points.reasons: 1~3개, 짧은 근거.\n"
    )

    user_prompt = (
        f"date_kst: {date_kst}\n"
        f"sign_key: {sign_key}\n"
        f"sign_name_ja: {sign_jp}\n"
        f"message_jp: {message_jp}\n"
        f"scores:\n{json.dumps(scores, ensure_ascii=False)}\n\n"
        "요청:\n"
        "A) message_ko: message_jp를 자연스러운 한국어 1~2문장으로 번역\n"
        "B) ai.summary: vibe/one_liner/focus 작성\n"
        "C) ai.cards: category/title/vibe/score/headline/detail/tip/warning 생성\n"
        "D) ai.lucky_points: color_name/color_hex/number/item/keyword/reasons 생성\n"
    )

    def request_once(extra: str = ""):
        prompt = user_prompt if not extra else (user_prompt + "\n\n" + extra)

        # 핵심: text.format에 name/schema/strict가 정확히 있어야 함
        resp = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "ohaasa_ai_bundle",  # <- name 필수(누락하면 'text.format.name' 400)
                    "schema": schema,
                    "strict": True,
                }
            },
            temperature=0.7,
            max_output_tokens=900,
        )
        raw = extract_output_text(resp)
        return json.loads(raw)

    # JSON 파싱 실패 등은 1회 재시도
    try:
        data = request_once()
    except Exception:
        data = request_once("출력 포맷이 깨졌다. JSON 객체만 정확히 다시 출력해라.")

    # -----------------------------
    # Post-fix (안전 보정)
    # -----------------------------
    # 1) cards: category 중복 제거 + score를 입력값으로 강제 덮어쓰기 + 5개 보정
    seen = set()
    fixed_cards = []
    for c in (data.get("ai", {}) or {}).get("cards", []) or []:
        cat = c.get("category")
        if cat not in score_by_category or cat in seen:
            continue
        c["score"] = score_by_category[cat]  # 입력 점수 강제
        fixed_cards.append(c)
        seen.add(cat)

    # 부족하면 fallback 생성
    default_titles = {
        "good": "전체 흐름",
        "love": "관계 흐름",
        "study": "집중 흐름",
        "money": "지출 흐름",
        "health": "컨디션 흐름",
    }
    for cat in ["good", "love", "study", "money", "health"]:
        if cat in seen:
            continue
        fixed_cards.append(
            {
                "category": cat,
                "title": default_titles[cat],
                "vibe": "안정",
                "score": score_by_category[cat],
                "headline": "리듬을 점검해 보세요",
                "detail": "무리하지 않고 오늘 할 일을 차근차근 정리하면 흐름을 유지하기 좋습니다.",
                "tip": "가장 작은 할 일을 먼저 끝내 보세요.",
                "warning": "결과를 서두르기보다 속도를 조절하세요.",
            }
        )

    data["ai"]["cards"] = fixed_cards[:5]

    # 2) lucky_points: HEX/number/reasons 보정
    lucky = data["ai"].get("lucky_points", {}) or {}
    lucky["color_hex"] = normalize_hex(lucky.get("color_hex"), "#8B7BFF")
    lucky["number"] = clamp_int(lucky.get("number", 1), 1, 9, 1)

    reasons = lucky.get("reasons")
    if not isinstance(reasons, list) or len(reasons) == 0:
        lucky["reasons"] = ["오늘의 흐름과 잘 맞는 선택이에요."]
    else:
        lucky["reasons"] = [normalize_whitespace(str(x)) for x in reasons[:3] if normalize_whitespace(str(x))]

    data["ai"]["lucky_points"] = lucky

    cache[cache_key] = data
    return data


# -----------------------------
# Main
# -----------------------------
def main():
    ensure_dir(CACHE_DIR)

    # 키 없으면 즉시 실패(원하는 동작)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY in environment variables.")

    client = OpenAI()

    date_kst = kst_today_str()
    ai_cache = load_json(AI_CACHE_PATH, default={})

    out = {
        "source": "asahi_ohaasa",
        "date_kst": date_kst,
        "updated_at_kst": kst_now().isoformat(),
        "status": "ok",
        "error_message": "",
        "rankings": [],
    }

    try:
        rankings = scrape_ohaasa_rankings()
    except Exception as e:
        out["status"] = "error"
        out["error_message"] = f"scrape_failed: {str(e)}"
        save_json(OUT_PATH, out)
        safe_print(f"[ERROR] scraping failed: {e}")
        return

    if not rankings:
        out["status"] = "error"
        out["error_message"] = "scrape_failed: empty rankings"
        save_json(OUT_PATH, out)
        safe_print("[ERROR] scraping returned empty rankings")
        return

    for it in rankings:
        sign_key = it["sign_key"]
        sign_jp = it["sign_jp"]
        message_jp = it["message_jp"]
        scores = it["scores"]

        message_ko = ""
        ai = None

        try:
            bundle = openai_generate_ai_bundle(
                client,
                date_kst=date_kst,
                sign_key=sign_key,
                sign_jp=sign_jp,
                message_jp=message_jp,
                scores=scores,
                cache=ai_cache,
            )
            message_ko = bundle.get("message_ko", "")
            ai = bundle.get("ai", None)
        except Exception as e:
            # OpenAI 실패해도 스크래핑 결과는 살려서 rankings 채움 (fortune.json 빈 깡통 방지)
            safe_print(f"[WARN] openai failed for {sign_key}: {e}")

        out["rankings"].append(
            {
                "rank": it["rank"],
                "sign_key": sign_key,
                "sign_jp": sign_jp,
                "sign_ko": jp_sign_to_ko(sign_jp),
                "message_jp": message_jp,
                "message_ko": message_ko,
                "scores": scores,
                "ai": ai,
            }
        )

        time.sleep(0.2)

    save_json(AI_CACHE_PATH, ai_cache)
    save_json(OUT_PATH, out)
    safe_print(f"Updated: {OUT_PATH}")


if __name__ == "__main__":
    main()
