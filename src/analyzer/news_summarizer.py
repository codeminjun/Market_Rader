"""
뉴스 요약 모듈
AI를 사용한 뉴스 요약 및 투자 인사이트 생성
"""
from typing import Optional

from src.collectors.base import ContentItem
from src.analyzer.groq_client import groq_client
from src.utils.logger import logger


class NewsSummarizer:
    """뉴스 요약기"""

    SYSTEM_PROMPT = """당신은 금융 전문가이자 뉴스 분석가입니다.
주어진 뉴스 목록을 분석하여 투자자에게 유용한 요약과 인사이트를 제공합니다.
응답은 항상 한국어로 작성합니다."""

    def __init__(self):
        self.client = groq_client

    def summarize_news_batch(
        self,
        items: list[ContentItem],
        max_items: int = 20,
    ) -> Optional[dict]:
        """
        뉴스 배치 요약

        Args:
            items: 뉴스 항목 리스트
            max_items: 최대 분석 항목 수

        Returns:
            {
                "summary": "전체 요약",
                "key_points": ["핵심 포인트 1", ...],
                "market_impact": "시장 영향 분석",
                "investment_insight": "투자 인사이트"
            }
        """
        if not items:
            return None

        # 뉴스 목록 텍스트 생성
        news_text = self._format_news_for_prompt(items[:max_items])

        prompt = f"""다음은 오늘의 주요 금융/경제 뉴스 목록입니다:

{news_text}

위 뉴스들을 분석하여 다음 JSON 형식으로 응답해주세요:
{{
    "summary": "전체 뉴스의 핵심 내용을 2-3문장으로 요약",
    "key_points": ["핵심 포인트 1", "핵심 포인트 2", "핵심 포인트 3"],
    "market_impact": "이 뉴스들이 주식 시장에 미칠 영향 분석 (1-2문장)",
    "investment_insight": "투자자가 주목해야 할 점과 조언 (1-2문장)"
}}"""

        result = self.client.generate_json(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=1024,
        )

        if result:
            logger.info("News batch summary generated successfully")
        else:
            logger.warning("Failed to generate news batch summary")

        return result

    def summarize_single_news(
        self,
        item: ContentItem,
    ) -> Optional[str]:
        """
        단일 뉴스 요약

        Args:
            item: 뉴스 항목

        Returns:
            요약 텍스트
        """
        content = item.description or item.title

        prompt = f"""다음 뉴스를 1-2문장으로 간결하게 요약해주세요:

제목: {item.title}
내용: {content}

핵심 내용만 간결하게 한국어로 요약:"""

        result = self.client.generate(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=200,
            temperature=0.5,
        )

        return result

    def _format_news_for_prompt(self, items: list[ContentItem]) -> str:
        """프롬프트용 뉴스 목록 포맷"""
        lines = []
        for i, item in enumerate(items, 1):
            source = item.source or "Unknown"
            title = item.title
            desc = item.description[:200] if item.description else ""

            line = f"{i}. [{source}] {title}"
            if desc:
                line += f"\n   요약: {desc}"
            lines.append(line)

        return "\n\n".join(lines)


class ReportSummarizer:
    """애널리스트 리포트 요약기"""

    SYSTEM_PROMPT = """당신은 증권 애널리스트 리포트 전문가입니다.
리포트의 핵심 내용을 투자자가 이해하기 쉽게 요약합니다.
응답은 항상 한국어로 작성합니다."""

    def __init__(self):
        self.client = groq_client

    def summarize_reports(
        self,
        items: list[ContentItem],
        max_items: int = 10,
    ) -> Optional[dict]:
        """
        리포트 배치 요약

        Returns:
            {
                "summary": "전체 요약",
                "recommendations": ["추천 사항 1", ...],
                "sectors_focus": ["주목 섹터 1", ...]
            }
        """
        if not items:
            return None

        reports_text = self._format_reports_for_prompt(items[:max_items])

        prompt = f"""다음은 최신 증권사 애널리스트 리포트 목록입니다:

{reports_text}

위 리포트들을 분석하여 다음 JSON 형식으로 응답해주세요:
{{
    "summary": "리포트들의 전체적인 시장 전망 요약 (2-3문장)",
    "recommendations": ["주요 투자 추천사항 1", "추천사항 2", "추천사항 3"],
    "sectors_focus": ["주목해야 할 섹터/테마 1", "섹터 2"]
}}"""

        result = self.client.generate_json(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=800,
        )

        return result

    def _format_reports_for_prompt(self, items: list[ContentItem]) -> str:
        """프롬프트용 리포트 목록 포맷"""
        lines = []
        for i, item in enumerate(items, 1):
            source = item.source or "Unknown"
            title = item.title
            extra = item.extra_data

            line = f"{i}. [{source}] {title}"
            if extra.get("stock_name"):
                line = f"{i}. [{source}] [{extra['stock_name']}] {title}"

            lines.append(line)

        return "\n".join(lines)


# 전역 인스턴스
news_summarizer = NewsSummarizer()
report_summarizer = ReportSummarizer()
