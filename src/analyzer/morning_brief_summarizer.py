"""
Morning Brief 요약기
증권사 Morning Brief PDF 내용을 요약
"""
from typing import Optional

from src.collectors.base import ContentItem
from src.analyzer.groq_client import groq_client
from src.utils.logger import logger


class MorningBriefSummarizer:
    """Morning Brief 요약기"""

    SYSTEM_PROMPT = """당신은 금융 애널리스트입니다.
증권사 Morning Brief 리포트의 핵심 내용을 요약합니다.
투자자에게 유용한 인사이트를 간결하게 전달합니다."""

    def summarize_morning_brief(self, item: ContentItem) -> Optional[dict]:
        """
        Morning Brief 요약

        Args:
            item: Morning Brief ContentItem (pdf_text 포함)

        Returns:
            {
                "summary": "전체 요약",
                "key_points": ["핵심 포인트 1", "핵심 포인트 2", ...],
                "market_outlook": "시장 전망",
                "attention_stocks": ["주목 종목 1", "주목 종목 2", ...],
                "insights": "투자 인사이트"
            }
        """
        pdf_text = item.extra_data.get("pdf_text", "")
        if not pdf_text:
            logger.warning(f"No PDF text for {item.title}")
            return None

        # 텍스트가 너무 길면 잘라내기
        max_chars = 8000
        if len(pdf_text) > max_chars:
            pdf_text = pdf_text[:max_chars]

        prompt = f"""다음은 {item.source}의 Morning Brief 리포트 내용입니다:

---
{pdf_text}
---

위 내용을 분석하여 다음 JSON 형식으로 요약해주세요:

{{
    "summary": "전체 내용 요약 (3-4문장)",
    "key_points": ["핵심 포인트 1", "핵심 포인트 2", "핵심 포인트 3"],
    "market_outlook": "오늘 시장 전망 (1-2문장)",
    "attention_stocks": ["주목할 종목/섹터 1", "주목할 종목/섹터 2"],
    "insights": "투자자를 위한 핵심 인사이트 (1-2문장)"
}}

요약 시 주의사항:
1. 구체적인 수치와 종목명을 포함
2. 투자자 관점에서 중요한 정보 위주
3. 간결하고 명확하게 작성"""

        try:
            result = groq_client.generate_json(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=1000,
            )

            if result:
                logger.info(f"Summarized Morning Brief: {item.title}")
                return result

        except Exception as e:
            logger.error(f"Failed to summarize Morning Brief: {e}")

        return None

    def analyze_all_briefs(self, items: list[ContentItem]) -> list[ContentItem]:
        """
        모든 Morning Brief 개별 분석 후 결과를 extra_data에 저장

        Args:
            items: Morning Brief ContentItem 리스트

        Returns:
            분석 결과가 추가된 items 리스트
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not items:
            return items

        def analyze_single(item: ContentItem) -> tuple[ContentItem, Optional[dict]]:
            result = self.summarize_morning_brief(item)
            return item, result

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(analyze_single, item): item for item in items}

            for future in as_completed(futures):
                try:
                    item, analysis = future.result()
                    if analysis:
                        item.extra_data["ai_analysis"] = analysis
                        logger.info(f"Analyzed Morning Brief: {item.source}")
                except Exception as e:
                    logger.debug(f"Morning Brief analysis failed: {e}")

        analyzed_count = sum(1 for item in items if item.extra_data.get("ai_analysis"))
        logger.info(f"Analyzed {analyzed_count}/{len(items)} Morning Briefs")
        return items

    def summarize_multiple_briefs(self, items: list[ContentItem]) -> Optional[dict]:
        """
        여러 Morning Brief를 종합 요약

        Args:
            items: Morning Brief ContentItem 리스트

        Returns:
            {
                "overall_summary": "종합 요약",
                "common_themes": ["공통 테마 1", "공통 테마 2"],
                "market_consensus": "시장 컨센서스",
                "key_recommendations": ["주요 추천 사항"]
            }
        """
        if not items:
            return None

        # 각 브리프의 텍스트 수집
        briefs_text = []
        for item in items[:3]:  # 최대 3개
            pdf_text = item.extra_data.get("pdf_text", "")
            if pdf_text:
                # 각 브리프당 최대 3000자
                brief_excerpt = pdf_text[:3000]
                briefs_text.append(f"[{item.source}]\n{brief_excerpt}")

        if not briefs_text:
            return None

        combined_text = "\n\n---\n\n".join(briefs_text)

        prompt = f"""다음은 오늘의 증권사 Morning Brief들입니다:

{combined_text}

위 내용을 종합 분석하여 다음 JSON 형식으로 요약해주세요:

{{
    "overall_summary": "오늘의 시장 종합 요약 (3-4문장)",
    "common_themes": ["증권사들이 공통으로 언급하는 테마 1", "테마 2"],
    "market_consensus": "시장 컨센서스/전망 (2문장)",
    "key_recommendations": ["핵심 투자 포인트 1", "핵심 투자 포인트 2", "핵심 투자 포인트 3"]
}}"""

        try:
            result = groq_client.generate_json(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=800,
            )

            if result:
                logger.info(f"Generated combined Morning Brief summary from {len(items)} briefs")
                return result

        except Exception as e:
            logger.error(f"Failed to generate combined summary: {e}")

        return None


# 전역 인스턴스
morning_brief_summarizer = MorningBriefSummarizer()
