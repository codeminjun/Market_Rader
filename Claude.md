# Market Rader - Claude Code 프로젝트 가이드

## 환경 설정

### Conda 환경
- **환경 이름**: `stock_bot`
- **환경 경로**: `/opt/anaconda3/envs/stock_bot`
- **Python 버전**: 3.11

### 의존성 설치 규칙
모든 Python 패키지는 반드시 Conda 환경에서 설치해야 합니다:

```bash
# 패키지 설치 시 반드시 이 경로 사용
/opt/anaconda3/envs/stock_bot/bin/pip install <패키지명>

# 예시
/opt/anaconda3/envs/stock_bot/bin/pip install PyMuPDF pytesseract
```

새 패키지 설치 후 반드시 `requirements.txt`에 추가할 것.

---

## 프로젝트 구조

### 주요 디렉토리
- `src/collectors/` - 뉴스, 리포트, 유튜브 수집기
- `src/analyzer/` - AI 요약 및 중요도 평가
- `src/discord/` - Discord Webhook 전송 및 Embed 빌더
- `config/` - 설정 파일 (YAML)

### 스케줄 (GitHub Actions)
- **오전 7시 (KST)**: 전체 콘텐츠 (뉴스 + 리포트 + 유튜브 + Morning Brief)
- **오후 12시 (KST)**: 국내 뉴스만 (간략)
- **오후 5시 (KST)**: 장마감 뉴스 (간략)
- **토요일**: 주간 리뷰
- **일요일**: 주간 전망

---

## 우선순위 시스템

### 우선 기자 (동일 가중치 0.25)
- 안재광 (한국경제)
- 김현석 (한국경제신문)
- 안근모 (글로벌모니터)
- 임형인 (중앙일보)
- 신현규 (매일경제신문)
- 황정수 (한국경제신문)
- 강해령 (서울경제신문)
- 이진우 (MBC)

### 우선 애널리스트 (동일 가중치 0.25)
- 허혜민 (키움증권)
- 엄경아 (신영증권)
- 박은정 (하나증권)
- 이동헌 (신한투자증권)

### 중요 키워드
- 퀄테스트, 캐파, 증설, 신한투자증권

---

## AI 시장 시그널 시스템

### 시그널 유형
| 시그널 | 이모지 | 의미 |
|--------|--------|------|
| `strong_bullish` | 🚀 | 강한 상승 (호재 다수) |
| `bullish` | 📈 | 상승 우위 (호재 > 악재) |
| `neutral` | ➡️ | 혼조세/영향 제한적 |
| `bearish` | 📉 | 하락 우위 (악재 > 호재) |
| `strong_bearish` | 💥 | 강한 하락 (악재 다수) |

### 분석 항목
- **시장 시그널**: 전체 뉴스 기반 상승/하락 판단
- **섹터별 시그널**: 반도체, 2차전지, AI, 자동차, 바이오 등
- **긴급 뉴스 감지**: 급등, 급락, 폭등, 폭락 키워드
- **핵심 이벤트**: 오늘의 주요 이벤트 3-4개
- **리스크 요인**: 주의할 위험 요소

### 섹터 분류
- 반도체: 삼성전자, SK하이닉스, HBM, D램 등
- 2차전지: LG에너지, 삼성SDI, 배터리, 리튬 등
- AI/소프트웨어: AI, 인공지능, 클라우드, 데이터센터
- 자동차: 현대차, 기아, 테슬라, 전기차
- 바이오: 바이오, 신약, 임상, FDA
- 금융: 금리, 은행, 증권
- 방산: 한화에어로, LIG넥스원
- 매크로: FOMC, 연준, 금리, CPI

---

## 외부 의존성

### 시스템 패키지 (OCR용)
로컬 개발 시:
```bash
brew install tesseract
brew install tesseract-lang  # 한국어 포함
```

GitHub Actions에서는 워크플로우에서 자동 설치됨 (`tesseract-ocr`, `tesseract-ocr-kor`)

---

## API 키 (환경변수)
- `DISCORD_WEBHOOK_URL` - Discord Webhook URL
- `GROQ_API_KEY` - Groq AI API 키
- `NEWSAPI_KEY` - NewsAPI 키 (선택)
- `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` - 네이버 API (선택)
