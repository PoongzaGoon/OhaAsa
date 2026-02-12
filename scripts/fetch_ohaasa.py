#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import time
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright


# =========================
# Config
# =========================
OHAASA_URL = "https://www.asahi.co.jp/ohaasa/week/horoscope/"  # 오하아사 12별자리 페이지
OUT_JSON_PATH = Path("public/fortune.json")

CACHE_DIR = Path("scripts/cache")
CACHE_FILE = CACHE_DIR / "openai_cache.json"

OPENAI_API_URL = "https://api.openai.com/v1/responses"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

KST = timezone(timedelta(hours=9))


SIGN_KEYS = [
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"
]

# (선택) 일본어 표기 보정/정규화에 쓰고 싶으면 활용
SIGN_KO = {
    "aries": "양자리", "taurus": "황소자리", "gemini": "쌍둥이자리", "cancer": "게자리",
    "leo": "사자자리", "virgo": "처녀자리", "libra": "천칭자리", "scorpio": "전갈자리",
    "sagittarius": "사수자리", "capricorn": "염소자리", "aquarius": "물병자리", "pisces": "물고기자리",
}


# =========================
# Helpers
# =========================
def now_kst_date_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def now_kst_iso() -> str:
    return datetime.now(KST).isoformat()


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def normalize_whitespace(s: str) -> str:
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_hex_color(v: str) -> bool:
    return bool(re.fullmatch(r"#([0-9a-fA-F]{6})", v or ""))


def clamp_int(x, lo, hi, default):
    try:
        x = int(x)
    except Exception:
        return default
    return max(lo, min(hi, x))


def load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


# =========================
# Scraping (rank/name/text)
# =========================
def scrape_ohaasa_rankings() -> list[dict]:
    """
    과거 방식 유지:
    리스트 루트: ul.oa_horoscope_list > li
    랭크: .horo_rank
    별자리명: .horo_name
    멘트: .horo_txt
    """
    results: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
        )
        page = context.new_page()

        page.goto(OHAASA_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)

        # 페이지가 느릴 때 대비: 리스트가 붙을 때까지 기다림
        page.wait_for_selector("ul.oa_horoscope_list > li", timeout=60000)
        items = page.query_selector_all("ul.oa_horoscope_list > li")

        for idx, li in enumerate(items):
            rank_el = li.query_selector(".horo_rank")
            name_el = li.query_selector(".horo_name")
            txt_el = li.query_selector(".horo_txt")

            rank = normalize_whitespace(rank_el.inner_text()) if rank_el else ""
            sign_jp = normalize_whitespace(name_el.inner_text()) if name_el else ""
            message_jp = normalize_whitespace(txt_el.inner_text()) if txt_el else ""

            # rank 숫자만 뽑기 (예: "1位" → 1)
            rank_num = None
            m = re.search(r"(\d+)", rank)
            if m:
                rank_num = int(m.group(1))

            results.append({
                "rank": rank_num if rank_num is not None else (idx + 1),
                "sign_jp": sign_jp,
                "message_jp": message_jp,
                # sign_key는 프론트/엔진이 쓰는 키로, 일단 rank 순서대로 매핑(필요시 너가 정확히 매칭 로직 넣기)
                "sign_key": SIGN_KEYS[idx] if idx < len(SIGN_KEYS) else f"sign_{idx+1}",
            })

        context.close()
        browser.close()

    # rank 기준 정렬
    results.sort(key=lambda x: x.get("rank", 999))
    return results


# =========================
# OpenAI (Responses API)
# =========================
def build_json_schema() -> dict:
    """
    Responses API의 strict json_schema용 schema.
    - required 누락되면 400이 나기 쉬워서 전부 명시
    - additionalProperties false로 안정화
    """
    return {
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
                            "title": {"type": "string"},
                            "body": {"type": "string"},
                            "tip": {"type": "string"},
                            "warning": {"type": "string"},
                        },
                        "required": ["title", "body", "tip", "warning"],
                    },
                    "cards": {
                        "type": "array",
                        "minItems": 5,
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "category": {
                                    "type": "string",
                                    "enum": ["total", "love", "study", "money", "health"],
                                },
                                "score": {"type": "integer"},
                                "title": {"type": "string"},
                                "body": {"type": "string"},
                                "tip": {"type": "string"},
                                "warning": {"type": "string"},
                            },
                            "required": ["category", "score", "title", "body", "tip", "warning"],
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
                            "reasons": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["color_name", "color_hex", "number", "item", "keyword", "reasons"],
                    },
                },
                "required": ["summary", "cards", "lucky_points"],
            },
        },
        "required": ["message_ko", "ai"],
    }


SYSTEM_PROMPT = """너는 한국어 운세 콘텐츠 에디터다.
입력으로 서양 별자리명(한국어), 오하아사 원문 일본어 멘트, 점수(총운/연애/학업/금전/건강)가 주어진다.
출력은 반드시 JSON만 반환하고, 스키마를 엄격히 지켜라.

콘텐츠 규칙:
- message_ko: 오하아사 일본어 멘트를 자연스러운 한국어로 번역(의역 허용, 의미 유지, 과장 금지)
- summary: 오늘 전체 분위기 요약(짧고 명확), tip/warning은 실천 가능한 행동으로
- cards: 5개(카테고리 total/love/study/money/health 각각 1개씩), title은 짧은 헤드라인, body는 2~3문장
- 모든 tip/warning은 서로 완전히 똑같지 않게 변주해라(카드별로)
- 점수 score는 입력 점수를 그대로 사용(0~100)
- lucky_points:
  - number: 1~9
  - color_hex: #RRGGBB 형식
  - reasons: 2~4개 한국어 문자열(왜 이 행운 포인트가 어울리는지 짧게)
금지:
- 혐오/차별/폭력 선동/성적 노골 표현
- “반드시”, “확정”, “무조건” 같은 단정적 표현
"""


def openai_responses_json(model: str, user_text: str, schema: dict, max_retries: int = 1) -> dict:
    """
    Responses API 호출.
    중요: content.type은 'input_text' 여야 함. ('text' 쓰면 지금 너가 본 400이 난다)
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Set it in GitHub Secrets / env.")

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_text}],
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

    last_err = None
    for attempt in range(max_retries + 1):
        r = requests.post(OPENAI_API_URL, headers=headers, data=json.dumps(payload), timeout=90)
        if r.status_code == 200:
            data = r.json()
            # Responses API는 output 배열로 오고, 텍스트는 output_text로 집계되는 경우가 많음
            # 안전하게 output_text 우선, 없으면 output에서 찾아봄
            text_out = data.get("output_text")
            if not text_out:
                # fallback: output[] 구조에서 text 찾기
                out = data.get("output", [])
                for block in out:
                    for c in block.get("content", []):
                        if c.get("type") in ("output_text", "summary_text") and c.get("text"):
                            text_out = c["text"]
                            break
                    if text_out:
                        break

            if not text_out:
                raise RuntimeError("OpenAI response missing output_text.")

            try:
                return json.loads(text_out)
            except Exception as e:
                last_err = f"JSON parse failed: {e}"
        else:
            last_err = f"OpenAI HTTP {r.status_code}: {r.text}"

        if attempt < max_retries:
            time.sleep(1.2)

    raise RuntimeError(last_err or "OpenAI call failed.")


def postprocess_ai_bundle(bundle: dict, scores: dict) -> dict:
    """
    - cards 5개/카테고리 1개씩 강제
    - score는 입력 scores로 덮어씀(모델이 실수해도 UI 안정)
    - lucky number 1~9, color_hex 형식 강제
    """
    # message_ko
    bundle["message_ko"] = normalize_whitespace(bundle.get("message_ko", ""))

    ai = bundle.get("ai") or {}
    summary = ai.get("summary") or {}
    for k in ["title", "body", "tip", "warning"]:
        summary[k] = normalize_whitespace(summary.get(k, ""))

    cards = ai.get("cards") or []
    # 카테고리별로 하나씩 뽑기
    by_cat = {}
    for c in cards:
        cat = c.get("category")
        if cat in ["total", "love", "study", "money", "health"] and cat not in by_cat:
            by_cat[cat] = c

    # 부족하면 빈 카드 채우기
    for cat in ["total", "love", "study", "money", "health"]:
        if cat not in by_cat:
            by_cat[cat] = {
                "category": cat,
                "score": int(scores.get(cat, 50)),
                "title": "오늘의 흐름",
                "body": "흐름을 정리하고 한 가지씩 처리해보세요.",
                "tip": "작은 목표부터 시작해보세요.",
                "warning": "무리한 결정은 피하세요.",
            }

    fixed_cards = []
    for cat in ["total", "love", "study", "money", "health"]:
        c = by_cat[cat]
        c["category"] = cat
        c["score"] = clamp_int(scores.get(cat, c.get("score", 50)), 0, 100, 50)
        c["title"] = normalize_whitespace(c.get("title", ""))
        c["body"] = normalize_whitespace(c.get("body", ""))
        c["tip"] = normalize_whitespace(c.get("tip", ""))
        c["warning"] = normalize_whitespace(c.get("warning", ""))
        fixed_cards.append(c)

    lucky = ai.get("lucky_points") or {}
    lucky["color_name"] = normalize_whitespace(lucky.get("color_name", ""))
    lucky["item"] = normalize_whitespace(lucky.get("item", ""))
    lucky["keyword"] = normalize_whitespace(lucky.get("keyword", ""))
    lucky["number"] = clamp_int(lucky.get("number", 7), 1, 9, 7)
    hexv = (lucky.get("color_hex") or "").strip()
    if not is_hex_color(hexv):
        hexv = "#4A7EBB"  # 기본값
    lucky["color_hex"] = hexv

    reasons = lucky.get("reasons")
    if not isinstance(reasons, list):
        reasons = []
    reasons = [normalize_whitespace(x) for x in reasons if isinstance(x, str) and normalize_whitespace(x)]
    if len(reasons) < 2:
        reasons += ["오늘의 분위기와 잘 맞는 포인트예요.", "작은 선택에서 운이 따라줄 수 있어요."]
    lucky["reasons"] = reasons[:4]

    ai["summary"] = summary
    ai["cards"] = fixed_cards
    ai["lucky_points"] = lucky
    bundle["ai"] = ai
    return bundle


def generate_ai_for_ranking(date_kst: str, sign_key: str, sign_ko: str, message_jp: str, scores: dict, cache: dict) -> dict:
    # 캐시 키: date + sign_key + message_jp hash
    key = f"{date_kst}:{sign_key}:{sha1(message_jp)}"
    if key in cache:
        return cache[key]

    schema = build_json_schema()

    user_text = json.dumps({
        "date_kst": date_kst,
        "western_zodiac": sign_ko,
        "scores": scores,
        "source_text_ja": message_jp,
    }, ensure_ascii=False)

    bundle = openai_responses_json(OPENAI_MODEL, user_text, schema, max_retries=1)
    bundle = postprocess_ai_bundle(bundle, scores)

    cache[key] = bundle
    return bundle


# =========================
# Main
# =========================
def main():
    if not OPENAI_API_KEY:
        raise SystemExit("ERROR: OPENAI_API_KEY is missing. Set GitHub Secret OPENAI_API_KEY.")

    date_kst = now_kst_date_str()
    updated_at_kst = now_kst_iso()

    out = {
        "source": "asahi_ohaasa",
        "date_kst": date_kst,
        "updated_at_kst": updated_at_kst,
        "status": "ok",
        "error_message": "",
        "rankings": [],
    }

    try:
        rankings = scrape_ohaasa_rankings()
        if not rankings:
            raise RuntimeError("scrape returned empty rankings")
    except Exception as e:
        out["status"] = "error"
        out["error_message"] = f"스크랩 실패: {e}"
        OUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        raise

    cache = load_cache()

    # 점수는 아직 placeholder라면 여기서 유지/변경
    # TODO: 실제 상세페이지 크롤링 붙이면 여기 scores만 교체하면 됨
    def placeholder_scores():
        return {"total": 50, "love": 50, "study": 50, "money": 50, "health": 50}

    enriched = []
    for r in rankings:
        sign_key = r["sign_key"]
        sign_ko = SIGN_KO.get(sign_key, sign_key)
        message_jp = r.get("message_jp", "")
        sign_jp = r.get("sign_jp", "")

        scores = placeholder_scores()

        try:
            ai_bundle = generate_ai_for_ranking(
                date_kst=date_kst,
                sign_key=sign_key,
                sign_ko=sign_ko,
                message_jp=message_jp,
                scores=scores,
                cache=cache
            )
        except Exception as e:
            # AI 실패해도 전체 파일을 깨지지 않게 유지
            ai_bundle = {
                "message_ko": "",
                "ai": {
                    "summary": {
                        "title": "요약 생성 실패",
                        "body": "일시적으로 AI 생성에 실패했습니다.",
                        "tip": "잠시 후 다시 시도해보세요.",
                        "warning": "네트워크/키 설정을 확인하세요.",
                    },
                    "cards": [
                        {"category": "total", "score": scores["total"], "title": "총운", "body": "", "tip": "", "warning": ""},
                        {"category": "love", "score": scores["love"], "title": "연애운", "body": "", "tip": "", "warning": ""},
                        {"category": "study", "score": scores["study"], "title": "학업운", "body": "", "tip": "", "warning": ""},
                        {"category": "money", "score": scores["money"], "title": "금전운", "body": "", "tip": "", "warning": ""},
                        {"category": "health", "score": scores["health"], "title": "건강운", "body": "", "tip": "", "warning": ""},
                    ],
                    "lucky_points": {
                        "color_name": "블루",
                        "color_hex": "#4A7EBB",
                        "number": 7,
                        "item": "메모",
                        "keyword": "정리",
                        "reasons": ["기본값입니다.", "AI 실패로 대체되었습니다."],
                    },
                },
                "_error": str(e),
            }

        enriched.append({
            "rank": r.get("rank"),
            "sign_key": sign_key,
            "sign_jp": sign_jp,
            "sign_ko": sign_ko,
            "message_jp": message_jp,
            "message_ko": ai_bundle.get("message_ko", ""),
            "scores": scores,
            "ai": ai_bundle.get("ai", {}),
        })

    out["rankings"] = enriched

    # write outputs
    OUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    save_cache(cache)


if __name__ == "__main__":
    main()
