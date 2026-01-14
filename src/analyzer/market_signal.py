"""
AI 시장 시그널 분석기
뉴스 기반 투자 시그널 생성 (Bullish/Bearish/Neutral)
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from src.collectors.base import ContentItem
from src.analyzer.groq_client import groq_client
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
객관적이고 데이터 기반으로 분석합니다."""

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
        self.client = groq_client

    def analyze_news_batch(
        self,
        items: list[ContentItem],
        max_items: int = 15,
    ) -> Optional[dict]:
        """
        뉴스 배치 분석 및 시장 시그널 생성

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

        # 뉴스 텍스트 생성
        news_text = self._format_news_for_analysis(items[:max_items])

        prompt = f"""다음 오늘의 주요 금융 뉴스를 분석하여 시장 시그널을 평가해주세요:

{news_text}

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
                logger.info(f"Market signal generated: {result.get('overall_signal')}")
                return result

        except Exception as e:
            logger.error(f"Failed to generate market signal: {e}")

        return None

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
