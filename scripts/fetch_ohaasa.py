# scripts/fetch_ohaasa.py
import os
import re
import json
import time
import hashlib
import datetime
from typing import Any, Dict, List, Optional

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# -----------------------------
# Config
# -----------------------------
OHAASA_URL = "https://www.asahi.com/uranai/12seiza/"  # (필요하면 기존에 쓰던 URL로 되돌려도 됨)
OUT_PATH = "public/fortune.json"

CACHE_DIR = "scripts/cache"
OPENAI_CACHE_PATH = os.path.join(CACHE_DIR, "openai_cache.json")

# env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

# -----------------------------
# Zodiac mappings
# (site에서 긁히는 표기가 조금 달라도 매칭되게 느슨하게 처리)
# -----------------------------
SIGN_ORDER = [
    ("aries", "おひつじ座", "양자리"),
    ("taurus", "おうし座", "황소자리"),
    ("gemini", "ふたご座", "쌍둥이자리"),
    ("cancer", "かに座", "게자리"),
    ("leo", "しし座", "사자자리"),
    ("virgo", "おとめ座", "처녀자리"),
    ("libra", "てんびん座", "천칭자리"),
    ("scorpio", "さそり座", "전갈자리"),
    ("sagittarius", "いて座", "사수자리"),
    ("capricorn", "やぎ座", "염소자리"),
    ("aquarius", "みずがめ座", "물병자리"),
    ("pisces", "うお座", "물고기자리"),
]

JP_TO_KEY = {jp: key for (key, jp, ko) in SIGN_ORDER}
KEY_TO_KO = {key: ko for (key, jp, ko) in SIGN_ORDER}

# -----------------------------
# Helpers
# -----------------------------
def now_kst() -> datetime.datetime:
    # KST = UTC+9
    return datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).astimezone(
        datetime.timezone(datetime.timedelta(hours=9))
    )

def kst_date_str() -> str:
    return now_kst().date().isoformat()

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def safe_write_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def load_json(path: str) -> Any:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def normalize_sign_jp(raw: str) -> str:
    # 공백/줄바꿈 제거
    s = re.sub(r"\s+", "", raw or "")
    return s

def sign_key_from_jp(sign_jp: str) -> Optional[str]:
    s = normalize_sign_jp(sign_jp)
    # 완전 일치 우선
    if s in JP_TO_KEY:
        return JP_TO_KEY[s]
    # 부분 매칭(표기 흔들릴 때 대비)
    for (key, jp, _ko) in SIGN_ORDER:
        if jp in s or s in jp:
            return key
    return None

def clamp_int(v: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(v)
        return max(lo, min(hi, n))
    except Exception:
        return default

def normalize_hex(color_hex: str, fallback: str = "#3FA7D6") -> str:
    if not isinstance(color_hex, str):
        return fallback
    s = color_hex.strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", s):
        return s.upper()
    # "#RGB" 형태면 확장
    m = re.fullmatch(r"#[0-9A-Fa-f]{3}", s)
    if m:
        r, g, b = s[1], s[2], s[3]
        return f"#{r}{r}{g}{g}{b}{b}".upper()
    return fallback

# -----------------------------
# Scraping (과거 안정 버전 스타일로 최대한 유지)
# -----------------------------
def scrape_ohaasa_rankings() -> List[Dict[str, Any]]:
    """
    리스트 루트: ul.oa_horoscope_list > li
    랭크: .horo_rank
    별자리명: .horo_name
    멘트: .horo_txt
    """
    results: List[Dict[str, Any]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ja-JP",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
        )
        # 일부 사이트는 언어/헤더 민감
        context.set_extra_http_headers(
            {
                "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.7,en;q=0.6",
            }
        )

        page = context.new_page()
        page.set_default_timeout(45000)

        # networkidle은 종종 끝까지 안 떨어져서 실패 원인이 됨 → domcontentloaded + selector 대기
        page.goto(OHAASA_URL, wait_until="domcontentloaded")

        # 리스트가 뜰 때까지 대기
        page.wait_for_selector("ul.oa_horoscope_list > li", timeout=45000)

        items = page.query_selector_all("ul.oa_horoscope_list > li")
        for li in items:
            rank_el = li.query_selector(".horo_rank")
            name_el = li.query_selector(".horo_name")
            txt_el = li.query_selector(".horo_txt")

            rank_txt = (rank_el.inner_text().strip() if rank_el else "").strip()
            sign_jp = (name_el.inner_text().strip() if name_el else "").strip()
            message_jp = (txt_el.inner_text().strip() if txt_el else "").strip()

            # rank 파싱(예: "1位" 같은 경우 숫자만)
            rank_num = None
            m = re.search(r"(\d+)", rank_txt)
            if m:
                rank_num = int(m.group(1))

            if not sign_jp or not message_jp or rank_num is None:
                continue

            key = sign_key_from_jp(sign_jp)
            if not key:
                # 못 맞추면 그래도 저장(디버깅용)
                key = "unknown"

            results.append(
                {
                    "rank": rank_num,
                    "sign_key": key,
                    "sign_jp": sign_jp,
                    "message_jp": message_jp,
                }
            )

        context.close()
        browser.close()

    # rank 기준 정렬
    results.sort(key=lambda x: x.get("rank", 999))
    return results

def scrape_scores_for_sign(_page, _sign_key: str) -> Dict[str, int]:
    # TODO: 상세 페이지 점수 크롤링 붙이기 전까지는 placeholder 유지
    return {"total": 50, "love": 50, "study": 50, "money": 50, "health": 50}

# -----------------------------
# OpenAI (Responses API)
# -----------------------------
def build_response_schema() -> Dict[str, Any]:
    """
    strict JSON schema:
    - 각 object 레벨에서 required는 properties의 모든 키를 포함해야 함.
    - 불필요한 optional 필드는 넣지 않는 게 안정적.
    """
    card_item = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "category": {"type": "string", "enum": ["총운", "연애운", "학업운", "금전운", "건강운"]},
            "tone": {"type": "string", "enum": ["상승", "안정", "하락"]},
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "comment": {"type": "string"},
            "tip": {"type": "string"},
            "warning": {"type": "string"},
        },
        "required": ["category", "tone", "score", "comment", "tip", "warning"],
    }

    schema = {
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
                            "body": {"type": "string"},
                            "tip": {"type": "string"},
                            "warning": {"type": "string"},
                        },
                        "required": ["headline", "body", "tip", "warning"],
                    },
                    "cards": {
                        "type": "array",
                        "minItems": 5,
                        "maxItems": 5,
                        "items": card_item,
                    },
                    "lucky_points": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "color_name": {"type": "string"},
                            "color_hex": {"type": "string", "pattern": r"^#[0-9A-Fa-f]{6}$"},
                            "number": {"type": "integer", "minimum": 1, "maximum": 9},
                            "item": {"type": "string"},
                            "keyword": {"type": "string"},
                        },
                        "required": ["color_name", "color_hex", "number", "item", "keyword"],
                    },
                },
                "required": ["summary", "cards", "lucky_points"],
            },
        },
        "required": ["message_ko", "ai"],
    }
    return schema

def extract_output_text(resp_json: Dict[str, Any]) -> str:
    # Responses API output 파싱(유연하게)
    if isinstance(resp_json, dict):
        if "output_text" in resp_json and isinstance(resp_json["output_text"], str):
            return resp_json["output_text"]
        out = resp_json.get("output")
        if isinstance(out, list):
            for item in out:
                content = item.get("content") if isinstance(item, dict) else None
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict):
                            # 보통 {"type":"output_text","text":"..."} 형태
                            if c.get("type") in ("output_text", "text") and isinstance(c.get("text"), str):
                                return c["text"]
    return ""

def openai_generate_bundle(
    *,
    date_kst: str,
    sign_key: str,
    sign_ko: str,
    message_jp: str,
    scores: Dict[str, int],
    zodiac_color_hex: str = "#3FA7D6",
) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    schema = build_response_schema()

    system = (
        "너는 한국어 운세 콘텐츠를 만드는 전문 에디터다.\n"
        "- 사용자가 보는 UI는 카드형(총운/연애운/학업운/금전운/건강운) 5개다.\n"
        "- 번역: message_jp를 자연스러운 한국어로 번역하되 과장하지 말고 간결하게.\n"
        "- 카드: 각 카드 comment는 1~2문장, tip/warning은 각 1문장.\n"
        "- 표현 금지: 선정적/차별적/혐오/폭력 조장.\n"
        "- 점수는 입력 scores를 참고하되 0~100 정수.\n"
        "- lucky_points는 모바일 UI에 들어갈 짧은 단어로.\n"
        "- 반드시 JSON만 출력.\n"
    )

    user = (
        f"[KST 날짜] {date_kst}\n"
        f"[서양 별자리] {sign_ko} ({sign_key})\n"
        f"[별자리 고유색 HEX] {zodiac_color_hex}\n"
        f"[오하아사 원문 message_jp]\n{message_jp}\n\n"
        f"[점수(scores)] {json.dumps(scores, ensure_ascii=False)}\n\n"
        "요구 결과(JSON):\n"
        "- message_ko: 원문을 자연스러운 한국어로 번역\n"
        "- ai.summary: headline/body/tip/warning\n"
        "- ai.cards: 5개(총운/연애운/학업운/금전운/건강운) category, tone(상승/안정/하락), score, comment, tip, warning\n"
        "- ai.lucky_points: color_name,color_hex,number(1~9),item,keyword\n"
    )

    payload = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "system", "content": [{"type": "text", "text": system}]},
            {"role": "user", "content": [{"type": "text", "text": user}]},
        ],
        # 핵심: text.format.name 필수 + strict schema
        "text": {
            "format": {
                "type": "json_schema",
                "name": "ohaasa_ai_bundle",
                "schema": schema,
                "strict": True,
            }
        },
    }

    url = f"{OPENAI_BASE_URL}/responses"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text[:4000]}")

    resp_json = r.json()
    out_text = extract_output_text(resp_json)
    if not out_text:
        raise RuntimeError("OpenAI response has no output text")

    try:
        data = json.loads(out_text)
    except Exception:
        # JSON 파싱 실패 시 1회 재시도(응답에 잡텍스트 섞일 때 대비)
        r2 = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        if r2.status_code >= 400:
            raise RuntimeError(f"OpenAI retry HTTP {r2.status_code}: {r2.text[:4000]}")
        resp2 = r2.json()
        out2 = extract_output_text(resp2)
        data = json.loads(out2)

    # --- post-normalize (최소 보정) ---
    # lucky_points 보정
    lp = data["ai"]["lucky_points"]
    lp["color_hex"] = normalize_hex(lp.get("color_hex", "#3FA7D6"))
    lp["number"] = clamp_int(lp.get("number", 7), 1, 9, 7)

    # cards 5개 보정 + category 중복/누락 보정
    cards = data["ai"]["cards"]
    # 혹시 순서 꼬이면 category 기준 정렬
    order = {"총운": 0, "연애운": 1, "학업운": 2, "금전운": 3, "건강운": 4}
    cards.sort(key=lambda c: order.get(c.get("category", ""), 999))
    data["ai"]["cards"] = cards[:5]

    return data

# -----------------------------
# Cache
# -----------------------------
def load_cache() -> Dict[str, Any]:
    ensure_dir(CACHE_DIR)
    try:
        return load_json(OPENAI_CACHE_PATH) or {}
    except Exception:
        return {}

def save_cache(cache: Dict[str, Any]) -> None:
    ensure_dir(CACHE_DIR)
    safe_write_json(OPENAI_CACHE_PATH, cache)

def cache_key(date_kst: str, sign_key: str, message_jp: str) -> str:
    return f"{date_kst}:{sign_key}:{sha1(message_jp)}"

# -----------------------------
# Main
# -----------------------------
def main() -> int:
    date_kst = kst_date_str()
    updated_at_kst = now_kst().isoformat()

    out: Dict[str, Any] = {
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

        cache = load_cache()

        enriched: List[Dict[str, Any]] = []
        for row in rankings:
            sign_key = row.get("sign_key", "unknown")
            sign_jp = row.get("sign_jp", "")
            message_jp = row.get("message_jp", "")

            sign_ko = KEY_TO_KO.get(sign_key, "알수없음")

            # scores: 아직 placeholder이지만 스키마/프론트 호환 위해 유지
            scores = {"total": 50, "love": 50, "study": 50, "money": 50, "health": 50}

            ck = cache_key(date_kst, sign_key, message_jp)
            if ck in cache:
                ai_pack = cache[ck]
            else:
                ai_pack = openai_generate_bundle(
                    date_kst=date_kst,
                    sign_key=sign_key,
                    sign_ko=sign_ko,
                    message_jp=message_jp,
                    scores=scores,
                    zodiac_color_hex="#3FA7D6",
                )
                cache[ck] = ai_pack
                save_cache(cache)
                # API 호출 과속 방지(살짝 텀)
                time.sleep(0.2)

            enriched.append(
                {
                    "rank": row["rank"],
                    "sign_key": sign_key,
                    "sign_jp": sign_jp,
                    "sign_ko": sign_ko,
                    "message_jp": message_jp,               # 원문 유지
                    "message_ko": ai_pack.get("message_ko", ""),  # 번역본
                    "scores": scores,
                    "ai": ai_pack.get("ai", {}),
                }
            )

        out["rankings"] = enriched

    except Exception as e:
        out["status"] = "error"
        out["error_message"] = f"스크랩 실패: {str(e)}"

        # 실패 시라도 최소한 깨진 파일 커밋되는 걸 막고 싶으면 여기서 exit(1)로 바꿔도 됨
        # 지금은 네 요구가 "json 생성은 하되 정상데이터"가 목표라서,
        # CI에서 실패를 감지하게끔 non-zero로 종료하는게 더 안전함.
        safe_write_json(OUT_PATH, out)
        return 1

    safe_write_json(OUT_PATH, out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
