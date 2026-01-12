# 오하아사 별자리 운세

매일 오전 5시(KST) 기준으로 아사히 오하아사의 별자리 순위를 스크래핑하여 `public/fortune.json`에 저장합니다.

## GitHub Actions Secrets

리포지토리 Settings > Secrets and variables > Actions에서 아래 값을 등록하세요.

- `PAPAGO_CLIENT_ID`
- `PAPAGO_CLIENT_SECRET`

Papago 키가 없을 경우 번역은 생략되고 일본어 원문만 제공됩니다.

## 로컬 실행

```bash
python scripts/fetch_ohaasa.py
```

```bash
npm install
npm run dev
```

워크플로는 `workflow_dispatch`로 수동 실행할 수 있습니다.
