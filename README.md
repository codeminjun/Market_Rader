# Market Rader 📈

매일 오전 7시(KST)에 주식 관련 뉴스, 애널리스트 리포트, 유튜브 영상을 정리하여 디스코드로 보내주는 봇입니다.

## 주요 기능

- **📰 뉴스 수집**: 네이버 금융, 한국경제, 매일경제, Reuters, CNBC 등
- **📊 애널리스트 리포트**: 네이버 증권 리서치, Seeking Alpha
- **🎬 유튜브 영상**: 삼프로TV, 슈카월드, CNBC, Bloomberg 등
- **🤖 AI 요약**: Groq API (Llama 3.1)를 사용한 뉴스 요약 및 투자 인사이트
- **⭐ 중요도 평가**: AI 기반 콘텐츠 중요도 자동 판단
- **🆓 무료 운영**: GitHub Actions + 무료 API 활용

## 설치 및 설정

### 1. 저장소 클론

```bash
git clone https://github.com/your-username/Market_Rader.git
cd Market_Rader
```

### 2. 가상환경 생성 및 의존성 설치

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env.example`을 복사하여 `.env` 파일 생성:

```bash
cp .env.example .env
```

`.env` 파일 편집:

```env
# 필수
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
GROQ_API_KEY=gsk_...

# 선택
NEWSAPI_KEY=...
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
```

### 4. 로컬 테스트

```bash
python src/main.py
```

## API 키 발급

### Discord Webhook (필수)
1. Discord 서버 설정 → 연동 → 웹후크
2. 새 웹후크 만들기
3. 웹후크 URL 복사

### Groq API (필수, 무료)
1. https://console.groq.com/ 가입
2. API Keys에서 새 키 생성

### NewsAPI (선택, 무료 100회/일)
1. https://newsapi.org/ 가입
2. API Key 발급

### 네이버 개발자 API (선택)
1. https://developers.naver.com/ 가입
2. 애플리케이션 등록 → 검색 API 선택

## GitHub Actions 설정

### 1. 저장소 Secrets 설정

GitHub 저장소 → Settings → Secrets and variables → Actions에서 다음 시크릿 추가:

| Secret Name | 설명 |
|-------------|------|
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL |
| `GROQ_API_KEY` | Groq API 키 |
| `NEWSAPI_KEY` | (선택) NewsAPI 키 |
| `NAVER_CLIENT_ID` | (선택) 네이버 Client ID |
| `NAVER_CLIENT_SECRET` | (선택) 네이버 Client Secret |

### 2. 워크플로우 활성화

저장소를 푸시하면 자동으로 워크플로우가 활성화됩니다.
- 자동 실행: 매일 07:00 KST (22:00 UTC)
- 수동 실행: Actions → Daily Stock News → Run workflow

## 프로젝트 구조

```
Market_Rader/
├── .github/workflows/
│   └── daily_news.yml          # GitHub Actions
├── src/
│   ├── main.py                 # 메인 실행 파일
│   ├── collectors/             # 콘텐츠 수집
│   │   ├── news/               # 뉴스 수집기
│   │   ├── reports/            # 리포트 수집기
│   │   └── youtube/            # 유튜브 수집기
│   ├── analyzer/               # AI 분석
│   │   ├── groq_client.py      # Groq API
│   │   ├── news_summarizer.py  # 뉴스 요약
│   │   ├── video_summarizer.py # 영상 요약
│   │   └── importance_scorer.py # 중요도 평가
│   ├── discord/                # Discord 전송
│   │   ├── webhook.py          # Webhook 전송
│   │   └── embeds/             # Embed 빌더
│   └── utils/                  # 유틸리티
├── config/
│   ├── settings.py             # 설정 관리
│   ├── news_sources.yaml       # 뉴스 소스 설정
│   └── youtube_channels.yaml   # 유튜브 채널 설정
├── data/                       # 캐시 데이터
├── requirements.txt
└── .env.example
```

## 설정 커스터마이징

### 뉴스 소스 추가/수정

`config/news_sources.yaml` 편집:

```yaml
news:
  korean:
    - name: "새 뉴스 소스"
      type: "rss"
      url: "https://example.com/rss"
      enabled: true
```

### 유튜브 채널 추가/수정

`config/youtube_channels.yaml` 편집:

```yaml
korean:
  - name: "새 채널"
    channel_id: "UC..."  # 채널 ID
    priority: "high"     # high, medium, low
    enabled: true
```

> 채널 ID 확인: 유튜브 채널 페이지 → 소스 보기 → "channelId" 검색

## 메시지 예시

```
📰 2024년 1월 15일 (월) 주식 뉴스 브리핑

📋 오늘의 요약
연준 금리 동결 기대감 속 국내외 증시 동반 상승...

🎯 핵심 포인트
• FOMC 회의 결과 발표 예정
• 삼성전자 4분기 실적 발표
• 2차전지 관련주 강세

💡 투자 인사이트
금리 동결 기대감이 성장주에 긍정적 영향...

📊 애널리스트 리포트 (5건)
📄 [KB증권] 삼성전자 목표가 상향
📄 [미래에셋] 2차전지 산업 분석

🎬 새 유튜브 영상 (3건)
⭐⭐⭐ 삼프로TV
└ 긴급! 연준 금리 결정 앞두고...
```

## 비용

- **GitHub Actions**: 무료 (월 2,000분)
- **Groq API**: 무료 (일 14,400 요청)
- **기타**: 모두 무료 티어 사용

예상 월 비용: **$0**

## 라이선스

MIT License

## 기여

이슈 및 PR 환영합니다!
