# Market Rader 📈

매일 자동으로 주식 뉴스, 애널리스트 리포트를 수집하고 AI가 분석하여 디스코드로 보내주는 봇입니다.

## 주요 기능

- **📰 뉴스 수집**: 11개 한국 경제/증시 소스 + 해외 3개 (RSS 기반)
- **📊 애널리스트 리포트**: 네이버 증권 리서치, Seeking Alpha (PDF OCR 분석 포함)
- **🎬 유튜브 모니터링**: 삼프로TV 등 경제 채널 신규 영상 감지 + AI 요약
- **🤖 AI 분석**: Google Gemini 2.5 Flash — 아침 전략, 장마감 리뷰, 시장 시그널
- **📡 SWOT 분석**: 뉴스 기반 강점/약점/기회/위협 분석
- **🏭 BCG 매트릭스**: 섹터별 Star/Cash Cow/Question Mark/Dog 분류
- **📈 섹터 ETF 시세**: 9개 섹터 ETF 실시간 등락률
- **🌙 야간선물**: KOSPI 200, KOSDAQ 150 야간선물 마감 데이터
- **🇺🇸 미국장 마감**: 전일 미국 시장 마감 데이터 (S&P 500, NASDAQ, 다우 등)
- **🔍 통합 AI 뉴스 평가**: Gemini 1회 호출로 중요도 + 감성 + 긴급뉴스 동시 판단
- **📊 감성 분류**: AI 맥락 기반 긍정/부정 뉴스 분류 (키워드 폴백)
- **⭐ 중요도 평가**: 키워드(40%) + AI(60%) 블렌딩 + 우선 기자/애널리스트 가중치
- **🔗 뉴스 중복 제거**: 제목 유사도 기반 동일 이벤트 중복 보도 제거
- **🛢️ 원자재 급변 감지**: WTI/금 5%+ 변동 시 AI 브리핑에 자동 반영
- **📊 오전 시그널 캐시**: 아침 예측 vs 장마감 결과 비교
- **🏖️ 휴장일 감지**: 한국 시장 휴장일 자동 감지 (오전 1회만 안내)
- **🆓 무료 운영**: GitHub Actions + 무료 API 활용

## 뉴스 소스

### 한국 (11개)
| 소스 | 특화 | 우선순위 |
|------|------|----------|
| 네이버 금융 | 증시/경제 | - |
| 한국경제 | 금융 | high |
| 한경 산업 | 산업/기업 | high |
| 전자신문 | IT/반도체 | high |
| 연합인포맥스 | 금융 | medium |
| 매일경제 | 종합 | low |
| 서울경제 증권 | 증권 | high |
| 이데일리 증시 | 증시 | high |
| 이데일리 경제 | 경제정책 | medium |
| 파이낸셜뉴스 증시 | 증시 | high |
| 아시아경제 증시 | 증시 | medium |
| 헤럴드경제 증권 | 증권 | medium |

### 해외 (3개)
Reuters Business, Yahoo Finance, CNBC

## 스케줄

| 시간 (KST) | 요일 | 내용 |
|------------|------|------|
| 오전 7시 | 월~금 | AI 아침 전략 + SWOT/BCG + 긍정/부정 뉴스 + 리포트 |
| 오후 12시 | 월~금 | 국내 뉴스 (간략) |
| 오후 5시 | 월~금 | 장 마감 시황 + AI 리뷰 + 원자재 급변 |
| 오후 1시 | 토요일 | 주간 시장 리뷰 (크롤링 데이터 기반) |
| 오후 1시 | 일요일 | 다음 주 시장 전망 |
| 휴장일 | - | 오전 1회 휴장 안내만 전송 |

### 오전 7시 Embed 구성
1. 긴급 뉴스 (조건부 — AI 맥락 검증 통과 건만)
2. AI 아침 전략 — Morning Brief + 해외뉴스 + 미국장 마감 + 야간선물
3. 시장 시그널 + SWOT + BCG
4. 📈 긍정 뉴스 5건 / 📉 부정 뉴스 5건
5. 애널리스트 리포트 (AI 분석 + 목록)

### 오후 5시 Embed 구성
1. 장 마감 시황 (KOSPI 70% + KOSDAQ 30% 가중 평가)
2. AI 장 마감 리뷰 (오전 예측 대비 결과 포함)
3. 뉴스 목록 (중복 제거 적용)

## 분석 파이프라인

```
수집 (병렬)
├── 뉴스 (한국 11 + 해외 3 RSS)
├── 리포트 (네이버 리서치 + Seeking Alpha)
├── Morning Brief (오전만)
└── 유튜브 (오전 제외)
        ↓
  키워드 사전 필터 (min 0.3)
        ↓
  ┌─────────────────────────────┐
  │  통합 AI 배치 평가 (Gemini 1회) │
  │  ① 중요도 재평가 (0.0~1.0)    │
  │  ② 감성 분류 (맥락 기반)       │
  │  ③ 긴급뉴스 여부              │
  └─────────────────────────────┘
        ↓
  키워드(40%) + AI(60%) 블렌딩
        ↓
  제목 유사도 중복 제거 (0.55)
        ↓
  ┌─────┴─────┐
  │           │
수치 데이터   AI 분석
(크롤링 100%)  (정성적만)
  │           │
  ├ ETF 시세   ├ SWOT 분석
  ├ 야간선물   ├ BCG 매트릭스
  ├ 환율/지수  ├ 아침 전략
  ├ 미국장 마감 ├ 장마감 리뷰
  │           └ 원자재 급변 반영
  └─────┬─────┘
        ↓
   Discord Embed 전송
```

**핵심 원칙**: 모든 수치(주가, 등락률, 환율 등)는 크롤링 데이터를 직접 표시하고, AI는 정성적 분석(원인, 전망, 인사이트)만 담당합니다.

## 설치 및 설정

### 1. 저장소 클론

```bash
git clone https://github.com/codeminjun/Market_Rader.git
cd Market_Rader
```

### 2. Conda 환경 설정

```bash
conda create -n stock_bot python=3.11
conda activate stock_bot
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env.example`을 복사하여 `.env` 파일 생성:

```bash
cp .env.example .env
```

```env
# 필수
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
GEMINI_API_KEY=AIza...

# 테스트 서버 (선택)
DISCORD_WEBHOOK_URL_TEST=https://discord.com/api/webhooks/...

# 선택
NEWSAPI_KEY=...
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
```

### 4. 시스템 패키지 (OCR용)

```bash
# macOS
brew install tesseract
brew install tesseract-lang  # 한국어 포함

# Ubuntu (GitHub Actions에서 자동 설치)
sudo apt-get install tesseract-ocr tesseract-ocr-kor
```

### 5. 실행

```bash
# 일반 실행 (시간 기반 자동 스케줄)
python src/main.py

# 스케줄 지정
python src/main.py --schedule morning
python src/main.py --schedule noon
python src/main.py --schedule afternoon

# 테스트 서버로 전송
python src/main.py --test --schedule morning

# 터미널 미리보기 (AI 호출 없음, Discord 전송 없음)
python src/main.py --dry-run --schedule morning
```

#### CLI 옵션
| 옵션 | 설명 |
|------|------|
| `--test` | 테스트 웹훅 서버로 전송 |
| `--schedule morning/noon/afternoon` | 스케줄 타입 강제 지정 |
| `--dry-run` | 터미널 출력만 (API 호출 없음) |

## API 키 발급

### Discord Webhook (필수)
1. Discord 서버 설정 → 연동 → 웹후크
2. 새 웹후크 만들기
3. 웹후크 URL 복사

### Google Gemini API (필수, 무료)
1. https://aistudio.google.com/apikey 접속
2. API Key 생성
3. 무료 한도: 5 RPM / 20 RPD (gemini-2.5-flash)

### NewsAPI (선택, 무료 100회/일)
1. https://newsapi.org/ 가입
2. API Key 발급

### 네이버 개발자 API (선택)
1. https://developers.naver.com/ 가입
2. 애플리케이션 등록 → 검색 API 선택

## GitHub Actions 설정

### 1. 저장소 Secrets 설정

GitHub 저장소 → Settings → Secrets and variables → Actions:

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
│   └── daily_news.yml              # GitHub Actions 스케줄
├── src/
│   ├── main.py                     # 메인 실행 파일
│   ├── collectors/                 # 콘텐츠 수집
│   │   ├── base.py                 # ContentItem 기본 클래스
│   │   ├── news/                   # 뉴스 수집기
│   │   │   ├── rss_news.py         # RSS 피드 (11개 한국 + 3개 해외)
│   │   │   └── naver_news.py       # 네이버 금융 + 검색
│   │   ├── reports/                # 리포트 수집기
│   │   │   ├── naver_research.py   # 네이버 리서치 (PDF OCR)
│   │   │   ├── seeking_alpha.py    # Seeking Alpha
│   │   │   └── morning_brief.py    # 증권사 Morning Brief
│   │   ├── market/                 # 시장 데이터
│   │   │   └── market_data.py      # 지수, ETF, 환율, 원자재, 야간선물, 미국장
│   │   └── youtube/                # 유튜브 수집기
│   │       ├── channel_monitor.py  # 채널 모니터링
│   │       └── transcript_extractor.py  # 자막 추출
│   ├── analyzer/                   # AI 분석
│   │   ├── gemini_client.py        # Gemini 2.5 Flash API (rate limit 자동 재시도)
│   │   ├── news_evaluator.py       # 통합 AI 뉴스 평가 (중요도+감성+긴급)
│   │   ├── news_sentiment.py       # 키워드+AI 감성 분류 (폴백용)
│   │   ├── market_signal.py        # 시장 시그널 + SWOT + 긴급뉴스 맥락 검증
│   │   ├── market_briefing.py      # 아침 전략 / 장마감 리뷰 (원자재 급변 반영)
│   │   ├── weekly_summarizer.py    # 주간 리뷰 / 전망
│   │   ├── importance_scorer.py    # 중요도 평가 (키워드+기자+커버드콜)
│   │   ├── report_analyzer.py      # PDF 리포트 AI 분석
│   │   ├── news_summarizer.py      # 뉴스/리포트 AI 요약
│   │   ├── video_summarizer.py     # 유튜브 AI 요약
│   │   ├── morning_brief_summarizer.py  # Morning Brief 요약
│   │   └── briefing_validator.py   # AI 브리핑 검증
│   ├── discord/                    # Discord 전송
│   │   ├── webhook.py              # Webhook 전송
│   │   └── embeds/                 # Embed 빌더
│   │       ├── news_embed.py       # 뉴스 헤더/목록/감성분류
│   │       ├── report_embed.py     # 리포트 목록 + AI 분석
│   │       ├── youtube_embed.py    # 유튜브 영상
│   │       ├── briefing_embed.py   # AI 브리핑
│   │       ├── market_close_embed.py   # 장마감 시황 (KOSPI 가중)
│   │       ├── morning_brief_embed.py  # Morning Brief
│   │       ├── weekend_embed.py    # 주간 리뷰/전망
│   │       └── holiday_embed.py    # 휴장일 안내
│   └── utils/                      # 유틸리티
│       ├── constants.py            # 설정 상수 (스케줄/뉴스/중요도)
│       ├── cache.py                # 중복 전송 방지
│       ├── dedup.py                # 제목 유사도 기반 중복 제거
│       ├── logger.py               # 로깅
│       ├── market_holiday.py       # 휴장일 감지
│       ├── signal_cache.py         # 오전 시그널 캐시
│       └── weekly_archive.py       # 주간 뉴스 아카이브
├── config/
│   ├── settings.py                 # 설정 관리 (API 키, 모델)
│   ├── news_sources.yaml           # 뉴스 소스 설정
│   ├── youtube_channels.yaml       # 유튜브 채널 설정
│   ├── journalist_priority.yaml    # 우선 기자/애널리스트 설정
│   └── top_companies.yaml          # 시총 상위 50 (국내+해외)
├── data/                           # 캐시 데이터
├── requirements.txt
└── .env.example
```

## 우선순위 시스템

### 우선 기자 (가중치 +0.25)
안재광 (한국경제) · 김현석 (한국경제신문) · 안근모 (글로벌모니터) · 임형인 (중앙일보) · 신현규 (매일경제신문) · 황정수 (한국경제신문) · 강해령 (서울경제신문) · 이진우 (MBC)

### 우선 애널리스트 (가중치 +0.25)
허혜민 (키움증권) · 엄경아 (신영증권) · 박은정 (하나증권) · 이동헌 (신한투자증권)

## AI 시장 시그널

| 시그널 | 이모지 | 의미 |
|--------|--------|------|
| `strong_bullish` | 🚀 | 강한 상승 (호재 다수) |
| `bullish` | 📈 | 상승 우위 (호재 > 악재) |
| `neutral` | ➡️ | 혼조세/영향 제한적 |
| `bearish` | 📉 | 하락 우위 (악재 > 호재) |
| `strong_bearish` | 💥 | 강한 하락 (악재 다수) |

### 섹터별 시그널
반도체 · 2차전지 · AI/소프트웨어 · 자동차 · 바이오 · 금융 · 방산 · 매크로

## 비용

- **GitHub Actions**: 무료 (월 2,000분)
- **Gemini API**: 무료 (일 20회, 분 5회 — gemini-2.5-flash)
- **기타**: 모두 무료 티어 사용

예상 월 비용: **$0**

## 라이선스

MIT License
