"""
시장 브리핑 생성기
장 마감 리뷰 및 아침 전략 브리핑을 AI가 생성
실제 뉴스/리포트 내용을 기반으로 작성
"""
from typing import Optional
from dataclasses import dataclass, field

from src.collectors.base import ContentItem
from src.analyzer.gemini_client import gemini_client
from src.utils.logger import logger


@dataclass
class MarketBriefing:
    """시장 브리핑 데이터"""
    greeting: str           # 인사말
    summary: str            # 핵심 요약 (2-3문장)
    key_points: list[str]   # 주요 포인트 (3-5개)
    action_items: list[str] # 액션 아이템 / 주의사항 (2-3개)
    closing: str            # 마무리 멘트
    mood: str               # 시장 분위기 (positive/neutral/negative)
    sources: list[str] = field(default_factory=list)  # 참고 출처


class MarketBriefingGenerator:
    """시장 브리핑 생성기 (실제 데이터 기반)"""

    SYSTEM_PROMPT = """당신은 친근한 주식 시장 애널리스트예요.
제공된 실제 뉴스와 리포트 데이터만을 기반으로 시장 정보를 전달해요.

=== 작성 스타일 (토스 보이스톤) ===
1. 해요체 사용
   - 모든 문장을 '~해요', '~이에요' 형태로 끝내세요
   - 예: "상승했어요", "주목할 만해요", "좋은 신호예요"

2. 캐주얼하고 친근하게
   - "~하시겠어요?" → "~하면 좋아요"
   - "~되었습니다" → "~됐어요" 또는 "~했어요"
   - "~계시다" → "~있어요"
   - 과도한 경어 사용하지 않기

3. 능동적으로 말하기
   - "상승이 예상됩니다" → "상승할 것 같아요"
   - "확인되었습니다" → "확인했어요"

4. 긍정적으로 말하기
   - "~할 수 없어요" → "~하면 할 수 있어요"
   - 에러나 부정적 상황도 해결 방향 제시

=== 절대 준수 규칙 ===
1. 데이터 정확성
   - 제공된 데이터에 있는 내용만 언급하세요
   - 숫자는 제공된 값을 그대로 사용하세요
   - 절대로 숫자를 추측하지 마세요

2. 출처 명시 필수
   - 모든 정보에는 반드시 출처를 괄호로 표시하세요
   - 예: "삼성전자 실적이 좋아요 (한국경제)"

3. 금지 사항
   - 제공되지 않은 회사/종목 언급 금지
   - 위 데이터에 없는 숫자 사용 금지"""

    def __init__(self):
        self.client = gemini_client

    def generate_closing_review(
        self,
        news_items: list[ContentItem],
        report_items: list[ContentItem] = None,
    ) -> Optional[MarketBriefing]:
        """
        장 마감 리뷰 생성 (오후 5시용)
        실제 뉴스/리포트 내용을 분석하여 정성적 리뷰 작성
        (수치는 별도 market_close_embed에서 크롤링 데이터로 직접 표시)

        Args:
            news_items: 오늘의 주요 뉴스
            report_items: 오늘의 리포트 (AI 분석 포함)

        Returns:
            MarketBriefing 객체
        """
        if not news_items:
            return None

        # 실제 데이터 기반 텍스트 생성
        news_text, news_sources = self._format_news_detailed(news_items[:10])
        report_text, report_sources = self._format_reports_detailed(report_items[:5]) if report_items else ("", [])

        all_sources = news_sources + report_sources

        prompt = f"""아래 제공된 실제 데이터만을 기반으로 오늘의 장 마감 리뷰를 작성해주세요.
모든 문장은 '해요체'로 친근하게 작성하세요.

=== 오늘의 주요 뉴스 (실제 기사) ===
{news_text}

=== 애널리스트 리포트 분석 결과 ===
{report_text if report_text else "리포트 없음"}

위 데이터를 종합 분석하여 다음 JSON 형식으로 응답해주세요:
{{
    "greeting": "오늘 장 마감 인사 (해요체, 친근하게, 1문장). 예: '오늘 장이 마감됐어요.'",
    "summary": "오늘 시장 핵심 흐름 요약 (해요체, 2-3문장). 수치 없이 '상승했어요', '하락했어요' 같은 정성적 표현만 사용하세요.",
    "key_points": ["핵심 포인트 3-5개 (해요체, 출처 명시). 예: '반도체 업황이 좋아지고 있어요 (한경)'"],
    "action_items": ["내일 주목할 점 2-3개 (해요체). 예: '내일은 ~를 눈여겨보면 좋아요'"],
    "closing": "마무리 인사 (해요체, 1문장). 예: '내일도 좋은 하루 보내세요!'",
    "mood": "positive/neutral/negative"
}}

=== 절대 준수 사항 ===
1. 해요체 필수: 모든 문장을 '~해요', '~이에요', '~예요' 형태로 끝내세요
2. 🌟 우선 반영: "사용자 관심 뉴스" 섹션 기사를 반드시 summary와 key_points에 포함하세요
3. 수치 금지: 코스피/코스닥 지수, 환율, 등락률 등 구체적 숫자를 절대 쓰지 마세요. 수치는 별도로 표시돼요.
4. 출처 필수: 모든 정보에 출처를 괄호로 표시하세요
5. 금지: 위 데이터에 없는 정보 사용 금지"""

        try:
            result = self.client.generate_json(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=1000,
            )

            if result:
                return MarketBriefing(
                    greeting=result.get("greeting", "오늘 하루도 수고하셨습니다."),
                    summary=result.get("summary", ""),
                    key_points=result.get("key_points", []),
                    action_items=result.get("action_items", []),
                    closing=result.get("closing", "내일도 좋은 하루 되세요!"),
                    mood=result.get("mood", "neutral"),
                    sources=all_sources[:5],  # 상위 5개 출처
                )

        except Exception as e:
            logger.error(f"Failed to generate closing review: {e}")

        return None

    def generate_morning_strategy(
        self,
        news_items: list[ContentItem],
        morning_briefs: list[ContentItem] = None,
        report_items: list[ContentItem] = None,
        intl_news_items: list[ContentItem] = None,
    ) -> Optional[MarketBriefing]:
        """
        아침 전략 브리핑 생성 (오전 7시용)
        Morning Brief + 뉴스 + 리포트 + 해외뉴스를 종합 분석

        Args:
            news_items: 전일/금일 주요 뉴스 (국내)
            morning_briefs: Morning Brief 내용 (OCR 텍스트 포함)
            report_items: 최신 리포트 (AI 분석 포함)
            intl_news_items: 해외 주요 뉴스 (AI가 한줄 요약으로 정리)

        Returns:
            MarketBriefing 객체
        """
        if not news_items and not morning_briefs:
            return None

        # 실제 데이터 기반 텍스트 생성
        brief_text, brief_sources = self._format_morning_briefs_detailed(morning_briefs[:3]) if morning_briefs else ("", [])
        news_text, news_sources = self._format_news_detailed(news_items[:10]) if news_items else ("", [])
        report_text, report_sources = self._format_reports_detailed(report_items[:5]) if report_items else ("", [])
        intl_text, intl_sources = self._format_news_detailed(intl_news_items[:6]) if intl_news_items else ("", [])

        all_sources = brief_sources + news_sources + intl_sources + report_sources

        prompt = f"""아래 제공된 실제 데이터만을 기반으로 오늘의 장 전략 브리핑을 작성해주세요.
모든 문장은 '해요체'로 친근하게 작성하세요.

=== 증권사 Morning Brief (전문가 분석) ===
{brief_text if brief_text else "Morning Brief 없음"}

=== 국내 주요 뉴스 (실제 기사) ===
{news_text if news_text else "뉴스 없음"}

=== 해외 주요 뉴스 ===
{intl_text if intl_text else "해외 뉴스 없음"}

=== 애널리스트 리포트 분석 결과 ===
{report_text if report_text else "리포트 없음"}

위 데이터를 종합 분석하여 다음 JSON 형식으로 응답해주세요:
{{
    "greeting": "아침 인사 + 오늘 장 전망 (해요체, 1문장). 예: '좋은 아침이에요! 오늘 장은 ~할 것 같아요.'",
    "summary": "오늘 장 전망 요약 (해요체, 2-3문장). 해외 시장 동향도 한줄로 녹여주세요.",
    "key_points": ["핵심 포인트 3-5개 (해요체, 출처 명시). 예: '반도체 업황이 좋아지고 있어요 (SK증권)'"],
    "action_items": ["오늘 체크할 것 2-3개 (해요체). 예: '~를 눈여겨보면 좋아요'"],
    "closing": "응원 메시지 (해요체, 1문장). 예: '오늘도 좋은 투자 하세요!'",
    "mood": "positive/neutral/negative"
}}

=== 절대 준수 사항 ===
1. 해요체 필수: 모든 문장을 '~해요', '~이에요', '~예요' 형태로 끝내세요
2. 🌟 우선 반영: "사용자 관심 뉴스" 섹션 기사를 반드시 summary와 key_points에 포함하세요
3. Morning Brief 우선: Morning Brief 내용이 있다면 가장 우선 반영하세요
4. 해외 뉴스 활용: 해외 주요 뉴스를 전략에 자연스럽게 녹여주세요 (한줄 요약 형태)
5. 출처 필수: 모든 정보에 출처를 괄호로 표시하세요
6. 금지: 위 데이터에 없는 정보/숫자 사용 금지"""

        try:
            result = self.client.generate_json(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=1000,
            )

            if result:
                return MarketBriefing(
                    greeting=result.get("greeting", "좋은 아침입니다!"),
                    summary=result.get("summary", ""),
                    key_points=result.get("key_points", []),
                    action_items=result.get("action_items", []),
                    closing=result.get("closing", "오늘도 좋은 투자 되세요!"),
                    mood=result.get("mood", "neutral"),
                    sources=all_sources[:5],
                )

        except Exception as e:
            logger.error(f"Failed to generate morning strategy: {e}")

        return None

    def _format_news_detailed(self, items: list[ContentItem]) -> tuple[str, list[str]]:
        """
        뉴스 항목을 상세 텍스트로 변환 (제목 + 내용 + 우선순위 정보)

        Returns:
            (텍스트, 출처 리스트)
        """
        lines = []
        sources = []
        priority_items = []  # 우선 기자/키워드 기사

        for i, item in enumerate(items, 1):
            source = item.source.split("(")[0].strip() if "(" in item.source else item.source
            sources.append(source)

            # 기본 정보
            line = f"{i}. [{source}] {item.title}"

            # 기자명 추가
            journalist = item.extra_data.get("journalist", "")
            if journalist:
                line += f" (기자: {journalist})"

            # 요약/설명이 있으면 추가
            description = item.description or item.summary
            if description:
                # 너무 길면 자르기
                desc_clean = description.replace("\n", " ").strip()
                if len(desc_clean) > 200:
                    desc_clean = desc_clean[:200] + "..."
                line += f"\n   내용: {desc_clean}"

            # 우선 기자 표시
            if item.extra_data.get("is_priority_journalist_article"):
                priority_journalist = item.extra_data.get("priority_journalist", {})
                line += f"\n   ⭐ [우선 기자: {priority_journalist.get('name', '')} - {priority_journalist.get('affiliation', '')}]"
                priority_items.append(f"우선 기자 {priority_journalist.get('name', '')}의 기사: {item.title}")

            # 우선 키워드 표시
            if item.extra_data.get("is_priority_keyword_match"):
                keywords = item.extra_data.get("priority_keywords", [])
                line += f"\n   🔑 [관심 키워드: {', '.join(keywords)}]"
                priority_items.append(f"관심 키워드({', '.join(keywords)}) 기사: {item.title}")

            # 중요도 점수
            if item.importance_score > 0.6:
                line += f"\n   [중요도: 높음]"

            lines.append(line)

        # 우선 항목이 있으면 상단에 요약 추가
        result_lines = []
        if priority_items:
            result_lines.append("=== 🌟 사용자 관심 뉴스 (우선 반영 필수) ===")
            for pi in priority_items[:5]:
                result_lines.append(f"• {pi}")
            result_lines.append("")

        result_lines.append("=== 전체 뉴스 목록 ===")
        result_lines.extend(lines)

        return "\n\n".join(result_lines), sources

    def _format_reports_detailed(self, items: list[ContentItem]) -> tuple[str, list[str]]:
        """
        리포트 항목을 상세 텍스트로 변환 (AI 분석 결과 + 우선순위 정보 포함)

        Returns:
            (텍스트, 출처 리스트)
        """
        lines = []
        sources = []
        priority_items = []

        for i, item in enumerate(items, 1):
            stock = item.extra_data.get("stock_name", "")
            broker = item.extra_data.get("broker", item.source)
            opinion = item.extra_data.get("opinion", "")
            target = item.extra_data.get("target_price")
            ai_analysis = item.extra_data.get("ai_analysis", {})

            sources.append(f"{broker} - {stock}" if stock else broker)

            # 기본 정보
            header = f"{i}. [{broker}]"
            if stock:
                header += f" {stock}"
            if opinion:
                header += f" ({opinion})"
            if target:
                header += f" 목표가 {target:,}원"

            lines.append(header)

            # 우선 애널리스트 표시
            if item.extra_data.get("is_priority_analyst_article"):
                priority_analyst = item.extra_data.get("priority_analyst", {})
                lines.append(f"   ⭐ [우선 애널리스트: {priority_analyst.get('name', '')} - {priority_analyst.get('affiliation', '')}]")
                priority_items.append(f"우선 애널리스트 {priority_analyst.get('name', '')}의 리포트: {stock or item.title}")

            # 우선 소스 표시
            if item.extra_data.get("is_priority_source"):
                priority_source = item.extra_data.get("priority_report_source", {})
                lines.append(f"   ⭐ [우선 소스: {priority_source.get('name', '')}]")
                priority_items.append(f"우선 소스 {priority_source.get('name', '')} 리포트")

            # AI 분석 결과가 있으면 상세 추가
            if ai_analysis:
                if ai_analysis.get("one_line_summary"):
                    lines.append(f"   📝 요약: {ai_analysis['one_line_summary']}")
                if ai_analysis.get("investment_point"):
                    lines.append(f"   💡 투자포인트: {ai_analysis['investment_point']}")
                if ai_analysis.get("risk_factor"):
                    lines.append(f"   ⚠️ 리스크: {ai_analysis['risk_factor']}")
                if ai_analysis.get("keywords"):
                    keywords = ", ".join(ai_analysis["keywords"][:3])
                    lines.append(f"   🏷️ 키워드: {keywords}")
            else:
                # AI 분석 없으면 제목만
                lines.append(f"   제목: {item.title}")

            lines.append("")  # 빈 줄

        # 우선 항목이 있으면 상단에 요약 추가
        result_lines = []
        if priority_items:
            result_lines.append("=== 🌟 사용자 관심 리포트 (우선 반영 필수) ===")
            for pi in priority_items[:3]:
                result_lines.append(f"• {pi}")
            result_lines.append("")

        result_lines.extend(lines)
        return "\n".join(result_lines), sources

    def _format_morning_briefs_detailed(self, items: list[ContentItem]) -> tuple[str, list[str]]:
        """
        Morning Brief를 상세 텍스트로 변환 (OCR 전문 포함)

        Returns:
            (텍스트, 출처 리스트)
        """
        lines = []
        sources = []

        for i, item in enumerate(items, 1):
            source = item.source
            sources.append(source)

            lines.append(f"=== {i}. {source} Morning Brief ===")

            # OCR 텍스트가 있으면 상당 부분 포함
            ocr_text = item.extra_data.get("ocr_text", "")
            if ocr_text:
                # OCR 텍스트 정리 (최대 1000자)
                ocr_clean = ocr_text.replace("\n\n", "\n").strip()
                if len(ocr_clean) > 1000:
                    ocr_clean = ocr_clean[:1000] + "..."
                lines.append(ocr_clean)
            else:
                lines.append(f"제목: {item.title}")

            lines.append("")  # 빈 줄

        return "\n".join(lines), sources



# 전역 인스턴스
market_briefing_generator = MarketBriefingGenerator()
