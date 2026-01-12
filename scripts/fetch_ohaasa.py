import datetime
import hashlib
import json
import logging
import os
import random
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.asahi.co.jp/ohaasa/week/horoscope/"
OUTPUT_PATH = Path("public/fortune.json")
CACHE_PATH = Path("scripts/cache/translate_cache.json")
TIMEOUT = 20

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
    return datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=9)))


def kst_date_string():
    return get_kst_now().date().isoformat()


def kst_iso_string():
    return get_kst_now().isoformat()


def load_cache():
    if CACHE_PATH.exists():
        try:
            with CACHE_PATH.open("r", encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=2)


def fetch_html():
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; OhaAsaBot/1.0; +https://github.com)",
        "Accept-Language": "ja,en;q=0.8,ko;q=0.7",
    }
    response = requests.get(SOURCE_URL, headers=headers, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text


def seed_for(value):
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest, 16)


def score_from_rank(rank, seed_base):
    band = RANK_SCORE_BANDS.get(rank, (40, 60))
    rng = random.Random(seed_base)
    return rng.randint(band[0], band[1])


def clamp_score(value):
    return max(0, min(100, value))


def generate_scores(rank, date_key, sign_key):
    base_seed = seed_for(f"{date_key}|{sign_key}|overall")
    overall = score_from_rank(rank, base_seed)
    scores = {"overall": overall}
    for category in CATEGORY_KEYS:
        offset_seed = seed_for(f"{date_key}|{sign_key}|{category}")
        delta = random.Random(offset_seed).randint(-8, 8)
        scores[category] = clamp_score(overall + delta)
    scores["total"] = scores["total"] if "total" in scores else overall
    return scores


def parse_rank_from_text(text: str):
    if not text:
        return None

    m = re.search(r"(?:第\s*)?(1[0-2]|[1-9])\s*位", text)
    if m:
        return int(m.group(1))

    circled = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"
    for i, ch in enumerate(circled, start=1):
        if ch in text:
            return i

    m = re.search(r"\b(1[0-2]|[1-9])\b", text)
    if m:
        return int(m.group(1))

    return None



def parse_sign(text):
    match = re.search(r"([\wぁ-んァ-ン一-龠]+座)", text)
    if match:
        return match.group(1)
    return None


def extract_message(tag):

    candidates = []

    for p in tag.select("p"):
        t = p.get_text(" ", strip=True)
        if t:
            candidates.append(t)

    if not candidates:
        t = tag.get_text(" ", strip=True)
        if t:
            candidates.append(t)

    candidates = [c for c in candidates if len(c) >= 8]
    if not candidates:
        return None
    return max(candidates, key=len)



def parse_item(tag, rank_override=None):
    text = tag.get_text(" ", strip=True)

    rank = rank_override if rank_override is not None else parse_rank_from_text(text)

    sign = None
    for img in tag.select("img[alt]"):
        alt = img.get("alt", "").strip()
        if alt:
            sign = parse_sign(alt)
            if sign:
                break

    if not sign:
        sign = parse_sign(text)

    message = extract_message(tag)
    if message:
        message = re.sub(r"\s+", " ", message).strip()


    if not message:
        message = text

    if not sign:
        return None

    return {
        "rank": rank,
        "sign_jp": sign,
        "message_jp": message,
    }



def parse_rankings(html):
    soup = BeautifulSoup(html, "html.parser")

    heading = soup.find(string=re.compile(r"今日の星占いランキング"))
    root = heading.find_parent() if heading else soup

    blocks = []
    for tag in root.find_all_next(["li", "article", "div"], limit=2000):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        if "座" not in text:
            continue

        sign = parse_sign(text)
        if not sign:
            continue

        if len(text) > 500:
            continue

        blocks.append(tag)

        if len(blocks) >= 60:
            break

    seen = set()
    items = []
    for tag in blocks:
        text = tag.get_text(" ", strip=True)
        sign = parse_sign(text)
        if not sign or sign in seen:
            continue
        seen.add(sign)
        items.append(tag)
        if len(items) >= 12:
            break

    if len(items) < 12:
        raise ValueError(f"Rankings incomplete: found {len(items)} items")

    parsed = []
    for i, item_tag in enumerate(items, start=1):
        item = parse_item(item_tag, rank_override=i)
        if item:
            parsed.append(item)

    if len(parsed) < 12:
        raise ValueError(f"Rankings incomplete after parse: found {len(parsed)} items")

    return parsed




def translate_text(text, cache, date_key):
    if not text:
        return None
    cache_key = f"{date_key}|{text}"
    if cache_key in cache:
        return cache[cache_key]
    client_id = os.getenv("PAPAGO_CLIENT_ID")
    client_secret = os.getenv("PAPAGO_CLIENT_SECRET")
    if not client_id or not client_secret:
        logging.warning("Papago credentials are missing")
        return None
    url = "https://openapi.naver.com/v1/papago/n2mt"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    data = {"source": "ja", "target": "ko", "text": text}
    try:
        response = requests.post(url, headers=headers, data=data, timeout=TIMEOUT)
        response.raise_for_status()
        translated = response.json()["message"]["result"]["translatedText"]
    except Exception as error:
        logging.warning("Papago translation failed: %s", error)
        return None
    cache[cache_key] = translated
    return translated


def build_payload(date_key, rankings, status="ok", error_message=None):
    return {
        "source": "asahi_ohaasa",
        "date_kst": date_key,
        "updated_at_kst": kst_iso_string(),
        "status": status,
        "error_message": error_message,
        "rankings": rankings,
    }


def load_previous_payload():
    if not OUTPUT_PATH.exists():
        return None
    try:
        with OUTPUT_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return None


def write_payload(payload):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = OUTPUT_PATH.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    temp_path.replace(OUTPUT_PATH)


def main():
    date_key = kst_date_string()
    cache = load_cache()
    try:
        html = fetch_html()
        parsed = parse_rankings(html)
    except Exception as error:
        logging.error("Scraping failed: %s", error)
        previous = load_previous_payload()
        if previous:
            previous["status"] = "error"
            previous["error_message"] = str(error)
            previous["updated_at_kst"] = kst_iso_string()
            write_payload(previous)
            return
        payload = build_payload(date_key, [], status="error", error_message=str(error))
        write_payload(payload)
        return

    rankings = []
    translation_failed = False
    for item in parsed:
        sign_jp = item.get("sign_jp") or ""
        sign_ko = SIGN_MAP.get(sign_jp)
        if not sign_ko:
            sign_ko = SIGN_MAP.get(sign_jp.replace(" ", ""))
        scores = generate_scores(item["rank"], date_key, sign_jp)
        message_ko = translate_text(item.get("message_jp", ""), cache, date_key)
        if message_ko is None:
            translation_failed = True
        rankings.append(
            {
                "rank": item["rank"],
                "sign_jp": sign_jp,
                "sign_ko": sign_ko or "",
                "message_jp": item.get("message_jp", ""),
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

    rankings.sort(key=lambda item: item["rank"])
    status = "partial" if translation_failed else "ok"
    error_message = "Papago translation failed" if translation_failed else None
    payload = build_payload(date_key, rankings, status=status, error_message=error_message)
    write_payload(payload)
    save_cache(cache)


if __name__ == "__main__":
    main()
