# Market Rader 기능 확장 구현 워크플로우

## 요구사항 요약

| # | 기능 | 우선순위 | 복잡도 |
|---|------|----------|--------|
| 1 | 인베스팅닷컴 인기 뉴스 수집 | HIGH | MEDIUM |
| 2 | 국내 시총 50위 애널리스트 리포트 (목표가 변동) | HIGH | HIGH |
| 3 | 해외 시총 50위 애널리스트 리포트 (목표가 변동) | HIGH | HIGH |
| 4 | 스케줄 변경: 오전 7시 + 오후 12시 | MEDIUM | LOW |
| 5 | 국내/해외 비중 70:30 | MEDIUM | LOW |
| 6 | 커버드콜/배당 뉴스 최우선 + 강조 | HIGH | MEDIUM |
| 7 | 삼프로TV only 유튜브 + 요약 표시 | MEDIUM | LOW |

---

## Phase 1: 커버드콜/배당 뉴스 우선 처리 (예상 작업: 30분)

### 1.1 키워드 가중치 추가
**파일:** `src/analyzer/importance_scorer.py`

```python
# 최상위 가중치 키워드 추가
COVERED_CALL_KEYWORDS = [
    "커버드콜", "covered call", "배당", "dividend",
    "배당주", "배당금", "배당수익", "배당성장",
    "고배당", "월배당", "분기배당", "SCHD", "JEPI", "JEPQ",
    "배당귀족", "배당킹", "배당ETF", "인컴",
]
```

**점수 체계:**
- 커버드콜/배당 키워드: **+0.30** (최우선)
- 산업 키워드: +0.20
- HIGH 키워드: +0.15

### 1.2 Discord Embed 강조 표시
**파일:** `src/discord/embeds/news_embed.py`

```python
# 커버드콜/배당 뉴스 강조 표시
def _get_priority_indicator(item):
    if is_covered_call_news(item):
        return "💰🔥 [배당/커버드콜]"  # 특별 강조
    # 기존 로직...
```

### 1.3 작업 체크리스트
- [ ] `COVERED_CALL_KEYWORDS` 리스트 추가
- [ ] `score_item()` 메서드에 커버드콜 가중치 적용
- [ ] `news_sources.yaml`에 `covered_call` 키워드 섹션 추가
- [ ] `news_embed.py`에 강조 표시 로직 추가
- [ ] 테스트: 커버드콜 뉴스가 최상위 노출되는지 확인

---

## Phase 2: 스케줄 변경 (오전 7시 + 오후 12시) (예상 작업: 20분)

### 2.1 GitHub Actions 수정
**파일:** `.github/workflows/daily_news.yml`

```yaml
on:
  schedule:
    # 오전 7시 (전날 뉴스 요약) - UTC 22:00
    - cron: '0 22 * * *'
    # 오후 12시 (당일 오전 뉴스 요약) - UTC 03:00
    - cron: '0 3 * * *'
```

### 2.2 시간대별 메시지 분기
**파일:** `src/main.py`

```python
from datetime import datetime

def get_schedule_type() -> str:
    """현재 실행 시간에 따른 스케줄 타입 반환"""
    hour = datetime.now().hour
    if 6 <= hour <= 8:
        return "morning"  # 전날 뉴스 요약
    elif 11 <= hour <= 13:
        return "noon"     # 당일 오전 뉴스 요약
    return "manual"
```

### 2.3 Discord 헤더 메시지 분기
```python
# 오전 7시: "📰 전일 마감 후 주요 뉴스"
# 오후 12시: "📰 오전장 주요 뉴스"
```

### 2.4 작업 체크리스트
- [ ] `daily_news.yml` cron 스케줄 추가 (03:00 UTC)
- [ ] `main.py`에 시간대 분기 로직 추가
- [ ] `news_embed.py` 헤더 메시지 동적 생성
- [ ] 테스트: 두 시간대 모두 정상 동작 확인

---

## Phase 3: 국내/해외 비중 70:30 (예상 작업: 15분)

### 3.1 설정 추가
**파일:** `config/settings.py`

```python
class Settings:
    # 국내/해외 뉴스 비중
    KOREAN_NEWS_RATIO: float = 0.7   # 70%
    INTL_NEWS_RATIO: float = 0.3     # 30%

    # 총 뉴스 수 기준 계산
    MAX_KOREAN_NEWS: int = 14   # 20 * 0.7
    MAX_INTL_NEWS: int = 6      # 20 * 0.3
```

### 3.2 main.py 수정
```python
# analyze_content() 함수 수정
result["korean_news"] = scored[:settings.MAX_KOREAN_NEWS]      # 14건
result["international_news"] = scored[:settings.MAX_INTL_NEWS]  # 6건
```

### 3.3 작업 체크리스트
- [ ] `settings.py`에 비중 설정 추가
- [ ] `main.py` analyze_content() 수정
- [ ] `send_to_discord()` 슬라이싱 수정
- [ ] 테스트: 국내 14건, 해외 6건 출력 확인

---

## Phase 4: 삼프로TV only 유튜브 + 요약 (예상 작업: 20분)

### 4.1 youtube_channels.yaml 수정
**파일:** `config/youtube_channels.yaml`

```yaml
korean:
  - name: "삼프로TV"
    channel_id: "UCtmSO2WkVbgZra7FilQWPYQ"
    enabled: true
    priority: "high"
    summarize: true
    max_summary_length: 200  # 간단 요약

# 다른 채널 비활성화 또는 제거
```

### 4.2 main.py 수정
```python
# collect_youtube() - 삼프로TV만 수집
def collect_youtube():
    # korean_videos: 삼프로TV만
    # international_videos: 빈 리스트
```

### 4.3 youtube_embed.py 요약 표시
```python
def create_youtube_list_embed():
    # 각 영상에 간단 요약 표시
    # "📝 요약: {summary[:150]}..."
```

### 4.4 작업 체크리스트
- [ ] `youtube_channels.yaml`에서 삼프로TV만 활성화
- [ ] `main.py` 유튜브 수집 로직 단순화
- [ ] `youtube_embed.py` 요약 필드 표시
- [ ] 테스트: 삼프로TV 영상만 수집 + 요약 표시 확인

---

## Phase 5: 인베스팅닷컴 인기 뉴스 수집 (예상 작업: 1시간)

### 5.1 신규 수집기 생성
**파일:** `src/collectors/news/investing_news.py`

```python
class InvestingNewsCollector(BaseCollector):
    """인베스팅닷컴 인기 뉴스 수집기"""

    BASE_URL = "https://kr.investing.com/news/most-popular-news"

    def collect(self) -> list[ContentItem]:
        # BeautifulSoup으로 인기 뉴스 파싱
        # 조회수 기준 정렬
        pass

    def _parse_news_item(self, element) -> ContentItem:
        # 제목, URL, 조회수, 발행일 추출
        pass
```

### 5.2 news_sources.yaml 추가
```yaml
korean:
  - name: "인베스팅닷컴"
    type: "investing"
    url: "https://kr.investing.com/news/most-popular-news"
    enabled: true
    priority: "high"
```

### 5.3 main.py 통합
```python
# collect_news() 함수에 인베스팅닷컴 추가
from src.collectors.news import InvestingNewsCollector

investing_collector = InvestingNewsCollector()
investing_news = investing_collector.collect()
korean_news.extend(investing_news)
```

### 5.4 작업 체크리스트
- [ ] `investing_news.py` 수집기 생성
- [ ] HTML 구조 분석 및 파싱 로직 구현
- [ ] 조회수 기반 정렬 (extra_data["view_count"])
- [ ] `__init__.py` export 추가
- [ ] `news_sources.yaml` 설정 추가
- [ ] `main.py` 통합
- [ ] 테스트: 인기 뉴스 수집 및 정렬 확인

---

## Phase 6: 국내 시총 50위 애널리스트 리포트 (예상 작업: 2시간)

### 6.1 시총 50위 기업 목록 관리
**파일:** `config/top_companies.yaml`

```yaml
korean_top50:
  - code: "005930"
    name: "삼성전자"
  - code: "000660"
    name: "SK하이닉스"
  - code: "373220"
    name: "LG에너지솔루션"
  # ... 50개 기업
```

### 6.2 네이버 증권 리서치 수집기 개선
**파일:** `src/collectors/reports/naver_research.py`

```python
class NaverResearchCollector:
    def collect_by_company(self, company_code: str) -> list[ContentItem]:
        """특정 종목 리포트 수집"""
        url = f"https://finance.naver.com/research/company_list.naver?searchType=itemCode&itemCode={company_code}"
        # 목표가 변동 정보 추출
        # extra_data["target_price"], extra_data["price_change"]
```

### 6.3 목표가 변동 표시
**파일:** `src/discord/embeds/report_embed.py`

```python
def format_target_price_change(item: ContentItem) -> str:
    """목표가 변동 포맷팅"""
    target = item.extra_data.get("target_price")
    change = item.extra_data.get("price_change")

    if change > 0:
        return f"🎯 목표가 {target:,}원 (▲{change:,})"
    elif change < 0:
        return f"🎯 목표가 {target:,}원 (▼{abs(change):,})"
    return f"🎯 목표가 {target:,}원 (→유지)"
```

### 6.4 작업 체크리스트
- [ ] `top_companies.yaml` 생성 (시총 50위)
- [ ] `naver_research.py` 종목별 수집 메서드 추가
- [ ] 목표가/변동폭 파싱 로직 구현
- [ ] `report_embed.py` 목표가 표시 포맷 추가
- [ ] `main.py` 시총 50위 기준 필터링
- [ ] 테스트: 삼성전자 리포트 목표가 변동 표시 확인

---

## Phase 7: 해외 시총 50위 애널리스트 리포트 (예상 작업: 2시간)

### 7.1 해외 시총 50위 기업 목록
**파일:** `config/top_companies.yaml`

```yaml
international_top50:
  - ticker: "AAPL"
    name: "Apple"
  - ticker: "MSFT"
    name: "Microsoft"
  - ticker: "NVDA"
    name: "NVIDIA"
  # ... 50개 기업
```

### 7.2 Seeking Alpha 수집기 개선
**파일:** `src/collectors/reports/seeking_alpha.py`

```python
class SeekingAlphaCollector:
    def collect_by_ticker(self, ticker: str) -> list[ContentItem]:
        """특정 티커 리포트 수집"""
        url = f"https://seekingalpha.com/symbol/{ticker}/analysis"
        # 애널리스트 등급, 목표가 변동 추출
```

### 7.3 Yahoo Finance 애널리스트 데이터 (대안)
**파일:** `src/collectors/reports/yahoo_analyst.py`

```python
class YahooAnalystCollector(BaseCollector):
    """Yahoo Finance 애널리스트 추천 수집"""

    def collect_recommendations(self, ticker: str):
        url = f"https://finance.yahoo.com/quote/{ticker}/analysis"
        # Buy/Hold/Sell 비율
        # 평균 목표가, 최고/최저 목표가
```

### 7.4 작업 체크리스트
- [ ] `top_companies.yaml`에 해외 50위 추가
- [ ] `seeking_alpha.py` 티커별 수집 개선
- [ ] `yahoo_analyst.py` 신규 수집기 (대안)
- [ ] 목표가 변동 표시 로직 (report_embed.py)
- [ ] `main.py` 통합
- [ ] 테스트: AAPL, NVDA 리포트 확인

---

## 구현 순서 권장

```
Phase 1 (커버드콜/배당) → 가장 간단, 즉시 효과
    ↓
Phase 3 (70:30 비중) → 설정 변경만
    ↓
Phase 4 (삼프로TV only) → 설정 + 간단 수정
    ↓
Phase 2 (스케줄 변경) → GitHub Actions 수정
    ↓
Phase 5 (인베스팅닷컴) → 신규 수집기, 중간 복잡도
    ↓
Phase 6 (국내 애널리스트) → 복잡, 파싱 로직 필요
    ↓
Phase 7 (해외 애널리스트) → 가장 복잡, API 제한 고려
```

---

## 의존성 다이어그램

```
                    ┌─────────────────┐
                    │  Phase 1        │
                    │  커버드콜/배당   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ↓              ↓              ↓
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │  Phase 3    │  │  Phase 4    │  │  Phase 2    │
    │  70:30 비중  │  │  삼프로TV   │  │  스케줄     │
    └─────────────┘  └─────────────┘  └──────┬──────┘
                                             │
                             ┌───────────────┘
                             ↓
                    ┌─────────────────┐
                    │  Phase 5        │
                    │  인베스팅닷컴    │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              ↓                             ↓
    ┌─────────────────┐           ┌─────────────────┐
    │  Phase 6        │           │  Phase 7        │
    │  국내 애널리스트 │           │  해외 애널리스트 │
    └─────────────────┘           └─────────────────┘
```

---

## 예상 총 작업 시간

| Phase | 예상 시간 |
|-------|----------|
| Phase 1 | 30분 |
| Phase 2 | 20분 |
| Phase 3 | 15분 |
| Phase 4 | 20분 |
| Phase 5 | 1시간 |
| Phase 6 | 2시간 |
| Phase 7 | 2시간 |
| **총합** | **약 6시간 25분** |

---

## 다음 단계

구현을 시작하시겠습니까?

```
/sc:implement phase1  # 커버드콜/배당 우선 처리
/sc:implement phase2  # 스케줄 변경
...
/sc:implement all     # 전체 구현
```
