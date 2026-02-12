import datetime
import hashlib
import json
import logging
import os
import random
import re
import time
from pathlib import Path
from typing import Any

from openai import OpenAI
from playwright.sync_api import sync_playwright

SOURCE_URL = "https://www.asahi.co.jp/ohaasa/week/horoscope/"
OUTPUT_PATH = Path("public/fortune.json")
AI_CACHE_PATH = Path("scripts/cache/ai_cache.json")
TIMEOUT_MS = 30000
OPENAI_MODEL = "gpt-5-mini"
OPENAI_RETRY_COUNT = 1
REQUEST_SLEEP_SECONDS = 0.3

SIGN_MAP = {
    "おひつじ座": "양자리",
    "牡羊座": "양자리",
    "おうし座": "황소자리",
    "牡牛座": "황소자리",
    "ふたご座": "쌍둥이자리",
    "双子座": "쌍둥이자리",
    "かに座": "게자리",
    "蟹座": "게자리",
    "しし座": "사자자리",
    "獅子座": "사자자리",
    "おとめ座": "처녀자리",
    "乙女座": "처녀자리",
    "てんびん座": "천칭자리",
    "天秤座": "천칭자리",
    "さそり座": "전갈자리",
    "蠍座": "전갈자리",
    "いて座": "사수자리",
    "射手座": "사수자리",
    "やぎ座": "염소자리",
    "山羊座": "염소자리",
    "みずがめ座": "물병자리",
    "水瓶座": "물병자리",
    "うお座": "물고기자리",
    "魚座": "물고기자리",
}

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
    12: (40, 49),
}

CATEGORY_KEYS = ["total", "love", "study", "money", "health"]
CARD_KEYS = ["total", "love", "study", "money", "health"]
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def get_kst_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).astimezone(
        datetime.timezone(datetime.timedelta(hours=9))
    )


def kst_date_string() -> str:
    return get_kst_now().date().isoformat()


def kst_iso_string() -> str:
    return get_kst_now().isoformat()


def seed_for(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest, 16)


def score_from_rank(rank: int, seed_base: int) -> int:
    band = RANK_SCORE_BANDS.get(rank, (40, 60))
    rng = random.Random(seed_base)
    return rng.randint(band[0], band[1])


def clamp_score(value: int) -> int:
    return max(0, min(100, value))


def generate_scores(rank: int, date_key: str, sign_key: str) -> dict[str, int]:
    base_seed = seed_for(f"{date_key}|{sign_key}|overall")
    overall = score_from_rank(rank, base_seed)
    scores = {"overall": overall}
    for category in CATEGORY_KEYS:
        offset_seed = seed_for(f"{date_key}|{sign_key}|{category}")
        delta = random.Random(offset_seed).randint(-8, 8)
        scores[category] = clamp_score(overall + delta)
    scores["total"] = scores.get("total", overall)
    return scores


def load_cache(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def build_payload(date_key: str, rankings: list[dict], status: str = "ok", error_message: str | None = None) -> dict:
    return {
        "source": "asahi_ohaasa",
        "date_kst": date_key,
        "updated_at_kst": kst_iso_string(),
        "status": status,
        "error_message": error_message,
        "rankings": rankings,
    }


def write_payload(payload: dict) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUTPUT_PATH)


def scrape_with_playwright() -> tuple[str, list[dict]]:
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
        page.wait_for_selector("ul.oa_horoscope_list li", timeout=TIMEOUT_MS)

        date_text = ""
        try:
            date_text = page.locator(".oa_horoscope_date").inner_text(timeout=2000).strip()
        except Exception:
            date_text = ""

        items = page.locator("ul.oa_horoscope_list li")
        count = items.count()
        results = []

        for i in range(count):
            li = items.nth(i)
            rank_raw = li.locator(".horo_rank").inner_text().strip()
            rank = int(re.sub(r"\D+", "", rank_raw) or "0")
            sign_jp = li.locator(".horo_name").inner_text().strip()
            msg_jp = li.locator(".horo_txt").inner_text().strip()

            if rank and sign_jp:
                results.append({"rank": rank, "sign_jp": sign_jp, "message_jp": msg_jp})

        context.close()
        browser.close()
        return date_text, results


def get_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text_value = getattr(content, "text", None)
            if text_value:
                chunks.append(text_value)
    return "\n".join(chunks).strip()


def validate_ai_bundle(data: dict[str, Any]) -> None:
    if not isinstance(data.get("message_ko"), str) or not data["message_ko"].strip():
        raise ValueError("message_ko missing")

    ai = data.get("ai")
    if not isinstance(ai, dict):
        raise ValueError("ai missing")

    for key in ["summary", "tip", "warning"]:
        if not isinstance(ai.get(key), str) or not ai[key].strip():
            raise ValueError(f"ai.{key} missing")

    lucky = ai.get("lucky")
    if not isinstance(lucky, dict):
        raise ValueError("ai.lucky missing")

    if not isinstance(lucky.get("color_name_ko"), str) or not lucky["color_name_ko"].strip():
        raise ValueError("ai.lucky.color_name_ko missing")
    if not isinstance(lucky.get("color_hex"), str) or not re.match(r"^#[0-9A-Fa-f]{6}$", lucky["color_hex"]):
        raise ValueError("ai.lucky.color_hex invalid")
    if not isinstance(lucky.get("number"), int) or lucky["number"] < 0 or lucky["number"] > 9:
        raise ValueError("ai.lucky.number invalid")
    for key in ["item", "keyword"]:
        if not isinstance(lucky.get(key), str) or not lucky[key].strip():
            raise ValueError(f"ai.lucky.{key} missing")

    cards = ai.get("cards")
    if not isinstance(cards, dict):
        raise ValueError("ai.cards missing")
    for card_key in CARD_KEYS:
        card = cards.get(card_key)
        if not isinstance(card, dict):
            raise ValueError(f"ai.cards.{card_key} missing")
        for field in ["title", "body", "tip", "warning"]:
            if not isinstance(card.get(field), str) or not card[field].strip():
                raise ValueError(f"ai.cards.{card_key}.{field} missing")


def build_prompt_payload(date_key: str, sign_jp: str, sign_ko: str, scores: dict[str, int], message_jp: str) -> str:
    payload = {
        "date_kst": date_key,
        "sign_jp": sign_jp,
        "sign_ko": sign_ko,
        "scores": scores,
        "message_jp": message_jp,
        "seed_hint": f"{date_key}|{sign_jp}|ohaasa-ai-v1",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def generate_ai_bundle(
    client: OpenAI,
    date_key: str,
    sign_jp: str,
    sign_ko: str,
    scores: dict[str, int],
    message_jp: str,
) -> dict[str, Any]:
    prompt_input = build_prompt_payload(date_key, sign_jp, sign_ko, scores, message_jp)
    system_prompt = (
        "You are a Korean horoscope localization assistant. "
        "Return JSON only. Do not include markdown. "
        "Use safe, non-deterministic but calm tone. Avoid medical/financial certainty claims. "
        "Keep constraints: message_ko 1-2 sentences, ai.summary/tip/warning 1 sentence each, "
        "cards.*.body 2-3 sentences, cards.*.tip and cards.*.warning 1 sentence each. "
        "lucky.item 2-6 Korean words, lucky.keyword 1-4 Korean words, lucky.number integer 0-9."
    )
    json_schema = {
        "type": "object",
        "properties": {
            "message_ko": {"type": "string"},
            "ai": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "tip": {"type": "string"},
                    "warning": {"type": "string"},
                    "lucky": {
                        "type": "object",
                        "properties": {
                            "color_name_ko": {"type": "string"},
                            "color_hex": {"type": "string"},
                            "number": {"type": "integer"},
                            "item": {"type": "string"},
                            "keyword": {"type": "string"},
                        },
                        "required": ["color_name_ko", "color_hex", "number", "item", "keyword"],
                        "additionalProperties": False,
                    },
                    "cards": {
                        "type": "object",
                        "properties": {
                            k: {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "body": {"type": "string"},
                                    "tip": {"type": "string"},
                                    "warning": {"type": "string"},
                                },
                                "required": ["title", "body", "tip", "warning"],
                                "additionalProperties": False,
                            }
                            for k in CARD_KEYS
                        },
                        "required": CARD_KEYS,
                        "additionalProperties": False,
                    },
                },
                "required": ["summary", "tip", "warning", "lucky", "cards"],
                "additionalProperties": False,
            },
        },
        "required": ["message_ko", "ai"],
        "additionalProperties": False,
    }

    last_error: Exception | None = None
    for attempt in range(OPENAI_RETRY_COUNT + 1):
        try:
            response = client.responses.create(
                model=OPENAI_MODEL,
                input=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            "Generate output with this exact JSON schema and values in Korean.\n"
                            f"schema={json.dumps(json_schema, ensure_ascii=False)}\n"
                            f"input={prompt_input}"
                        ),
                    },
                ],
            )
            raw_text = get_response_text(response)
            parsed = json.loads(raw_text)
            validate_ai_bundle(parsed)
            return parsed
        except Exception as error:
            last_error = error
            logging.warning("OpenAI parse/generation failed (%s/%s): %s", attempt + 1, OPENAI_RETRY_COUNT + 1, error)
            if attempt < OPENAI_RETRY_COUNT:
                time.sleep(0.4)

    raise RuntimeError(f"OpenAI generation failed: {last_error}")


def main() -> None:
    date_key = kst_date_string()
    ai_cache = load_cache(AI_CACHE_PATH)

    try:
        _, parsed = scrape_with_playwright()
    except Exception as error:
        logging.error("Scraping failed: %s", error)
        write_payload(build_payload(date_key, [], status="error", error_message=str(error)))
        return

    if len(parsed) < 12:
        msg = f"Rankings incomplete: found {len(parsed)} items"
        logging.error(msg)
        write_payload(build_payload(date_key, [], status="error", error_message=msg))
        return

    openai_api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=openai_api_key) if openai_api_key else None
    if not client:
        logging.warning("OPENAI_API_KEY missing. ai fields will be null.")

    rankings: list[dict[str, Any]] = []
    ai_failed_items: list[str] = []

    parsed.sort(key=lambda x: x["rank"])
    for item in parsed:
        sign_jp = item["sign_jp"]
        sign_ko = SIGN_MAP.get(sign_jp) or SIGN_MAP.get(sign_jp.replace(" ", "")) or ""
        scores = generate_scores(item["rank"], date_key, sign_jp)

        cache_key = f"{date_key}|{sign_jp}"
        ai_bundle = ai_cache.get(cache_key)

        if not ai_bundle and client:
            try:
                ai_bundle = generate_ai_bundle(
                    client=client,
                    date_key=date_key,
                    sign_jp=sign_jp,
                    sign_ko=sign_ko,
                    scores=scores,
                    message_jp=item["message_jp"],
                )
                ai_cache[cache_key] = ai_bundle
            except Exception as error:
                ai_failed_items.append(f"{item['rank']}:{sign_jp}")
                logging.warning("AI bundle failed for %s: %s", sign_jp, error)
            finally:
                time.sleep(REQUEST_SLEEP_SECONDS)

        if ai_bundle:
            try:
                validate_ai_bundle(ai_bundle)
            except Exception as error:
                logging.warning("Cached AI bundle invalid for %s: %s", sign_jp, error)
                ai_bundle = None
                ai_failed_items.append(f"{item['rank']}:{sign_jp}")

        rankings.append(
            {
                "rank": item["rank"],
                "sign_jp": sign_jp,
                "sign_ko": sign_ko,
                "message_jp": item["message_jp"],
                "message_ko": ai_bundle.get("message_ko") if ai_bundle else None,
                "scores": {
                    "overall": scores["overall"],
                    "total": scores["total"],
                    "love": scores["love"],
                    "study": scores["study"],
                    "money": scores["money"],
                    "health": scores["health"],
                },
                "ai": ai_bundle.get("ai") if ai_bundle else None,
            }
        )

    status = "ok"
    error_message = None
    if ai_failed_items or not client:
        status = "partial"
        reason = "OPENAI_API_KEY missing" if not client else f"AI generation failed for: {', '.join(ai_failed_items)}"
        error_message = reason

    write_payload(build_payload(date_key, rankings, status=status, error_message=error_message))
    save_cache(AI_CACHE_PATH, ai_cache)
    logging.info("Updated %s with %d rankings", OUTPUT_PATH, len(rankings))


if __name__ == "__main__":
    main()
