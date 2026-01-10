"""
주말 전용 요약 모듈
토요일: 한 주간 시장 리뷰 / 일요일: 다음 주 시장 전망
"""
from datetime import datetime, timedelta
from typing import Optional

from src.collectors.base import ContentItem
from src.analyzer.groq_client import groq_client
from src.utils.logger import logger


class WeeklySummarizer:
    """토요일용 - 한 주간 시장 리뷰 요약기"""

    SYSTEM_PROMPT = """당신은 금융 시장 전문 애널리스트입니다.
한 주간의 시장 동향을 분석하여 투자자에게 명확한 인사이트를 제공합니다.
객관적인 데이터를 바탕으로 시장 흐름을 설명하고, 핵심 이벤트를 정리합니다.
응답은 항상 한국어로 작성합니다."""

    def __init__(self):
        self.client = groq_client

    def generate_weekly_review(
        self,
        news_items: list[ContentItem],
        report_items: list[ContentItem] = None,
    ) -> Optional[dict]:
        """
        한 주간 시장 리뷰 생성 (토요일용)

        Args:
            news_items: 이번 주 주요 뉴스
            report_items: 이번 주 주요 리포트

        Returns:
            {
                "week_summary": "이번 주 시장 총평",
                "major_events": ["주요 이벤트 1", ...],
                "sector_performance": "섹터별 성과 분석",
                "market_sentiment": "시장 심리 분석",
                "key_numbers": ["주요 지표/수치 1", ...],
                "lessons_learned": "이번 주 시장에서 배울 점"
            }
        """
        if not news_items:
            return None

        news_text = self._format_items_for_prompt(news_items[:25])
        reports_text = ""
        if report_items:
            reports_text = f"\n\n주요 애널리스트 리포트:\n{self._format_items_for_prompt(report_items[:10])}"

        # 이번 주 날짜 범위 계산
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=4)  # 금요일까지
        date_range = f"{week_start.strftime('%m/%d')} ~ {week_end.strftime('%m/%d')}"

        prompt = f"""다음은 이번 주({date_range}) 주요 금융/경제 뉴스입니다:

{news_text}{reports_text}

위 내용을 바탕으로 이번 한 주 시장을 리뷰해주세요. 다음 JSON 형식으로 응답:
{{
    "week_summary": "이번 주 시장의 전체적인 흐름을 3-4문장으로 총평 (지수 동향, 주요 테마 포함)",
    "major_events": ["이번 주 가장 중요했던 이벤트/뉴스 1", "이벤트 2", "이벤트 3", "이벤트 4", "이벤트 5"],
    "sector_performance": "이번 주 강세/약세 섹터 분석 (2-3문장)",
    "market_sentiment": "현재 시장 심리 분석 - 낙관/비관/중립 및 그 이유 (1-2문장)",
    "key_numbers": ["코스피 4,586pt (+2.3%)", "삼성전자 14만원 돌파", "외국인 순매수 1.2조원 등 주요 수치"],
    "lessons_learned": "이번 주 시장에서 투자자가 배울 수 있는 교훈 (1-2문장)"
}}"""

        result = self.client.generate_json(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=1500,
        )

        if result:
            logger.info("Weekly review generated successfully")
        else:
            logger.warning("Failed to generate weekly review")

        return result

    def _format_items_for_prompt(self, items: list[ContentItem]) -> str:
        """프롬프트용 아이템 포맷"""
        lines = []
        for i, item in enumerate(items, 1):
            source = item.source or "Unknown"
            title = item.title
            date_str = ""
            if item.published_at:
                date_str = f"({item.published_at.strftime('%m/%d')})"

            line = f"{i}. [{source}] {title} {date_str}"
            lines.append(line)

        return "\n".join(lines)


class WeeklyPreview:
    """일요일용 - 다음 주 시장 전망 생성기"""

    SYSTEM_PROMPT = """당신은 금융 시장 전략가입니다.
다가오는 한 주의 시장을 전망하고 투자자가 주목해야 할 이벤트와 전략을 제시합니다.
현실적이고 균형 잡힌 시각으로 분석하며, 과도한 낙관이나 비관은 피합니다.
응답은 항상 한국어로 작성합니다."""

    def __init__(self):
        self.client = groq_client

    def generate_weekly_preview(
        self,
        recent_news: list[ContentItem],
        recent_reports: list[ContentItem] = None,
    ) -> Optional[dict]:
        """
        다음 주 시장 전망 생성 (일요일용)

        Args:
            recent_news: 최근 뉴스 (시장 맥락 파악용)
            recent_reports: 최근 리포트

        Returns:
            {
                "week_outlook": "다음 주 시장 전망",
                "key_events": ["주목할 이벤트 1", ...],
                "watch_sectors": ["주목 섹터 1", ...],
                "risk_factors": ["리스크 요인 1", ...],
                "trading_strategy": "다음 주 투자 전략 제안",
                "key_levels": "주요 지수/종목 관심 가격대"
            }
        """
        if not recent_news:
            return None

        news_text = self._format_items_for_prompt(recent_news[:20])
        reports_text = ""
        if recent_reports:
            reports_text = f"\n\n최근 애널리스트 전망:\n{self._format_items_for_prompt(recent_reports[:10])}"

        # 다음 주 날짜 범위 계산
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        next_friday = next_monday + timedelta(days=4)
        date_range = f"{next_monday.strftime('%m/%d')} ~ {next_friday.strftime('%m/%d')}"

        prompt = f"""다음은 최근 주요 금융/경제 뉴스와 리포트입니다:

{news_text}{reports_text}

위 내용을 바탕으로 다음 주({date_range}) 시장을 전망해주세요. 다음 JSON 형식으로 응답:
{{
    "week_outlook": "다음 주 시장 전체 전망 (3-4문장, 예상되는 흐름과 주요 변수)",
    "key_events": ["다음 주 주목해야 할 경제 이벤트/일정 1", "이벤트 2", "이벤트 3", "이벤트 4"],
    "watch_sectors": ["다음 주 주목할 섹터/테마 1", "섹터 2", "섹터 3"],
    "risk_factors": ["다음 주 주의해야 할 리스크 요인 1", "리스크 2"],
    "trading_strategy": "다음 주 투자 전략 제안 (2-3문장, 포지션 관리, 관심 종목군 등)",
    "key_levels": "코스피/코스닥 주요 지지/저항선, 관심 종목 매수/매도 가격대 제시"
}}

참고: 예정된 경제 지표 발표, FOMC, 기업 실적 발표 일정 등을 고려해주세요."""

        result = self.client.generate_json(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=1500,
        )

        if result:
            logger.info("Weekly preview generated successfully")
        else:
            logger.warning("Failed to generate weekly preview")

        return result

    def _format_items_for_prompt(self, items: list[ContentItem]) -> str:
        """프롬프트용 아이템 포맷"""
        lines = []
        for i, item in enumerate(items, 1):
            source = item.source or "Unknown"
            title = item.title

            line = f"{i}. [{source}] {title}"
            lines.append(line)

        return "\n".join(lines)


# 전역 인스턴스
weekly_summarizer = WeeklySummarizer()
weekly_preview = WeeklyPreview()
