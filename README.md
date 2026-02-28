# Market Rader 📈

매일 자동으로 주식 뉴스, 애널리스트 리포트, 유튜브 영상을 수집하고 AI가 분석하여 디스코드로 보내주는 봇입니다.

## 주요 기능

- **📰 뉴스 수집**: 네이버 금융, 한국경제, 매일경제, Reuters, CNBC 등
- **📊 애널리스트 리포트**: 네이버 증권 리서치, Seeking Alpha (PDF OCR 분석 포함)
- **🎬 유튜브 영상**: 삼프로TV, 슈카월드, CNBC, Bloomberg 등
- **🤖 AI 분석**: Google Gemini 2.5 Flash를 사용한 뉴스 요약 및 투자 인사이트
- **📡 AI 시장 시그널**: 뉴스 기반 Bullish/Bearish/Neutral 투자 시그널
- **📈 섹터 ETF 시세**: 9개 섹터 ETF 실시간 등락률 (네이버 금융 크롤링)
- **⭐ 중요도 평가**: AI + 우선 기자/애널리스트 기반 자동 중요도 판단
- **🏖️ 휴장일 감지**: 한국 시장 휴장일 자동 감지 및 안내
- **🆓 무료 운영**: GitHub Actions + 무료 API 활용

## 스케줄

| 시간 (KST) | 요일 | 내용 |
|------------|------|------|
| 오전 7시 | 월~금 | 전체 콘텐츠 (뉴스 + 리포트 + 유튜브 + AI 아침 전략) |
| 오후 12시 | 월~금 | 국내 뉴스 (간략) |
| 오후 5시 | 월~금 | 장 마감 시황 + AI 리뷰 (수치는 크롤링, 분석은 AI) |
| 오후 1시 | 토요일 | 주간 시장 리뷰 (크롤링 데이터 기반) |
| 오후 1시 | 일요일 | 다음 주 시장 전망 |

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
GEMINI_API_KEY=AIza...

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

### Google Gemini API (필수, 무료)
1. https://aistudio.google.com/apikey 접속
2. API Key 생성
3. 무료 한도: 10 RPM / 250 RPD / 250,000 TPM

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
| `GEMINI_API_KEY` | Google Gemini API 키 |
| `NEWSAPI_KEY` | (선택) NewsAPI 키 |
| `NAVER_CLIENT_ID` | (선택) 네이버 Client ID |
| `NAVER_CLIENT_SECRET` | (선택) 네이버 Client Secret |

### 2. 워크플로우 활성화

저장소를 푸시하면 자동으로 워크플로우가 활성화됩니다.
- 자동 실행: 스케줄 표 참조
- 수동 실행: Actions → Daily Stock News → Run workflow

## 프로젝트 구조

```
Market_Rader/
├── .github/workflows/
│   └── daily_news.yml          # GitHub Actions
├── src/
│   ├── main.py                 # 메인 실행 파일
│   ├── collectors/             # 콘텐츠 수집
│   │   ├── news/               # 뉴스 수집기 (네이버, RSS)
│   │   ├── reports/            # 리포트 수집기 (PDF OCR)
│   │   ├── market/             # 시장 데이터 수집기 (지수, ETF)
│   │   └── youtube/            # 유튜브 수집기
│   ├── analyzer/               # AI 분석
│   │   ├── gemini_client.py    # Gemini 2.5 Flash API
│   │   ├── news_summarizer.py  # 뉴스 요약
│   │   ├── market_signal.py    # 시장 시그널 분석
│   │   ├── market_briefing.py  # 장 마감 리뷰 / 아침 전략
│   │   ├── weekly_summarizer.py # 주간 리뷰 / 전망
│   │   ├── importance_scorer.py # 중요도 평가
│   │   └── briefing_validator.py # 브리핑 검증
│   ├── discord/                # Discord 전송
│   │   ├── webhook.py          # Webhook 전송
│   │   └── embeds/             # Embed 빌더
│   └── utils/                  # 유틸리티
│       ├── weekly_archive.py   # 주간 뉴스 아카이브
│       ├── market_holiday.py   # 휴장일 감지
│       └── cache.py            # 중복 전송 방지
├── config/
│   ├── settings.py             # 설정 관리
│   ├── news_sources.yaml       # 뉴스 소스 설정
│   ├── youtube_channels.yaml   # 유튜브 채널 설정
│   └── journalist_priority.yaml # 우선 기자 설정
├── data/                       # 캐시 데이터
├── requirements.txt
└── .env.example
```

## 아키텍처

```
크롤링 (네이버/RSS/유튜브)
        ↓
  중요도 평가 (AI + 규칙)
        ↓
  ┌─────┴─────┐
  │           │
수치 데이터   AI 분석
(크롤링 100%)  (정성적만)
  │           │
  └─────┬─────┘
        ↓
   Discord Embed
```

**핵심 원칙**: 모든 수치(주가, 등락률, 환율 등)는 크롤링 데이터를 직접 표시하고, AI는 정성적 분석(원인, 전망, 인사이트)만 담당합니다.

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

## 비용

- **GitHub Actions**: 무료 (월 2,000분)
- **Gemini API**: 무료 (일 250회, 분 10회)
- **기타**: 모두 무료 티어 사용

예상 월 비용: **$0**

## 라이선스

MIT License

## 기여

이슈 및 PR 환영합니다!
