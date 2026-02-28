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
# 스케줄 설정
# ============================================================
class ScheduleSettings:
    """스케줄 관련 설정 (main.py에서 하드코딩된 값 외부화)"""
    # 오전 스케줄 (전일 마감 후 뉴스) - 전일 17:00 ~ 당일 07:00
    MORNING_START_HOUR = 6
    MORNING_END_HOUR = 8
    MORNING_TITLE = "📰 전일 마감 후 주요 뉴스"

    # 점심 스케줄 (오전장 뉴스) - 당일 07:00 ~ 12:00
    NOON_START_HOUR = 11
    NOON_END_HOUR = 13
    NOON_TITLE = "📰 오전장 주요 뉴스"

    # 오후 스케줄 (장마감 뉴스) - 당일 12:00 ~ 17:00
    AFTERNOON_START_HOUR = 16
    AFTERNOON_END_HOUR = 18
    AFTERNOON_TITLE = "📰 장마감 주요 뉴스"

    # 수동 실행
    MANUAL_TITLE = "📰 주식 뉴스 브리핑"

    # 주말 스케줄
    SATURDAY_TITLE = "📊 이번 주 시장 리뷰"  # 토요일: 주간 리뷰 (1PM KST 1회)
    SUNDAY_TITLE = "🔮 다음 주 시장 전망"    # 일요일: 주간 전망 (1PM KST 1회)
    WEEKEND_HOUR = 13  # 주말 알림 시간 (토/일 오후 1시)

    # 휴장일 스케줄
    HOLIDAY_TITLE = "🏖️ 시장 휴일 안내"


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

    # 오후 5시 (장마감 뉴스) - 한국 뉴스 10개
    AFTERNOON_MAX_KOREAN_NEWS = 10
    AFTERNOON_MAX_INTL_NEWS = 0  # 해외 뉴스 제외

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


# ============================================================
# Discord Embed 공통 유틸리티
# ============================================================
class EmbedUtils:
    """Discord Embed 공통 유틸리티 (중복 코드 통합)"""

    # 제목/설명 길이 제한 (Discord API 한계)
    MAX_TITLE_LENGTH = 250
    MAX_DESCRIPTION_LENGTH = 4096
    MAX_FIELD_VALUE_LENGTH = 1024

    @staticmethod
    def get_importance_emoji(score: float, is_covered_call: bool = False) -> str:
        """중요도 점수에 따른 이모지 (통합 버전)"""
        if is_covered_call:
            return "💰🔥"  # 배당/커버드콜 강조
        if score >= 0.8:
            return "🔴"  # 긴급
        elif score >= 0.6:
            return "🟠"  # 중요
        elif score >= 0.4:
            return "🟡"  # 일반
        else:
            return "⚪"  # 참고

    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """텍스트를 지정된 길이로 자름"""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix

    @staticmethod
    def get_priority_display(priority: "Priority", style: str = "stars") -> str:
        """우선순위 표시 (스타일 통합)

        Args:
            priority: Priority enum
            style: "stars" | "emoji" | "text"
        """
        from src.collectors.base import Priority

        if style == "stars":
            if priority == Priority.HIGH:
                return "⭐⭐⭐"
            elif priority == Priority.MEDIUM:
                return "⭐⭐"
            else:
                return "⭐"
        elif style == "emoji":
            if priority == Priority.HIGH:
                return "⭐"
            elif priority == Priority.MEDIUM:
                return "☆"
            else:
                return "·"
        elif style == "text":
            if priority == Priority.HIGH:
                return "⭐⭐⭐ [필수 시청]"
            elif priority == Priority.MEDIUM:
                return "⭐⭐ [추천]"
            else:
                return "⭐ [참고]"
        return ""
