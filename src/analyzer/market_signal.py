"""
AI 시장 시그널 분석기
뉴스 기반 투자 시그널 생성 (Bullish/Bearish/Neutral)
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from src.collectors.base import ContentItem
from src.analyzer.gemini_client import gemini_client
from src.utils.logger import logger


class Signal(Enum):
    """투자 시그널"""
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


@dataclass
class MarketSignal:
    """시장 시그널 데이터"""
    signal: Signal
    confidence: float  # 0.0 ~ 1.0
    reasoning: str
    affected_sectors: list[str]
    key_tickers: list[str]


class MarketSignalAnalyzer:
    """AI 기반 시장 시그널 분석기"""

    SYSTEM_PROMPT = """당신은 월스트리트 퀀트 애널리스트입니다.
뉴스를 분석하여 시장 영향과 투자 시그널을 평가합니다.
객관적이고 데이터 기반으로 분석하며, 낙관 편향을 경계합니다.

중요 원칙:
- 긍정적 뉴스가 많더라도 모든 섹터를 "bullish"로 평가하지 마세요
- 각 섹터를 독립적으로 분석하고, 해당 섹터의 뉴스 내용만으로 판단하세요
- 명확한 호재/악재가 없는 섹터는 반드시 "neutral"로 평가하세요
- 리스크 요인이 언급된 섹터는 하락 시그널을 고려하세요"""

    # 유효한 섹터 시그널 값
    VALID_SECTOR_SIGNALS = {"bullish", "neutral", "bearish"}

    # 시그널별 이모지
    SIGNAL_EMOJI = {
        Signal.STRONG_BULLISH: "🚀",
        Signal.BULLISH: "📈",
        Signal.NEUTRAL: "➡️",
        Signal.BEARISH: "📉",
        Signal.STRONG_BEARISH: "💥",
    }

    # 시그널별 색상 (Discord Embed용, 16진수)
    SIGNAL_COLOR = {
        Signal.STRONG_BULLISH: 0x00FF00,  # 밝은 초록
        Signal.BULLISH: 0x32CD32,          # 라임그린
        Signal.NEUTRAL: 0x808080,          # 회색
        Signal.BEARISH: 0xFFA500,          # 주황
        Signal.STRONG_BEARISH: 0xFF0000,   # 빨강
    }

    # 섹터 분류
    SECTORS = {
        "반도체": ["삼성전자", "SK하이닉스", "엔비디아", "TSMC", "인텔", "AMD", "HBM", "D램", "낸드", "파운드리"],
        "2차전지": ["LG에너지", "삼성SDI", "SK온", "CATL", "배터리", "리튬", "양극재", "음극재", "전고체"],
        "AI/소프트웨어": ["AI", "인공지능", "LLM", "챗GPT", "클라우드", "데이터센터", "마이크로소프트", "구글"],
        "자동차": ["현대차", "기아", "테슬라", "전기차", "자율주행", "EV"],
        "바이오": ["바이오", "신약", "임상", "FDA", "셀트리온", "삼성바이오"],
        "금융": ["금리", "은행", "증권", "보험", "KB", "신한", "하나"],
        "방산": ["방산", "한화에어로", "LIG넥스원", "한국항공우주", "무기", "수출"],
        "조선": ["조선", "HD한국조선", "삼성중공업", "한화오션", "LNG선"],
        "에너지": ["정유", "석유", "가스", "LNG", "신재생", "태양광", "풍력"],
        "매크로": ["FOMC", "연준", "금리", "인플레이션", "CPI", "GDP", "고용", "실업률"],
    }

    def __init__(self):
        self.client = gemini_client

    def analyze_news_batch(
        self,
        items: list[ContentItem],
        max_items: int = 15,
        sector_etf_data: dict = None,
    ) -> Optional[dict]:
        """
        뉴스 배치 분석 및 시장 시그널 생성

        개선사항:
        - 뉴스에 실제 언급된 섹터만 분석 대상으로 전달
        - 섹터별 관련 뉴스를 구체적으로 제시하여 정확도 향상
        - 낙관 편향 방지 지시 포함
        - AI 응답 후처리 검증

        Returns:
            {
                "overall_signal": "bullish/bearish/neutral",
                "signal_strength": 0.0-1.0,
                "market_sentiment": "시장 분위기 요약",
                "sector_signals": {"반도체": "bullish", ...},
                "key_events": ["핵심 이벤트 1", ...],
                "risk_factors": ["리스크 요인 1", ...],
                "opportunity": "투자 기회 요약"
            }
        """
        if not items:
            return None

        analysis_items = items[:max_items]

        # 1단계: 뉴스에 실제 언급된 섹터 식별
        detected_sectors = self._detect_sectors_in_news(analysis_items)

        # 2단계: 섹터별 관련 뉴스 컨텍스트 생성
        sector_context = self._build_sector_context(detected_sectors)

        # 3단계: 전체 뉴스 텍스트
        news_text = self._format_news_for_analysis(analysis_items)

        # 3.5단계: ETF 시세 컨텍스트 생성
        etf_context = self._build_etf_context(sector_etf_data)

        # 4단계: 분석 대상 섹터 목록 (뉴스에 언급된 것만)
        target_sectors = list(detected_sectors.keys())

        prompt = f"""다음 오늘의 주요 금융 뉴스를 분석하여 시장 시그널을 평가해주세요.

=== 전체 뉴스 ===
{news_text}

=== 섹터별 관련 뉴스 ===
{sector_context}
{etf_context}
=== 분석 대상 섹터 (이 섹터들만 분석하세요) ===
{', '.join(target_sectors)}

다음 JSON 형식으로 응답해주세요:
{{
    "overall_signal": "strong_bullish/bullish/neutral/bearish/strong_bearish 중 하나",
    "signal_strength": 0.0에서 1.0 사이 (확신도),
    "market_sentiment": "전반적인 시장 분위기 요약 (1-2문장)",
    "sector_signals": {{
        "섹터명": "bullish/neutral/bearish"
    }},
    "key_events": ["오늘 가장 중요한 이벤트 1", "이벤트 2", "이벤트 3"],
    "risk_factors": ["주의할 리스크 요인"],
    "opportunity": "오늘의 투자 기회나 주목 포인트 (1문장)"
}}

=== 필수 규칙 ===
1. sector_signals에는 위 "분석 대상 섹터"에 나열된 섹터명만 사용하세요. 다른 이름을 만들지 마세요.
2. 각 섹터는 해당 섹터의 관련 뉴스만 보고 독립적으로 판단하세요.
3. 명확한 호재가 없으면 "neutral"로, 악재가 있으면 "bearish"로 평가하세요.
4. 모든 섹터를 동일한 시그널로 평가하지 마세요. 각 섹터의 뉴스 내용이 다르면 시그널도 달라야 합니다.
5. "해당 섹터에 대한 뉴스는 있지만 방향성이 불분명한 경우"는 반드시 "neutral"입니다.
6. 실제 섹터 ETF 시세가 제공된 경우, 뉴스와 시세를 교차 검증하세요. ETF가 하락 중인데 뉴스가 호재면 "neutral"로 하향 조정을, ETF가 상승 중인데 뉴스가 악재면 "neutral"로 상향 조정을 고려하세요.

분석 기준:
- strong_bullish: 시장 전반 강한 상승 기대 (호재 다수)
- bullish: 상승 우위 (호재 > 악재)
- neutral: 혼조세 또는 영향 제한적
- bearish: 하락 우위 (악재 > 호재)
- strong_bearish: 시장 전반 강한 하락 우려 (악재 다수)"""

        try:
            result = self.client.generate_json(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=800,
            )

            if result:
                # 5단계: 후처리 검증
                result = self._validate_signal_response(result, target_sectors)
                # ETF 데이터를 결과에 첨부 (embed에서 사용)
                if sector_etf_data:
                    result["sector_etf_data"] = sector_etf_data
                logger.info(f"Market signal generated: {result.get('overall_signal')}")
                return result

        except Exception as e:
            logger.error(f"Failed to generate market signal: {e}")

        return None

    def _detect_sectors_in_news(
        self,
        items: list[ContentItem],
    ) -> dict[str, list[ContentItem]]:
        """
        뉴스에서 실제 언급된 섹터와 관련 뉴스를 식별

        Returns:
            {"반도체": [item1, item2], "자동차": [item3], ...}
            (뉴스에 언급되지 않은 섹터는 포함하지 않음)
        """
        sector_items: dict[str, list[ContentItem]] = {}

        for item in items:
            text = f"{item.title} {item.description or ''}".lower()

            for sector, keywords in self.SECTORS.items():
                for keyword in keywords:
                    if keyword.lower() in text:
                        if sector not in sector_items:
                            sector_items[sector] = []
                        sector_items[sector].append(item)
                        break  # 한 섹터에 대해 키워드 하나만 매칭되면 충분

        return sector_items

    def _build_sector_context(
        self,
        sector_items: dict[str, list[ContentItem]],
    ) -> str:
        """섹터별 관련 뉴스를 AI에게 전달할 컨텍스트로 구성"""
        if not sector_items:
            return "(관련 섹터 뉴스 없음)"

        lines = []
        for sector, items in sector_items.items():
            lines.append(f"\n[{sector}] 관련 뉴스 {len(items)}건:")
            for item in items[:5]:  # 섹터당 최대 5건
                title = item.title[:60]
                lines.append(f"  - {title}")

        return "\n".join(lines)

    def _build_etf_context(self, sector_etf_data: dict = None) -> str:
        """섹터 ETF 실시간 시세를 AI에게 전달할 컨텍스트로 구성"""
        if not sector_etf_data:
            return ""

        lines = ["\n=== 실제 섹터 ETF 시세 (참고 데이터) ==="]
        for sector, etf in sector_etf_data.items():
            sign = "+" if etf.is_up else ""
            lines.append(f"- {sector}: {etf.etf_name} {sign}{etf.change_percent:.2f}% (현재가 {etf.price:,.0f}원)")

        lines.append("(위 ETF 시세는 실제 시장 데이터입니다. 뉴스 판단과 교차 검증에 활용하세요.)")
        return "\n".join(lines)

    def _validate_signal_response(
        self,
        result: dict,
        target_sectors: list[str],
    ) -> dict:
        """
        AI 응답 후처리 검증

        - 사전 정의되지 않은 섹터 제거
        - 유효하지 않은 시그널값 보정
        - 모든 섹터가 동일 시그널이면 경고 로깅
        """
        sector_signals = result.get("sector_signals", {})

        # 사전 정의된 섹터만 유지 (AI가 임의로 만든 섹터명 제거)
        validated_signals = {}
        for sector, signal in sector_signals.items():
            if sector in self.SECTORS:
                # 유효한 시그널값인지 확인
                if signal in self.VALID_SECTOR_SIGNALS:
                    validated_signals[sector] = signal
                else:
                    logger.warning(f"Invalid sector signal '{signal}' for {sector}, defaulting to neutral")
                    validated_signals[sector] = "neutral"
            else:
                logger.warning(f"AI generated unknown sector '{sector}', skipping")

        # 뉴스에 언급되지 않은 섹터가 AI 응답에 있으면 제거
        final_signals = {}
        for sector in target_sectors:
            if sector in validated_signals:
                final_signals[sector] = validated_signals[sector]

        # 모든 섹터가 동일 시그널이면 경고
        if final_signals:
            unique_signals = set(final_signals.values())
            if len(unique_signals) == 1 and len(final_signals) >= 3:
                logger.warning(
                    f"All {len(final_signals)} sectors have same signal "
                    f"'{unique_signals.pop()}' - possible bias"
                )

        result["sector_signals"] = final_signals
        return result

    def categorize_by_sector(self, items: list[ContentItem]) -> dict[str, list[ContentItem]]:
        """
        뉴스를 섹터별로 분류

        Returns:
            {"반도체": [item1, item2], "2차전지": [item3], ...}
        """
        categorized = {sector: [] for sector in self.SECTORS}
        categorized["기타"] = []

        for item in items:
            text = f"{item.title} {item.description or ''}".lower()
            matched = False

            for sector, keywords in self.SECTORS.items():
                for keyword in keywords:
                    if keyword.lower() in text:
                        categorized[sector].append(item)
                        item.extra_data["sector"] = sector
                        matched = True
                        break
                if matched:
                    break

            if not matched:
                categorized["기타"].append(item)
                item.extra_data["sector"] = "기타"

        # 빈 섹터 제거
        return {k: v for k, v in categorized.items() if v}

    def detect_breaking_news(self, items: list[ContentItem]) -> list[ContentItem]:
        """
        급등/급락 등 시장 급변 뉴스 감지

        Returns:
            긴급 뉴스 리스트
        """
        breaking_keywords = [
            "급등", "급락", "폭등", "폭락", "사상최고", "사상최저",
            "서킷브레이커", "거래정지", "상한가", "하한가",
            "긴급", "속보", "충격", "파산", "부도",
            "전쟁", "테러", "대폭", "급변",
        ]

        breaking_news = []
        for item in items:
            text = f"{item.title} {item.description or ''}".lower()
            for keyword in breaking_keywords:
                if keyword in text:
                    item.extra_data["is_breaking"] = True
                    item.extra_data["breaking_keyword"] = keyword
                    breaking_news.append(item)
                    break

        if breaking_news:
            logger.info(f"Detected {len(breaking_news)} breaking news items")

        return breaking_news

    def get_signal_emoji(self, signal_str: str) -> str:
        """시그널 문자열에서 이모지 반환"""
        try:
            signal = Signal(signal_str)
            return self.SIGNAL_EMOJI.get(signal, "➡️")
        except ValueError:
            return "➡️"

    def get_signal_color(self, signal_str: str) -> int:
        """시그널 문자열에서 색상 코드 반환"""
        try:
            signal = Signal(signal_str)
            return self.SIGNAL_COLOR.get(signal, 0x808080)
        except ValueError:
            return 0x808080

    def _format_news_for_analysis(self, items: list[ContentItem]) -> str:
        """분석용 뉴스 포맷팅"""
        lines = []
        for i, item in enumerate(items, 1):
            source = item.source or "Unknown"
            title = item.title
            desc = item.description[:150] if item.description else ""

            line = f"{i}. [{source}] {title}"
            if desc:
                line += f" - {desc}"
            lines.append(line)

        return "\n".join(lines)


# 전역 인스턴스
market_signal_analyzer = MarketSignalAnalyzer()
