import datetime
import hashlib
import json
import logging
import os
import random
import re
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

SOURCE_URL = "https://www.asahi.co.jp/ohaasa/week/horoscope/"
OUTPUT_PATH = Path("public/fortune.json")
CACHE_PATH = Path("scripts/cache/translate_cache.json")
TIMEOUT_MS = 30000

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
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def get_kst_now():
    return datetime.datetime.now(datetime.timezone.utc).astimezone(
        datetime.timezone(datetime.timedelta(hours=9))
    )


def kst_date_string():
    return get_kst_now().date().isoformat()


def kst_iso_string():
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


def generate_scores(rank: int, date_key: str, sign_key: str) -> dict:
    base_seed = seed_for(f"{date_key}|{sign_key}|overall")
    overall = score_from_rank(rank, base_seed)
    scores = {"overall": overall}
    for category in CATEGORY_KEYS:
        offset_seed = seed_for(f"{date_key}|{sign_key}|{category}")
        delta = random.Random(offset_seed).randint(-8, 8)
        scores[category] = clamp_score(overall + delta)
    scores["total"] = scores.get("total", overall)
    return scores


def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def translate_text(text: str, cache: dict, date_key: str) -> str | None:
    if not text:
        return None
    cache_key = f"{date_key}|{text}"
    if cache_key in cache:
        return cache[cache_key]

    client_id = os.getenv("PAPAGO_CLIENT_ID")
    client_secret = os.getenv("PAPAGO_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    url = "https://openapi.naver.com/v1/papago/n2mt"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    data = {"source": "ja", "target": "ko", "text": text}
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=20)
        resp.raise_for_status()
        translated = resp.json()["message"]["result"]["translatedText"]
    except Exception as e:
        logging.warning("Papago translation failed: %s", e)
        return None

    cache[cache_key] = translated
    return translated


def build_payload(date_key: str, rankings: list, status="ok", error_message=None) -> dict:
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

        # 랭킹 리스트가 렌더링될 때까지 대기
        page.wait_for_selector("ul.oa_horoscope_list li", timeout=TIMEOUT_MS)

        # 날짜 표시(있으면)
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

            # rank: <span class="horo_rank">1</span>
            rank_raw = li.locator(".horo_rank").inner_text().strip()
            rank = int(re.sub(r"\D+", "", rank_raw) or "0")

            # sign: <span class="horo_name">ふたご座</span>
            sign_jp = li.locator(".horo_name").inner_text().strip()

            # message: <dd class="horo_txt">...</dd>
            msg_jp = li.locator(".horo_txt").inner_text().strip()

            if rank and sign_jp:
                results.append({"rank": rank, "sign_jp": sign_jp, "message_jp": msg_jp})

        context.close()
        browser.close()
        return date_text, results


def main():
    date_key = kst_date_string()
    cache = load_cache()

    try:
        _, parsed = scrape_with_playwright()
    except Exception as e:
        logging.error("Scraping failed: %s", e)
        write_payload(build_payload(date_key, [], status="error", error_message=str(e)))
        return

    if len(parsed) < 12:
        msg = f"Rankings incomplete: found {len(parsed)} items"
        logging.error(msg)
        write_payload(build_payload(date_key, [], status="error", error_message=msg))
        return

    rankings = []
    translation_failed = False

    parsed.sort(key=lambda x: x["rank"])
    for item in parsed:
        sign_jp = item["sign_jp"]
        sign_ko = SIGN_MAP.get(sign_jp) or SIGN_MAP.get(sign_jp.replace(" ", "")) or ""
        scores = generate_scores(item["rank"], date_key, sign_jp)

        message_ko = translate_text(item["message_jp"], cache, date_key)
        if message_ko is None and (os.getenv("PAPAGO_CLIENT_ID") and os.getenv("PAPAGO_CLIENT_SECRET")):
            translation_failed = True

        rankings.append(
            {
                "rank": item["rank"],
                "sign_jp": sign_jp,
                "sign_ko": sign_ko,
                "message_jp": item["message_jp"],
                "message_ko": message_ko,
                "scores": {
                    "overall": scores["overall"],
                    "total": scores["total"],
                    "love": scores["love"],
                    "study": scores["study"],
                    "money": scores["money"],
                    "health": scores["health"],
                },
            }
        )

    status = "partial" if translation_failed else "ok"
    error_message = "Papago translation failed" if translation_failed else None

    write_payload(build_payload(date_key, rankings, status=status, error_message=error_message))
    save_cache(cache)
    logging.info("Updated %s with %d rankings", OUTPUT_PATH, len(rankings))


if __name__ == "__main__":
    main()
