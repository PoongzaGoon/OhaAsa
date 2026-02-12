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
                        "required": ["color_name", "color_hex", "number", "item", "keyword"],
                        "properties": {
                            "color_name": {"type": "string"},
                            "color_hex": {"type": "string"},
                            "number": {"type": "integer"},
                            "item": {"type": "string"},
                            "keyword": {"type": "string"},
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
    message_jp: str,
    scores: dict,
    cache: dict,
) -> dict:
    """
    Returns dict matching schema:
      { message_ko: str, ai: { summary, cards, lucky_points } }
    Uses cache to avoid re-paying for same prompt.
    """
    message_jp = normalize_whitespace(message_jp)

    cache_key = sha1(f"{date_kst}|{sign_key}|{message_jp}")

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
        "3) 문체는 담백하고 실용적이며 과장/공포 조장 금지. 투자/의학 확정 표현 금지.\n"
        "4) cards는 정확히 5개이며 category는 [good,love,study,money,health]를 각각 1회씩 사용.\n"
        "5) tip/warning은 각각 1문장, 짧고 실행 가능한 조언.\n"
        "6) lucky_points.number는 1~9 정수, color_hex는 반드시 #RRGGBB.\n"
    )

    user_prompt = (
        f"date_kst: {date_kst}\n"
        f"sign_key: {sign_key}\n"
        f"sign_name_ja: {sign_name_ja}\n"
        f"message_jp: {message_jp}\n"
        f"scores: {json.dumps(scores, ensure_ascii=False)}\n\n"
        "요청:\n"
        "A) message_ko: message_jp를 자연스러운 한국어로 번역(뉘앙스 유지, 1~2문장)\n"
        "B) ai.summary: vibe, one_liner, focus 작성\n"
        "C) ai.cards: category/title/vibe/score/headline/detail/tip/warning 생성\n"
        "D) ai.lucky_points: color_name/color_hex/number/item/keyword 생성\n"
    )

    def request_bundle(extra_instruction: str = ""):
        prompt = user_prompt if not extra_instruction else f"{user_prompt}\n\n{extra_instruction}"
        resp = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
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
            max_output_tokens=900,
        )
        txt = extract_json_text_from_response(resp)
        return json.loads(txt)

    try:
        data = request_bundle()
    except Exception:
        data = request_bundle("출력 포맷이 깨졌다. JSON 객체만 정확히 다시 출력해라.")

    score_by_category = {
        "good": int(scores["total"]),
        "love": int(scores["love"]),
        "study": int(scores["study"]),
        "money": int(scores["money"]),
        "health": int(scores["health"]),
    }
    cards = []
    seen = set()
    for card in data["ai"].get("cards", []):
        category = card.get("category")
        if category not in score_by_category or category in seen:
            continue
        card["score"] = score_by_category[category]
        cards.append(card)
        seen.add(category)

    default_cards = {
        "good": "전체 흐름",
        "love": "관계 흐름",
        "study": "집중 흐름",
        "money": "지출 흐름",
        "health": "컨디션 흐름",
    }
    for category in ["good", "love", "study", "money", "health"]:
        if category in seen:
            continue
        cards.append(
            {
                "category": category,
                "title": default_cards[category],
                "vibe": "안정",
                "score": score_by_category[category],
                "headline": "리듬을 점검해 보세요",
                "detail": "무리하지 않고 오늘 할 일을 차근차근 정리하면 흐름을 유지하기 좋습니다.",
                "tip": "작은 목표를 먼저 완료해 보세요.",
                "warning": "결과를 서두르기보다 속도를 조절하세요.",
            }
        )

    data["ai"]["cards"] = cards

    lucky = data["ai"].get("lucky_points", {})
    if not re.match(r"^#[0-9A-Fa-f]{6}$", str(lucky.get("color_hex", ""))):
        lucky["color_hex"] = "#8B7BFF"

    try:
        lucky_number = int(lucky.get("number", 1))
    except Exception:
        lucky_number = 1
    lucky["number"] = min(max(lucky_number, 1), 9)
    data["ai"]["lucky_points"] = lucky

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
          "sign_jp": "...座",
          "message_jp": "...",
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
            sign_jp = normalize_whitespace(name_el.inner_text())
            message_jp = normalize_whitespace(txt_el.inner_text())

            # Rank like "1"
            try:
                rank = int(re.sub(r"[^\d]", "", rank_str))
            except Exception:
                continue

            # You likely map JP sign name to western sign key in another file,
            # but here is a minimal mapping by Japanese suffix strings.
            sign_key = jp_sign_to_key(sign_jp)

            # Scores are not on this list view; if you already scrape scores elsewhere,
            # keep your existing score-scrape logic here.
            scores = scrape_scores_for_sign(page, sign_key)

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


def jp_sign_to_ko(sign_jp: str) -> str:
    mapping = {
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
    return mapping.get(sign_jp, "알 수 없음")


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
        sign_jp = it["sign_jp"]
        message_jp = it["message_jp"]
        scores = it["scores"]

        try:
            ai_bundle = openai_generate_ai_bundle(
                client,
                date_kst=date_kst,
                sign_key=sign_key,
                sign_name_ja=sign_jp,
                message_jp=message_jp,
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
                "sign_jp": sign_jp,
                "sign_ko": jp_sign_to_ko(sign_jp),
                "message_jp": message_jp,
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
