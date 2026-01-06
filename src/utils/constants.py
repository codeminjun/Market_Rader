"""
공통 상수 및 유틸리티
중복 코드 제거를 위한 중앙 집중식 관리
"""
from src.collectors.base import Priority


# ============================================================
# 우선순위 매핑 (3곳에서 중복 사용되던 것 통합)
# ============================================================
PRIORITY_MAP = {
    "high": Priority.HIGH,
    "medium": Priority.MEDIUM,
    "low": Priority.LOW,
}


def get_priority_from_string(priority_str: str) -> Priority:
    """문자열을 Priority enum으로 변환"""
    return PRIORITY_MAP.get(priority_str.lower(), Priority.MEDIUM)


# ============================================================
# 뉴스 수집/표시 설정
# ============================================================
class NewsSettings:
    """뉴스 관련 설정 상수"""
    # 국내/해외 비중 (70:30)
    KOREAN_RATIO = 0.7
    INTL_RATIO = 0.3

    # 오전 7시 (전체 콘텐츠) - 총 뉴스 수 기준
    TOTAL_NEWS_COUNT = 20
    MAX_KOREAN_NEWS = 14   # 20 * 0.7
    MAX_INTL_NEWS = 6      # 20 * 0.3

    # 오후 12시 (뉴스 위주) - 한국 뉴스 중심 최대 15개
    NOON_MAX_KOREAN_NEWS = 15
    NOON_MAX_INTL_NEWS = 0   # 해외 뉴스 제외

    # 리포트/유튜브
    MAX_REPORTS = 10
    MAX_YOUTUBE_KOREAN = 5
    MAX_YOUTUBE_INTL = 5


# ============================================================
# 중요도 점수 임계값
# ============================================================
class ImportanceThresholds:
    """중요도 점수 기준"""
    # 우선순위 결정 기준
    HIGH_PRIORITY = 0.7
    MEDIUM_PRIORITY = 0.5

    # 필터링 기준
    MIN_SCORE = 0.3

    # 키워드 가중치
    COVERED_CALL_WEIGHT = 0.30   # 커버드콜/배당
    INDUSTRY_WEIGHT = 0.20       # 산업
    HIGH_KEYWORD_WEIGHT = 0.15   # 중요 키워드
    MEDIUM_KEYWORD_WEIGHT = 0.08 # 일반 키워드
    HIGH_PRIORITY_WEIGHT = 0.10  # HIGH priority 보너스
    LOW_PRIORITY_WEIGHT = -0.10  # LOW priority 페널티


# ============================================================
# Discord Embed 설정
# ============================================================
class EmbedColors:
    """Discord Embed 색상"""
    NEWS_KOREAN = "e74c3c"   # 빨강
    NEWS_INTL = "3498db"     # 파랑
    REPORTS = "9b59b6"       # 보라
    YOUTUBE = "e74c3c"       # 빨강 (YouTube)
    DEFAULT = "3498db"       # 파랑


# ============================================================
# 요청 설정
# ============================================================
class RequestSettings:
    """HTTP 요청 설정"""
    DEFAULT_TIMEOUT = 10
    RSS_TIMEOUT = 15
    API_TIMEOUT = 30

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )


# ============================================================
# 정규표현식 패턴 (사전 컴파일)
# ============================================================
import re

# HTML 태그 제거용
HTML_TAG_PATTERN = re.compile(r'<[^>]+>')

# 티커 추출용
TICKER_PATTERNS = {
    "dollar": re.compile(r'\$([A-Z]{1,5})\b'),
    "paren": re.compile(r'\(([A-Z]{1,5})\)'),
    "exchange": re.compile(r'(?:NASDAQ|NYSE|AMEX):([A-Z]{1,5})\b'),
}

# 종목코드 추출용 (한국)
STOCK_CODE_PATTERN = re.compile(r'code=(\d{6})')


def strip_html(text: str) -> str:
    """HTML 태그 제거 (사전 컴파일된 패턴 사용)"""
    return HTML_TAG_PATTERN.sub('', text).strip()


def extract_ticker(text: str) -> str | None:
    """텍스트에서 티커 심볼 추출"""
    for pattern in TICKER_PATTERNS.values():
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None
