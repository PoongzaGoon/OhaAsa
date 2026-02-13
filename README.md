# 오하아사 오늘의 운세

아사히TV **오하아사(おはよう朝日です)** 별자리 순위를 스크래핑하고, 한국어 번역/요약 데이터를 결합해 보여주는 웹 앱입니다.

- 오하아사 원문 순위(1~12위) 제공
- 별자리별 상세 멘트, 카테고리 점수(총운/연애/학업/금전/건강) 표시
- 생년월일 기반 개인 운세 화면 제공
- OpenAI Responses API를 이용해 한국어 번역 및 조언 문구 생성

## 프로젝트 구조

- `src/`: React(Vite) 프런트엔드
- `public/fortune.json`: 앱에서 읽는 운세 데이터
- `scripts/fetch_ohaasa.py`: 오하아사 스크래핑 + AI 데이터 생성 스크립트
- `scripts/validate_fortune_json.py`: 생성된 JSON 유효성 검사 도구

## 요구 사항

- Node.js 18+
- Python 3.10+
- (스크래핑용) Playwright 브라우저 실행 환경
- (AI 번역/조언 생성용) OpenAI API Key

## 환경 변수

`scripts/fetch_ohaasa.py` 실행 시 아래 값을 사용합니다.

- `OPENAI_API_KEY` (선택이지만 권장)
- `OPENAI_MODEL` (선택, 기본값: `gpt-5-mini`)

`OPENAI_API_KEY`가 없으면 한국어 AI 번역/조언이 비어 있을 수 있으며, 앱은 일본어 원문 중심으로 동작합니다.

## 로컬 실행

### 1) 의존성 설치

```bash
npm install
pip install -r scripts/requirements.txt
python -m playwright install chromium
```

### 2) 운세 데이터 생성

```bash
python scripts/fetch_ohaasa.py
python scripts/validate_fortune_json.py public/fortune.json
```

### 3) 프런트엔드 실행

```bash
npm run dev
```

브라우저에서 기본 주소(`http://localhost:5173`)로 접속합니다.

## 배포 빌드

```bash
npm run build
npm run preview
```

## 주의 사항

- 오하아사 사이트 구조가 변경되면 스크래핑 선택자(`ul.oa_horoscope_list > li` 등) 수정이 필요할 수 있습니다.
- 생성 결과가 12개 별자리 순위를 만족하지 않으면 스크립트가 실패하도록 보호 로직이 들어있습니다.
