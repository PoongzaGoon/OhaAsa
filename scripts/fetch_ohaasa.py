#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import time
import hashlib
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from playwright.sync_api import sync_playwright


# =========================
# Config
# =========================
SOURCE_URL = "https://www.asahi.co.jp/ohaasa/week/horoscope/"
OUT_PATH = os.path.join("public", "fortune.json")

CACHE_DIR = os.path.join("scripts", "cache")
CACHE_PATH = os.path.join(CACHE_DIR, "openai_cache.json")

OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"
OPENAI_MODEL_DEFAULT = "gpt-5-mini"

# KST (UTC+9)
KST = timezone(timedelta(hours=9))


# =========================
# Zodiac mappings
# =========================
SIGN_KEYS = [
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"
]

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
    # 간혹 한자 표기 섞이면 대비
    "牡羊座": "aries",
    "牡牛座": "taurus",
    "双子座": "gemini",
    "蟹座": "cancer",
    "獅子座": "leo",
    "乙女座": "virgo",
    "天秤座": "libra",
    "蠍座": "scorpio",
    "射手座": "sagittarius",
    "山羊座": "capricorn",
    "水瓶座": "aquarius",
    "魚座": "pisces",
}

KEY_TO_KO = {
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


# =========================
# Helpers
# =========================
def now_kst_iso() -> str:
    return datetime.now(KST).isoformat()


def today_kst_ymd() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def read_json_file(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_json_file(path: str, data: dict) -> None:
    ensure_dir(os.path.dirname(path))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clamp_int(x: Any, lo: int, hi: int, default: int) -> int:
    try:
        v = int(x)
        return max(lo, min(hi, v))
    except Exception:
        return default


def normalize_hex_color(x: Any, fallback: str = "#2F8F9D") -> str:
    if not isinstance(x, str):
        return fallback
    s = x.strip()
    if re.fullmatch(r"#([0-9a-fA-F]{6})", s):
        return s.upper()
    if re.fullmatch(r"([0-9a-fA-F]{6})", s):
        return ("#" + s).upper()
    return fallback


def sanitize_text(s: Any, fallback: str = "") -> str:
    if s is None:
        return fallback
    if not isinstance(s, str):
        try:
            s = str(s)
        except Exception:
            return fallback
    return s.strip()


# =========================
# Scraping
# =========================
def scrape_ohaasa_rankings() -> List[Dict[str, Any]]:
    """
    Scrape ranking list:
      - root: ul.oa_horoscope_list > li
      - rank: .horo_rank
      - sign: .horo_name
      - message: .horo_txt

    Returns list of items with:
      rank(int), sign_jp(str), message_jp(str), sign_key(str), sign_ko(str)
    """
    items: List[Dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=60000)

        # 네트워크/렌더 지연 대비
        page.wait_for_selector("ul.oa_horoscope_list > li", timeout=60000)

        lis = page.query_selector_all("ul.oa_horoscope_list > li")
        for idx, li in enumerate(lis):
            rank_el = li.query_selector(".horo_rank")
            name_el = li.query_selector(".horo_name")
            txt_el = li.query_selector(".horo_txt")

            rank_txt = sanitize_text(rank_el.inner_text() if rank_el else "")
            sign_jp = sanitize_text(name_el.inner_text() if name_el else "")
            message_jp = sanitize_text(txt_el.inner_text() if txt_el else "")

            # rank parse (예: "1位" "1" 등)
            m = re.search(r"(\d+)", rank_txt)
            rank = int(m.group(1)) if m else (idx + 1)

            sign_key = JP_TO_KEY.get(sign_jp)
            if not sign_key:
                # 혹시 순서가 12개 고정이라면 인덱스로 fallback
                if 0 <= idx < len(SIGN_KEYS):
                    sign_key = SIGN_KEYS[idx]
                else:
                    sign_key = "unknown"

            sign_ko = KEY_TO_KO.get(sign_key, "")

            # message_jp가 비어있으면 스킵 (하지만 전체가 비면 실패 처리)
            items.append({
                "rank": rank,
                "sign_key": sign_key,
                "sign_jp": sign_jp,
                "sign_ko": sign_ko,
                "message_jp": message_jp,
            })

        browser.close()

    # rank 기준 정렬 (보통 1~12)
    items.sort(key=lambda x: x.get("rank", 999))
    return items


# =========================
# OpenAI (Responses API)
# =========================
AI_SCHEMA: Dict[str, Any] = {
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
                "summary": {"type": "string"},
                "cards": {
                    "type": "array",
                    "minItems": 5,
                    "maxItems": 5,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["category", "score", "comment", "tip", "warning"],
                        "properties": {
                            "category": {"type": "string"},
                            "score": {"type": "integer"},
                            "comment": {"type": "string"},
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


SYSTEM_PROMPT = """너는 한국어 운세 콘텐츠 편집자이자 카피라이터다.
사용자가 볼 화면은 '오하아사 오늘의 운세'이며, 입력 데이터는 일본어 원문 운세 멘트(message_jp)와 점수(scores)다.

목표:
1) message_jp를 자연스러운 한국어(message_ko)로 번역한다. (의역 가능, 과장 금지)
2) ai.summary: 오늘 전체 톤을 1~2문장으로 요약한다.
3) ai.cards: 5개 카드를 생성한다. 각 카드는 category, score, comment, tip, warning을 포함한다.
   - category는 다음 5개 중 하나로 맞춘다: "총운", "연애운", "학업운", "금전운", "건강운"
   - score는 0~100 정수, 입력 scores의 해당 값을 우선 반영하되, 문맥이 안 맞으면 ±10 범위에서 조정 가능.
   - comment는 1~2문장, tip/warning은 짧고 실행 가능하게.
   - 금지: 혐오/차별/폭력 조장, 의료·법률 단정, 과도한 불안 조성, 성적 노골 표현.
4) ai.lucky_points: 오늘의 행운 포인트 5개를 만든다.
   - color_hex는 반드시 #RRGGBB 형식
   - number는 1~9
   - color_name/item/keyword는 짧고 구체적으로.

출력은 반드시 JSON 하나만. 다른 텍스트를 절대 출력하지 마라.
"""


def build_user_prompt(
    date_kst: str,
    sign_key: str,
    sign_ko: str,
    sign_jp: str,
    message_jp: str,
    scores: Dict[str, int],
) -> str:
    return (
        f"date_kst: {date_kst}\n"
        f"sign_key: {sign_key}\n"
        f"sign_ko: {sign_ko}\n"
        f"sign_jp: {sign_jp}\n"
        f"scores: {json.dumps(scores, ensure_ascii=False)}\n"
        f"message_jp: {message_jp}\n"
    )


def extract_output_text(resp_json: Dict[str, Any]) -> str:
    # Responses API는 환경/버전에 따라 output_text가 있거나 output 배열에 들어있을 수 있음
    if isinstance(resp_json.get("output_text"), str) and resp_json["output_text"].strip():
        return resp_json["output_text"].strip()

    out = resp_json.get("output", [])
    if isinstance(out, list):
        for item in out:
            content = item.get("content", [])
            if isinstance(content, list):
                for c in content:
                    if c.get("type") in ("output_text", "text") and isinstance(c.get("text"), str):
                        t = c["text"].strip()
                        if t:
                            return t
    return ""


def openai_generate_bundle(
    api_key: str,
    model: str,
    date_kst: str,
    sign_key: str,
    sign_ko: str,
    sign_jp: str,
    message_jp: str,
    scores: Dict[str, int],
    retry: int = 1,
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": build_user_prompt(
                            date_kst=date_kst,
                            sign_key=sign_key,
                            sign_ko=sign_ko,
                            sign_jp=sign_jp,
                            message_jp=message_jp,
                            scores=scores,
                        ),
                    }
                ],
            },
        ],
        # 여기서 name 누락하면 "Missing required parameter: text.format.name" 뜸
        "text": {
            "format": {
                "type": "json_schema",
                "name": "ohaasa_ai_bundle",
                "schema": AI_SCHEMA,
                "strict": True,
            }
        },
        "temperature": 0.7,
    }

    last_err = None
    for attempt in range(retry + 1):
        try:
            r = requests.post(OPENAI_ENDPOINT, headers=headers, json=payload, timeout=90)
            if r.status_code >= 400:
                raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text}")

            resp_json = r.json()
            text_out = extract_output_text(resp_json)
            if not text_out:
                raise RuntimeError(f"OpenAI empty output: {json.dumps(resp_json)[:500]}")

            data = json.loads(text_out)
            return data
        except Exception as e:
            last_err = e
            if attempt < retry:
                time.sleep(1.2)
                continue
            raise last_err


def validate_and_fix_ai_bundle(
    bundle: Dict[str, Any],
    scores: Dict[str, int],
) -> Dict[str, Any]:
    # 기본 구조 확보
    msg_ko = sanitize_text(bundle.get("message_ko"), "")
    ai = bundle.get("ai") if isinstance(bundle.get("ai"), dict) else {}

    summary = sanitize_text(ai.get("summary"), "")
    cards = ai.get("cards") if isinstance(ai.get("cards"), list) else []
    lucky = ai.get("lucky_points") if isinstance(ai.get("lucky_points"), dict) else {}

    # cards: 5개 고정 보정
    desired_categories = ["총운", "연애운", "학업운", "금전운", "건강운"]
    score_by_cat = {
        "총운": scores.get("total", 50),
        "연애운": scores.get("love", 50),
        "학업운": scores.get("study", 50),
        "금전운": scores.get("money", 50),
        "건강운": scores.get("health", 50),
    }

    normalized_cards: List[Dict[str, Any]] = []
    # category 기준으로 재정렬/매칭
    for cat in desired_categories:
        found = None
        for c in cards:
            if isinstance(c, dict) and sanitize_text(c.get("category")) == cat:
                found = c
                break
        if not found:
            found = {}

        normalized_cards.append({
            "category": cat,
            "score": clamp_int(found.get("score", score_by_cat[cat]), 0, 100, score_by_cat[cat]),
            "comment": sanitize_text(found.get("comment"), "오늘은 흐름을 천천히 확인해보세요."),
            "tip": sanitize_text(found.get("tip"), "작은 목표 하나만 먼저 끝내보세요."),
            "warning": sanitize_text(found.get("warning"), "무리한 확신은 피하세요."),
        })

    # lucky_points 보정
    lucky_fixed = {
        "color_name": sanitize_text(lucky.get("color_name"), "딥 틸"),
        "color_hex": normalize_hex_color(lucky.get("color_hex"), "#2F8F9D"),
        "number": clamp_int(lucky.get("number"), 1, 9, 7),
        "item": sanitize_text(lucky.get("item"), "메모장"),
        "keyword": sanitize_text(lucky.get("keyword"), "정리"),
    }

    return {
        "message_ko": msg_ko,
        "ai": {
            "summary": summary,
            "cards": normalized_cards,
            "lucky_points": lucky_fixed,
        }
    }


# =========================
# Cache
# =========================
def load_cache() -> Dict[str, Any]:
    data = read_json_file(CACHE_PATH)
    if isinstance(data, dict):
        return data
    return {}


def save_cache(cache: Dict[str, Any]) -> None:
    ensure_dir(CACHE_DIR)
    write_json_file(CACHE_PATH, cache)


def cache_key(date_kst: str, sign_key: str, message_jp: str) -> str:
    h = stable_hash(message_jp)
    return f"{date_kst}::{sign_key}::{h}"


# =========================
# Main
# =========================
def main() -> int:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("[FATAL] OPENAI_API_KEY is not set.")
        return 1

    model = os.environ.get("OPENAI_MODEL", OPENAI_MODEL_DEFAULT).strip() or OPENAI_MODEL_DEFAULT
    date_kst = today_kst_ymd()

    # 1) Scrape
    try:
        rankings_raw = scrape_ohaasa_rankings()
    except Exception:
        print("[FATAL] Scraping failed.")
        traceback.print_exc()
        return 1

    # 최소 안전장치: 12개 이상 확보 못 하면 덮어쓰기 금지
    non_empty = [x for x in rankings_raw if sanitize_text(x.get("message_jp"))]
    if len(rankings_raw) < 12 or len(non_empty) < 8:
        print(f"[FATAL] Scrape incomplete. items={len(rankings_raw)} non_empty={len(non_empty)}")
        return 1

    # 2) OpenAI enrich (cached)
    cache = load_cache()
    enriched: List[Dict[str, Any]] = []

    for item in rankings_raw[:12]:
        rank = item.get("rank")
        sign_key = sanitize_text(item.get("sign_key"))
        sign_jp = sanitize_text(item.get("sign_jp"))
        sign_ko = sanitize_text(item.get("sign_ko")) or KEY_TO_KO.get(sign_key, "")
        message_jp = sanitize_text(item.get("message_jp"))

        # 점수는 아직 placeholder 유지 (실제 크롤링 붙이기 전까지)
        scores = {"total": 50, "love": 50, "study": 50, "money": 50, "health": 50}

        ck = cache_key(date_kst, sign_key, message_jp)
        if ck in cache:
            ai_bundle = cache[ck]
        else:
            try:
                raw_bundle = openai_generate_bundle(
                    api_key=api_key,
                    model=model,
                    date_kst=date_kst,
                    sign_key=sign_key,
                    sign_ko=sign_ko,
                    sign_jp=sign_jp,
                    message_jp=message_jp,
                    scores=scores,
                    retry=1,
                )
                ai_bundle = validate_and_fix_ai_bundle(raw_bundle, scores=scores)
                cache[ck] = ai_bundle
                save_cache(cache)
            except Exception as e:
                print(f"[ERROR] OpenAI failed for {sign_key} (rank {rank}): {e}")
                traceback.print_exc()
                return 1

        enriched.append({
            "rank": rank,
            "sign_key": sign_key,
            "sign_jp": sign_jp,
            "sign_ko": sign_ko,
            "scores": scores,
            "message_jp": message_jp,
            "message_ko": ai_bundle.get("message_ko", ""),
            "ai": ai_bundle.get("ai", {}),
        })

    # 3) Write fortune.json (atomic)
    # 여기서도 12개 미만이면 쓰지 않음
    if len(enriched) < 12:
        print("[FATAL] Enriched rankings < 12. Will not overwrite fortune.json.")
        return 1

    out = {
        "source": "asahi_ohaasa",
        "source_url": SOURCE_URL,
        "date_kst": date_kst,
        "updated_at_kst": now_kst_iso(),
        "status": "ok",
        "error_message": "",
        "rankings": enriched,
    }
    write_json_file(OUT_PATH, out)
    print(f"[OK] Wrote {OUT_PATH} with {len(enriched)} rankings. model={model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
