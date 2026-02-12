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
CATEGORY_TITLE = {
    "total": "총운",
    "love": "연애운",
    "study": "학업운",
    "money": "금전운",
    "health": "건강운",
}
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

SYSTEM_PROMPT = """너는 한국어 운세 콘텐츠를 생성하는 시니어 서비스용 AI이다.

다음 입력 JSON은
- 날짜
- 서양 별자리
- 동양 띠
- 각 영역 점수(총운, 연애운, 학업운, 금전운, 건강운)
- 일본 원문 운세(있을 수도 있음)

이다.

너의 목표는
프론트엔드 카드 UI에 바로 출력 가능한
\"오늘의 운세 콘텐츠\"를 구조화된 JSON으로 생성하는 것이다.

중요 규칙
- 모든 출력은 반드시 한국어
- 반복되는 문장 패턴을 피할 것
- 영역별 톤을 분리할 것
- 점수에 따라 뉘앙스를 자연스럽게 조절할 것
- 일본 원문이 주어질 경우, 직역하지 말고 의미를 해석하여 반영할 것
- 과장된 미래 예언, 단정적 표현, 의료·투자 조언은 금지
- 오늘 하루에 적용 가능한 현실적인 조언만 작성

카드 영역 작성 가이드
1) main: 카드 상단 한 줄 요약, 25자 내외
2) detail: 오늘 하루 흐름을 설명, 행동 맥락 포함
3) tip: 지금 바로 실천 가능한 행동 1가지
4) caution: 오늘 특히 피하면 좋은 행동 1가지

점수 해석 기준
- 90~100: 매우 긍정적, 단 방심 경고 1회 포함
- 70~89: 안정적 + 기회 강조
- 50~69: 무난, 관리/조정/페이스 유지 중심
- 0~49: 조심, 감정 안정·휴식·정리 중심

영역별 톤 차별화
- 총운: 하루 전체 흐름
- 연애운: 감정·소통·관계
- 학업운: 집중·정리·루틴
- 금전운: 소비·판단·우선순위
- 건강운: 컨디션·피로·생활습관

행운 포인트 생성 규칙
- color.name: 한국어 색 이름(과도하게 추상적 금지)
- number.value: 1~9
- item.name: 실제 생활 소지품
- keyword.word: 행동 또는 태도 단어
- 각 항목 reason에는 반드시 오늘 운세와의 연결 이유 작성

중요
- 카드 5개 모두 서로 다른 문장 구조를 사용
- main 문장은 카드 간 유사도 최소화
- tip/caution 문장 재사용 금지
- 일본 원문이 없을 경우에도 반드시 새로운 멘트 생성

응답은 반드시 JSON만 출력하고, 설명·마크다운·주석은 출력하지 마라."""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "object",
            "properties": {"headline": {"type": "string"}, "message": {"type": "string"}},
            "required": ["headline", "message"],
            "additionalProperties": False,
        },
        "cards": {
            "type": "object",
            "properties": {
                "overall": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "score": {"type": "integer"},
                        "main": {"type": "string"},
                        "detail": {"type": "string"},
                        "tip": {"type": "string"},
                        "caution": {"type": "string"},
                    },
                    "required": ["title", "score", "main", "detail", "tip", "caution"],
                    "additionalProperties": False,
                },
                "love": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "score": {"type": "integer"},
                        "main": {"type": "string"},
                        "detail": {"type": "string"},
                        "tip": {"type": "string"},
                        "caution": {"type": "string"},
                    },
                    "required": ["title", "score", "main", "detail", "tip", "caution"],
                    "additionalProperties": False,
                },
                "study": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "score": {"type": "integer"},
                        "main": {"type": "string"},
                        "detail": {"type": "string"},
                        "tip": {"type": "string"},
                        "caution": {"type": "string"},
                    },
                    "required": ["title", "score", "main", "detail", "tip", "caution"],
                    "additionalProperties": False,
                },
                "money": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "score": {"type": "integer"},
                        "main": {"type": "string"},
                        "detail": {"type": "string"},
                        "tip": {"type": "string"},
                        "caution": {"type": "string"},
                    },
                    "required": ["title", "score", "main", "detail", "tip", "caution"],
                    "additionalProperties": False,
                },
                "health": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "score": {"type": "integer"},
                        "main": {"type": "string"},
                        "detail": {"type": "string"},
                        "tip": {"type": "string"},
                        "caution": {"type": "string"},
                    },
                    "required": ["title", "score", "main", "detail", "tip", "caution"],
                    "additionalProperties": False,
                },
            },
            "required": ["overall", "love", "study", "money", "health"],
            "additionalProperties": False,
        },
        "lucky_points": {
            "type": "object",
            "properties": {
                "color": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "reason": {"type": "string"}},
                    "required": ["name", "reason"],
                    "additionalProperties": False,
                },
                "number": {
                    "type": "object",
                    "properties": {"value": {"type": "integer"}, "reason": {"type": "string"}},
                    "required": ["value", "reason"],
                    "additionalProperties": False,
                },
                "item": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "reason": {"type": "string"}},
                    "required": ["name", "reason"],
                    "additionalProperties": False,
                },
                "keyword": {
                    "type": "object",
                    "properties": {"word": {"type": "string"}, "reason": {"type": "string"}},
                    "required": ["word", "reason"],
                    "additionalProperties": False,
                },
            },
            "required": ["color", "number", "item", "keyword"],
            "additionalProperties": False,
        },
    },
    "required": ["summary", "cards", "lucky_points"],
    "additionalProperties": False,
}


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
        return "", results


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


def validate_generated_content(content: dict[str, Any], scores: dict[str, int]) -> None:
    summary = content.get("summary")
    if not isinstance(summary, dict) or not summary.get("headline") or not summary.get("message"):
        raise ValueError("summary invalid")

    cards = content.get("cards")
    if not isinstance(cards, dict):
        raise ValueError("cards missing")

    score_keys = {
        "overall": "total",
        "love": "love",
        "study": "study",
        "money": "money",
        "health": "health",
    }
    for card_key, score_key in score_keys.items():
        card = cards.get(card_key)
        if not isinstance(card, dict):
            raise ValueError(f"cards.{card_key} missing")
        for field in ["title", "main", "detail", "tip", "caution"]:
            value = card.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"cards.{card_key}.{field} missing")
        card_score = card.get("score")
        if not isinstance(card_score, int):
            raise ValueError(f"cards.{card_key}.score invalid")
        if abs(card_score - scores[score_key]) > 5:
            raise ValueError(f"cards.{card_key}.score mismatch")

    lucky_points = content.get("lucky_points")
    if not isinstance(lucky_points, dict):
        raise ValueError("lucky_points missing")

    color = lucky_points.get("color")
    number = lucky_points.get("number")
    item = lucky_points.get("item")
    keyword = lucky_points.get("keyword")

    if not isinstance(color, dict) or not color.get("name") or not color.get("reason"):
        raise ValueError("lucky_points.color invalid")
    if not isinstance(number, dict) or not isinstance(number.get("value"), int) or not number.get("reason"):
        raise ValueError("lucky_points.number invalid")
    if number["value"] < 1 or number["value"] > 9:
        raise ValueError("lucky_points.number.value out of range")
    if not isinstance(item, dict) or not item.get("name") or not item.get("reason"):
        raise ValueError("lucky_points.item invalid")
    if not isinstance(keyword, dict) or not keyword.get("word") or not keyword.get("reason"):
        raise ValueError("lucky_points.keyword invalid")


def hex_from_seed(seed_text: str) -> str:
    digest = hashlib.md5(seed_text.encode("utf-8")).hexdigest()
    return f"#{digest[:6].upper()}"


def convert_content_to_ai(content: dict[str, Any], scores: dict[str, int], sign_seed: str) -> dict[str, Any]:
    cards = content["cards"]
    lucky = content["lucky_points"]

    return {
        "message_ko": content["summary"]["message"],
        "ai": {
            "summary": content["summary"]["headline"],
            "tip": cards["overall"]["tip"],
            "warning": cards["overall"]["caution"],
            "lucky": {
                "color_name_ko": lucky["color"]["name"],
                "color_hex": hex_from_seed(f"{sign_seed}|{lucky['color']['name']}"),
                "number": lucky["number"]["value"],
                "item": lucky["item"]["name"],
                "keyword": lucky["keyword"]["word"],
                "reasons": {
                    "color": lucky["color"]["reason"],
                    "number": lucky["number"]["reason"],
                    "item": lucky["item"]["reason"],
                    "keyword": lucky["keyword"]["reason"],
                },
            },
            "cards": {
                "total": {
                    "title": cards["overall"]["main"],
                    "body": cards["overall"]["detail"],
                    "tip": cards["overall"]["tip"],
                    "warning": cards["overall"]["caution"],
                },
                "love": {
                    "title": cards["love"]["main"],
                    "body": cards["love"]["detail"],
                    "tip": cards["love"]["tip"],
                    "warning": cards["love"]["caution"],
                },
                "study": {
                    "title": cards["study"]["main"],
                    "body": cards["study"]["detail"],
                    "tip": cards["study"]["tip"],
                    "warning": cards["study"]["caution"],
                },
                "money": {
                    "title": cards["money"]["main"],
                    "body": cards["money"]["detail"],
                    "tip": cards["money"]["tip"],
                    "warning": cards["money"]["caution"],
                },
                "health": {
                    "title": cards["health"]["main"],
                    "body": cards["health"]["detail"],
                    "tip": cards["health"]["tip"],
                    "warning": cards["health"]["caution"],
                },
            },
            "raw_content": content,
        },
    }


def generate_ai_bundle(
    client: OpenAI,
    date_key: str,
    sign_jp: str,
    sign_ko: str,
    scores: dict[str, int],
    message_jp: str,
) -> dict[str, Any]:
    prompt_input = {
        "date": date_key,
        "western_zodiac": sign_ko,
        "chinese_zodiac": "정보 없음",
        "scores": {
            "overall": scores["total"],
            "love": scores["love"],
            "study": scores["study"],
            "money": scores["money"],
            "health": scores["health"],
        },
        "source_text_ja": message_jp,
        "seed_hint": f"{date_key}|{sign_jp}|ohahasa-content-v2",
    }

    last_error: Exception | None = None
    for attempt in range(OPENAI_RETRY_COUNT + 1):
        try:
            response = client.responses.create(
                model=OPENAI_MODEL,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "[입력 데이터]\n"
                            f"{json.dumps(prompt_input, ensure_ascii=False, indent=2)}\n\n"
                            "[출력 형식]\n"
                            f"{json.dumps(RESPONSE_SCHEMA, ensure_ascii=False)}"
                        ),
                    },
                ],
            )
            raw_text = get_response_text(response)
            generated_content = json.loads(raw_text)
            validate_generated_content(generated_content, scores)
            return convert_content_to_ai(generated_content, scores, f"{date_key}|{sign_jp}")
        except Exception as error:
            last_error = error
            logging.warning("OpenAI parse/generation failed (%s/%s): %s", attempt + 1, OPENAI_RETRY_COUNT + 1, error)
            if attempt < OPENAI_RETRY_COUNT:
                time.sleep(0.4)

    raise RuntimeError(f"OpenAI generation failed: {last_error}")


def is_ai_bundle_usable(bundle: Any) -> bool:
    if not isinstance(bundle, dict):
        return False
    if not isinstance(bundle.get("message_ko"), str) or not bundle["message_ko"].strip():
        return False
    ai = bundle.get("ai")
    if not isinstance(ai, dict):
        return False
    if not isinstance(ai.get("cards"), dict):
        return False
    return True


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

        if not is_ai_bundle_usable(ai_bundle):
            ai_bundle = None

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
        error_message = "OPENAI_API_KEY missing" if not client else f"AI generation failed for: {', '.join(ai_failed_items)}"

    write_payload(build_payload(date_key, rankings, status=status, error_message=error_message))
    save_cache(AI_CACHE_PATH, ai_cache)
    logging.info("Updated %s with %d rankings", OUTPUT_PATH, len(rankings))


if __name__ == "__main__":
    main()
