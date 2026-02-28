"""
애널리스트 리포트 분석기
PDF 텍스트에서 한 줄 요약, 키워드, 목표가 추출
"""
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.collectors.base import ContentItem
from src.analyzer.gemini_client import gemini_client
from src.utils.logger import logger


class ReportAnalyzer:
    """애널리스트 리포트 AI 분석기"""

    SYSTEM_PROMPT = """당신은 증권 애널리스트입니다.
리포트를 분석하여 핵심 정보를 추출합니다.
정확하고 객관적으로 분석합니다."""

    def __init__(self):
        self.client = gemini_client

    def analyze_report(self, item: ContentItem) -> Optional[dict]:
        """
        단일 리포트 분석

        Args:
            item: 리포트 ContentItem (pdf_text가 extra_data에 있어야 함)

        Returns:
            {
                "one_line_summary": "한 줄 요약",
                "keywords": ["키워드1", "키워드2", "키워드3"],
                "target_price": 150000,
                "opinion": "매수/매도/보유",
                "investment_point": "투자 포인트",
                "risk_factor": "리스크 요인",
                "confidence": 0.8
            }
        """
        pdf_text = item.extra_data.get("pdf_text")
        if not pdf_text:
            return None

        # 기존 정보 활용
        stock_name = item.extra_data.get("stock_name", "")
        existing_target = item.extra_data.get("target_price")
        existing_opinion = item.extra_data.get("opinion", "")

        # 텍스트 길이 제한 (API 토큰 절약)
        pdf_text_truncated = pdf_text[:3000]

        prompt = f"""다음 증권사 애널리스트 리포트를 분석해주세요:

종목: {stock_name}
기존 목표가: {existing_target if existing_target else '없음'}
기존 의견: {existing_opinion if existing_opinion else '없음'}

리포트 내용:
{pdf_text_truncated}

다음 JSON 형식으로 응답해주세요:
{{
    "one_line_summary": "리포트 핵심을 한 문장으로 요약 (30자 이내)",
    "keywords": ["가장 중요한 키워드 3개"],
    "target_price": 목표가 (숫자만, 없으면 null),
    "opinion": "매수/매도/보유/중립 중 하나",
    "investment_point": "핵심 투자 포인트 (한 문장)",
    "risk_factor": "주요 리스크 (한 문장, 없으면 null)",
    "confidence": 분석 확신도 (0.0~1.0)
}}

분석 시 주의사항:
- 목표가는 리포트에 명시된 것만 추출 (추정하지 말 것)
- 키워드는 종목/섹터 특화된 것 우선
- 요약은 간결하게, 핵심만"""

        try:
            result = self.client.generate_json(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=500,
            )

            if result:
                # 기존 목표가가 없고 새로 추출된 경우 업데이트
                if not existing_target and result.get("target_price"):
                    item.extra_data["target_price"] = result["target_price"]

                logger.debug(f"Report analyzed: {stock_name} - {result.get('one_line_summary', '')[:30]}")
                return result

        except Exception as e:
            logger.error(f"Failed to analyze report: {e}")

        return None

    def analyze_batch(
        self,
        items: list[ContentItem],
        max_items: int = 5,
    ) -> dict[str, dict]:
        """
        여러 리포트 배치 분석 (병렬 처리)

        Args:
            items: 리포트 ContentItem 리스트
            max_items: 최대 분석 개수

        Returns:
            {item_id: analysis_result, ...}
        """
        # PDF 텍스트가 있는 항목만 필터
        pdf_items = [
            item for item in items
            if item.extra_data.get("pdf_text")
        ][:max_items]

        if not pdf_items:
            logger.info("No reports with PDF text to analyze")
            return {}

        logger.info(f"Analyzing {len(pdf_items)} reports with AI")
        results = {}

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self.analyze_report, item): item
                for item in pdf_items
            }

            for future in as_completed(futures):
                item = futures[future]
                try:
                    analysis = future.result()
                    if analysis:
                        results[item.id] = analysis
                        # extra_data에 분석 결과 저장
                        item.extra_data["ai_analysis"] = analysis
                except Exception as e:
                    logger.debug(f"Analysis failed for {item.title[:30]}: {e}")

        logger.info(f"Successfully analyzed {len(results)} reports")
        return results

    def generate_reports_insight(
        self,
        items: list[ContentItem],
        max_items: int = 10,
    ) -> Optional[dict]:
        """
        여러 리포트 종합 인사이트 생성

        Returns:
            {
                "market_view": "전체 시장 전망",
                "top_picks": ["추천 종목1", "추천 종목2"],
                "sector_focus": ["주목 섹터1", "섹터2"],
                "consensus": "애널리스트 컨센서스"
            }
        """
        if not items:
            return None

        # 리포트 정보 텍스트 생성
        report_lines = []
        for item in items[:max_items]:
            stock = item.extra_data.get("stock_name", "")
            target = item.extra_data.get("target_price")
            opinion = item.extra_data.get("opinion", "")
            analysis = item.extra_data.get("ai_analysis", {})
            summary = analysis.get("one_line_summary", item.title[:50])

            line = f"- {stock or item.title[:20]}"
            if opinion:
                line += f" ({opinion})"
            if target:
                line += f" 목표가 {target:,}원"
            line += f": {summary}"
            report_lines.append(line)

        reports_text = "\n".join(report_lines)

        prompt = f"""다음 증권사 애널리스트 리포트들을 종합 분석해주세요:

{reports_text}

다음 JSON 형식으로 응답해주세요:
{{
    "market_view": "전체적인 시장 전망 요약 (1-2문장)",
    "top_picks": ["가장 주목할 종목 3개"],
    "sector_focus": ["주목할 섹터/테마 2개"],
    "consensus": "애널리스트들의 전반적인 의견/컨센서스 (1문장)"
}}"""

        try:
            result = self.client.generate_json(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=500,
            )

            if result:
                logger.info("Reports insight generated successfully")
                return result

        except Exception as e:
            logger.error(f"Failed to generate reports insight: {e}")

        return None


# 전역 인스턴스
report_analyzer = ReportAnalyzer()
