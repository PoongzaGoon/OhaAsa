import os
import re
import json
import time
import hashlib
from datetime import datetime, timezone, timedelta

from playwright.sync_api import sync_playwright

# OpenAI Python SDK (Responses API)
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


def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def kst_today_str():
    kst = timezone(timedelta(hours=9))
    now = datetime.now(tz=kst)
    return now.strftime("%Y-%m-%d")


def normalize_whitespace(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def extract_json_text_from_response(resp) -> str:
    # Robust extraction: Responses API returns resp.output[] with message items
    # We want the first assistant message output_text
    if hasattr(resp, "output") and resp.output:
        for item in resp.output:
            if getattr(item, "type", None) == "message":
                content = getattr(item, "content", None) or []
                for part in content:
                    if getattr(part, "type", None) == "output_text":
                        return part.text
    # Fallback convenience
    if hasattr(resp, "output_text"):
        return resp.output_text
    raise RuntimeError("Failed to extract output_text from OpenAI response.")


def build_schema():
    # Output schema: strict JSON for your UI replacement
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
                        "required": ["one_liner", "overall_comment"],
                        "properties": {
                            "one_liner": {"type": "string"},
                            "overall_comment": {"type": "string"},
                        },
                    },
                    "cards": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["total", "love", "study", "money", "health"],
                        "properties": {
                            "total": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["score", "comment", "tip", "warning"],
                                "properties": {
                                    "score": {"type": "integer"},
                                    "comment": {"type": "string"},
                                    "tip": {"type": "string"},
                                    "warning": {"type": "string"},
                                },
                            },
                            "love": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["score", "comment", "tip", "warning"],
                                "properties": {
                                    "score": {"type": "integer"},
                                    "comment": {"type": "string"},
                                    "tip": {"type": "string"},
                                    "warning": {"type": "string"},
                                },
                            },
                            "study": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["score", "comment", "tip", "warning"],
                                "properties": {
                                    "score": {"type": "integer"},
                                    "comment": {"type": "string"},
                                    "tip": {"type": "string"},
                                    "warning": {"type": "string"},
                                },
                            },
                            "money": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["score", "comment", "tip", "warning"],
                                "properties": {
                                    "score": {"type": "integer"},
                                    "comment": {"type": "string"},
                                    "tip": {"type": "string"},
                                    "warning": {"type": "string"},
                                },
                            },
                            "health": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["score", "comment", "tip", "warning"],
                                "properties": {
                                    "score": {"type": "integer"},
                                    "comment": {"type": "string"},
                                    "tip": {"type": "string"},
                                    "warning": {"type": "string"},
                                },
                            },
                        },
                    },
                    "lucky_points": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["lucky_color", "lucky_number", "lucky_item", "lucky_keyword"],
                        "properties": {
                            "lucky_color": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["name_ko", "hex"],
                                "properties": {
                                    "name_ko": {"type": "string"},
                                    "hex": {"type": "string"},
                                },
                            },
                            "lucky_number": {"type": "integer"},
                            "lucky_item": {"type": "string"},
                            "lucky_keyword": {"type": "string"},
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
    sign_name_ja: str,
    message_ja: str,
    scores: dict,
    cache: dict,
) -> dict:
    """
    Returns dict matching schema:
      { message_ko: str, ai: { summary, cards, lucky_points } }
    Uses cache to avoid re-paying for same prompt.
    """
    message_ja = normalize_whitespace(message_ja)

    # Cache key: deterministic based on date + sign + message_ja + scores
    cache_key_raw = json.dumps(
        {
            "date_kst": date_kst,
            "sign_key": sign_key,
            "sign_name_ja": sign_name_ja,
            "message_ja": message_ja,
            "scores": scores,
            "model": OPENAI_MODEL,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    cache_key = sha1(cache_key_raw)

    if cache_key in cache:
        return cache[cache_key]

    schema = build_schema()

    system_prompt = (
        "너는 한국어 운세 콘텐츠 작가이자 로컬라이저다. "
        "입력으로 일본어 원문 운세와 점수(총운/연애/학업/금전/건강)가 주어진다. "
        "아래 규칙을 반드시 지켜라.\n\n"
        "규칙:\n"
        "1) 출력은 JSON만. 다른 텍스트 금지.\n"
        "2) 점수는 입력 값을 그대로 사용하고 바꾸지 마라.\n"
        "3) 문체는 담백하고 실용적이며 과장/공포 조장 금지.\n"
        "4) Tip/Warning은 각각 1문장, 짧고 실행 가능한 조언.\n"
        "5) one_liner는 18자 내외, overall_comment는 2~3문장.\n"
        "6) lucky_number는 1~9 정수.\n"
        "7) lucky_color.hex는 #RRGGBB.\n"
    )

    user_prompt = (
        f"date_kst: {date_kst}\n"
        f"sign_key: {sign_key}\n"
        f"sign_name_ja: {sign_name_ja}\n"
        f"message_ja: {message_ja}\n"
        f"scores: {json.dumps(scores, ensure_ascii=False)}\n\n"
        "요청:\n"
        "A) message_ko: message_ja를 자연스러운 한국어로 번역(뉘앙스 유지, 1~2문장)\n"
        "B) ai.summary: 오늘 전체 흐름 요약\n"
        "C) ai.cards: total/love/study/money/health 각각 score/comment/tip/warning 생성\n"
        "D) ai.lucky_points: lucky_color(이름+hex), lucky_number(1~9), lucky_item, lucky_keyword 생성\n"
    )

    resp = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "fortune_ai_bundle",
                "schema": schema,
                "strict": True,
            }
        },
        temperature=0.7,
        max_output_tokens=700,
    )

    txt = extract_json_text_from_response(resp)
    data = json.loads(txt)

    # Defensive validation (light)
    # Scores must match input
    for k in ["total", "love", "study", "money", "health"]:
        if int(data["ai"]["cards"][k]["score"]) != int(scores[k]):
            data["ai"]["cards"][k]["score"] = int(scores[k])

    # Lucky number range clamp
    ln = int(data["ai"]["lucky_points"]["lucky_number"])
    if ln < 1:
        data["ai"]["lucky_points"]["lucky_number"] = 1
    if ln > 9:
        data["ai"]["lucky_points"]["lucky_number"] = 9

    cache[cache_key] = data
    return data


def scrape_ohaasa_rankings(date_kst: str):
    """
    Scrape data from ohaasa/asahi horoscope page.
    Output items:
      [
        {
          "rank": 1,
          "sign_key": "aries|taurus|...",
          "sign_ja": "...座",
          "message_ja": "...",
          "scores": {"total": 87, "love": 85, "study": 94, "money": 80, "health": 93}
        },
        ...
      ]
    """
    url = "https://www.asahi.co.jp/ohaasa/horoscope/"
    items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(500)

        # The page uses li per rank. You already verified selectors in DevTools:
        # ul.oa_horoscope_list > li ...
        li_nodes = page.query_selector_all("ul.oa_horoscope_list > li")
        for li in li_nodes:
            rank_el = li.query_selector(".horo_rank")
            name_el = li.query_selector(".horo_name")
            txt_el = li.query_selector(".horo_txt")

            if not (rank_el and name_el and txt_el):
                continue

            rank_str = normalize_whitespace(rank_el.inner_text())
            sign_ja = normalize_whitespace(name_el.inner_text())
            message_ja = normalize_whitespace(txt_el.inner_text())

            # Rank like "1"
            try:
                rank = int(re.sub(r"[^\d]", "", rank_str))
            except Exception:
                continue

            # You likely map JP sign name to western sign key in another file,
            # but here is a minimal mapping by Japanese suffix strings.
            sign_key = jp_sign_to_key(sign_ja)

            # Scores are not on this list view; if you already scrape scores elsewhere,
            # keep your existing score-scrape logic here.
            scores = scrape_scores_for_sign(page, sign_key)

            items.append(
                {
                    "rank": rank,
                    "sign_key": sign_key,
                    "sign_ja": sign_ja,
                    "message_ja": message_ja,
                    "scores": scores,
                }
            )

        browser.close()

    # Ensure 12
    items.sort(key=lambda x: x["rank"])
    return items


def jp_sign_to_key(sign_ja: str) -> str:
    # Minimal JP -> key mapping
    # (Adjust if your project already has a definitive mapping.)
    mapping = {
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
    return mapping.get(sign_ja, "unknown")


def scrape_scores_for_sign(page, sign_key: str) -> dict:
    """
    Placeholder:
    If your current script already scrapes scores via detail view / another endpoint,
    move that logic here.
    For now, default to your existing behavior if you already had scores.
    """
    # If you already have score scraping in your current fetch_ohaasa.py,
    # replace this placeholder with your existing logic.

    # Safe defaults (will keep UI working even if score scrape breaks)
    return {"total": 50, "love": 50, "study": 50, "money": 50, "health": 50}


def main():
    ensure_cache_dir()

    # OpenAI key required
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY in environment variables.")

    client = OpenAI()

    date_kst = kst_today_str()
    ai_cache = load_json(AI_CACHE_PATH, default={})

    rankings = scrape_ohaasa_rankings(date_kst)

    out = {
        "source": "asahi_ohaasa",
        "date_kst": date_kst,
        "updated_at_kst": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "status": "ok",
        "error_message": "",
        "rankings": [],
    }

    for it in rankings:
        sign_key = it["sign_key"]
        sign_ja = it["sign_ja"]
        message_ja = it["message_ja"]
        scores = it["scores"]

        try:
            ai_bundle = openai_generate_ai_bundle(
                client,
                date_kst=date_kst,
                sign_key=sign_key,
                sign_name_ja=sign_ja,
                message_ja=message_ja,
                scores=scores,
                cache=ai_cache,
            )
        except Exception as e:
            ai_bundle = {
                "message_ko": "",
                "ai": None,
                "error": f"openai_failed: {str(e)}",
            }

        out["rankings"].append(
            {
                "rank": it["rank"],
                "sign_key": sign_key,
                "sign_ja": sign_ja,
                "message_ja": message_ja,
                "message_ko": ai_bundle.get("message_ko", ""),
                "scores": scores,
                "ai": ai_bundle.get("ai", None),
            }
        )

        # Gentle rate limit protection
        time.sleep(0.2)

    save_json(AI_CACHE_PATH, ai_cache)
    save_json(OUT_PATH, out)
    print(f"Updated: {OUT_PATH}")


if __name__ == "__main__":
    main()
