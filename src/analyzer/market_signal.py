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
전일 뉴스, 밤사이 미국장 결과, 야간 선물 데이터를 종합하여
"오늘 한국 장이 어떻게 될 것인가"를 예측합니다.

핵심 분석 프레임워크 (우선순위 순):
1. 야간 선물/미국장 실제 데이터 → 가장 강력한 방향 지표
2. 섹터 ETF 실시간 시세 → 현재 시장이 이미 반영한 방향
3. 뉴스 감성 → 참고 자료 (이미 시장에 반영되었을 수 있음)

중요 원칙:
- 뉴스 감성과 실제 시장 데이터가 상충할 때, 시장 데이터를 우선하세요
- 전일 대폭락 후에는 기술적 반등 가능성을 반드시 고려하세요
- 각 섹터를 독립적으로 분석하고, 해당 섹터의 뉴스 내용만으로 판단하세요
- 명확한 호재/악재가 없는 섹터는 반드시 "neutral"로 평가하세요
- 모든 섹터를 동일한 시그널로 평가하지 마세요"""

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
        overnight_us_data: list = None,
        night_futures: list = None,
        schedule_type: str = "morning",
        live_market_data=None,
        morning_signal_cache: dict = None,
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
                "swot": {
                    "strengths": ["강점 1", ...],
                    "weaknesses": ["약점 1", ...],
                    "opportunities": ["기회 1", ...],
                    "threats": ["위협 1", ...]
                },
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

        # 3.6단계: 미국장 마감 데이터 컨텍스트 생성
        us_market_context = self._build_overnight_us_context(overnight_us_data)

        # 3.7단계: 야간 선물 데이터 컨텍스트 생성
        night_futures_context = self._build_night_futures_context(night_futures)

        # 4단계: 분석 대상 섹터 목록 (뉴스에 언급된 것만)
        target_sectors = list(detected_sectors.keys())

        if schedule_type == "noon":
            prompt = self._build_midday_prompt(
                news_text, sector_context, etf_context,
                target_sectors, live_market_data, morning_signal_cache,
            )
        elif schedule_type == "afternoon":
            prompt = self._build_afternoon_prompt(
                news_text, sector_context, etf_context,
                target_sectors, live_market_data, morning_signal_cache,
            )
        else:
            prompt = f"""당신의 임무: 오늘 한국 주식 시장이 어떻게 움직일지 전망하세요.
아래 데이터를 종합하여 "오늘 장 전망"을 예측해주세요. 어제 이미 일어난 일이 아니라, 오늘 장에 어떤 영향을 줄지를 분석하세요.
{us_market_context}
{night_futures_context}
=== 전일 이후 주요 뉴스 ===
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
    "market_sentiment": "오늘 한국 장 전망 요약 (1-2문장, '오늘 장은 ~할 것으로 예상' 형태)",
    "swot": {{
        "strengths": ["오늘 장에 긍정적 요인 1-2개 (출처 포함)"],
        "weaknesses": ["오늘 장에 부정적 요인 1-2개"],
        "opportunities": ["오늘 주목할 투자 기회 1-2개"],
        "threats": ["오늘 주의할 위협 요인 1-2개"]
    }},
    "sector_signals": {{
        "섹터명": "bullish/neutral/bearish"
    }},
    "key_events": ["오늘 장에 영향을 줄 핵심 이벤트 (어제 이미 끝난 일 제외)", "이벤트 2", "이벤트 3"],
    "risk_factors": ["오늘 장에서 주의할 리스크 요인"],
    "opportunity": "오늘의 투자 기회나 주목 포인트 (1문장)"
}}

=== 필수 규칙 ===
1. ⚠️ 이것은 "오늘 장 전망"입니다. 어제 이미 발생한 이벤트(예: "어제 코스피 급락", "어제 서킷브레이커 발동")를 key_events에 넣지 마세요. 대신 그 여파로 오늘 어떤 일이 일어날지 예측하세요.
2. 야간 선물/미국장 데이터가 있으면 이를 최우선 근거로 사용하세요. 뉴스가 악재 위주라도 야간 선물이 상승 마감했다면 "갭업 출발" 가능성이 높습니다.
3. sector_signals에는 위 "분석 대상 섹터"에 나열된 섹터명만 사용하세요.
4. 각 섹터는 독립적으로 판단하세요. 모든 섹터를 동일 시그널로 평가하지 마세요.
5. 명확한 호재가 없으면 "neutral"로, 악재가 있으면 "bearish"로 평가하세요.
6. 실제 섹터 ETF 시세가 제공된 경우, 뉴스와 교차 검증하세요.
7. 전일 대폭락(-5% 이상) 뉴스가 있고 야간 선물/미국장이 반등했다면, "기술적 반등" 가능성을 반드시 반영하세요.

시그널 기준 (오늘 장 전망):
- strong_bullish: 오늘 강한 상승 예상 (야간 선물 상승 + 호재)
- bullish: 오늘 상승 우위 (호재 > 악재, 또는 야간 선물 소폭 상승)
- neutral: 혼조세/방향 불확실
- bearish: 오늘 하락 우위 (야간 선물 하락, 또는 악재 > 호재)
- strong_bearish: 오늘 강한 하락 예상 (야간 선물 하락 + 악재 다수)"""

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

    def _build_night_futures_context(self, night_futures: list = None) -> str:
        """야간 선물 마감 데이터를 AI에게 전달할 컨텍스트로 구성"""
        if not night_futures:
            return ""

        lines = ["\n=== 🌙 야간 선물 마감 데이터 (한국 시장 직접 선행 지표) ==="]
        for nf in night_futures:
            sign = "+" if nf.change_percent >= 0 else ""
            arrow = "📈" if nf.is_up else "📉"
            lines.append(f"- {nf.name}: {nf.price:,.2f} ({sign}{nf.change_percent:.2f}%) {arrow}")

        lines.append("")
        lines.append("⚠️ 야간 선물은 오늘 한국 장 시초가 방향을 가장 직접적으로 예측합니다.")
        lines.append("야간 선물이 +1% 이상이면 갭업 출발, -1% 이상이면 갭다운 출발 가능성이 높습니다.")
        return "\n".join(lines)

    def _build_overnight_us_context(self, overnight_us_data: list = None) -> str:
        """미국장 마감 데이터를 AI에게 전달할 컨텍스트로 구성"""
        if not overnight_us_data:
            return ""

        lines = ["\n=== ⚠️ 미국장 마감 데이터 (밤사이 실제 결과 - 매우 중요) ==="]
        for us in overnight_us_data:
            sign = "+" if us.is_up else ""
            arrow = "📈" if us.is_up else "📉"
            lines.append(f"- {us.name}: {us.value:,.2f} ({sign}{us.change_percent:.2f}%) {arrow}")

        lines.append("")
        lines.append("⚠️ 위 미국장 데이터는 한국 장 개장 전 실제 마감 결과입니다.")
        lines.append("한국 뉴스가 전일 악재 위주라도 밤사이 미국장이 반등했다면 한국 시장도 갭업 가능성이 높습니다.")
        lines.append("뉴스 톤과 미국장 방향이 다를 경우, 미국장 실제 결과를 더 신뢰하세요.")
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

    # 부정적 긴급 키워드 (이 키워드가 감지되면 맥락 검증 필요)
    NEGATIVE_BREAKING = {"급락", "폭락", "폭등", "대폭", "하한가", "사상최저", "충격"}
    # 긍정적 맥락 키워드 (부정 키워드와 함께 등장하면 오탐 가능성)
    POSITIVE_CONTEXT = {"반등", "회복", "상승", "강세", "급등", "호전", "반전", "개선", "만회"}

    def detect_breaking_news(self, items: list[ContentItem]) -> list[ContentItem]:
        """
        급등/급락 등 시장 급변 뉴스 감지
        맥락 검증으로 오탐 방지 (제목에 "폭락"이 있어도 내용이 긍정이면 제외)

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
            title_lower = item.title.lower()
            desc_lower = (item.description or "").lower()
            text = f"{title_lower} {desc_lower}"

            for keyword in breaking_keywords:
                if keyword not in text:
                    continue

                # 맥락 검증: 부정 키워드가 description에만 있고 title은 긍정이면 스킵
                if keyword in self.NEGATIVE_BREAKING:
                    # 제목에서 긍정 맥락 단어 개수
                    positive_in_title = sum(
                        1 for pw in self.POSITIVE_CONTEXT if pw in title_lower
                    )
                    # 키워드가 제목이 아닌 설명에만 있고, 제목이 긍정적이면 스킵
                    if keyword not in title_lower and positive_in_title >= 1:
                        logger.debug(
                            f"Breaking news skipped (context mismatch): "
                            f"keyword='{keyword}' in desc but title is positive: {item.title[:50]}"
                        )
                        continue
                    # 제목에 부정 키워드가 있지만 긍정 맥락이 더 많으면 스킵
                    negative_in_title = sum(
                        1 for nw in self.NEGATIVE_BREAKING if nw in title_lower
                    )
                    if positive_in_title > negative_in_title:
                        logger.debug(
                            f"Breaking news skipped (positive > negative): {item.title[:50]}"
                        )
                        continue

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

    def _build_midday_prompt(
        self,
        news_text: str,
        sector_context: str,
        etf_context: str,
        target_sectors: list[str],
        live_market_data=None,
        morning_signal_cache: dict = None,
    ) -> str:
        """점심 브리핑용 프롬프트 (장중 상황 체크)"""
        live_context = self._build_live_market_context(live_market_data)
        morning_context = self._build_morning_prediction_context(morning_signal_cache)

        return f"""당신의 임무: 현재 진행 중인 한국 장의 상황을 분석하세요.
오전에 수집된 뉴스와 실시간 시장 데이터를 종합하여 "장중 상황 체크"를 수행합니다.
{live_context}
{morning_context}
=== 오전장 주요 뉴스 ===
{news_text}

=== 섹터별 관련 뉴스 ===
{sector_context}
{etf_context}
=== 분석 대상 섹터 (이 섹터들만 분석하세요) ===
{', '.join(target_sectors)}

다음 JSON 형식으로 응답해주세요:
{{
    "overall_signal": "strong_bullish/bullish/neutral/bearish/strong_bearish 중 하나 (현재 장 방향)",
    "signal_strength": 0.0에서 1.0 사이 (확신도),
    "market_sentiment": "현재 장 상황 요약 (1-2문장, '현재 장은 ~하고 있어요' 형태)",
    "morning_accuracy": "적중/불일치/부분적중 (오전 예측 대비 실제 결과)",
    "morning_accuracy_comment": "오전 예측이 어떻게 됐는지 코멘트 (1문장, 해요체)",
    "swot": {{
        "strengths": ["오전장 긍정적 요인 1-2개 (출처 포함)"],
        "weaknesses": ["오전장 부정적 요인 1-2개"],
        "opportunities": ["오후 장 투자 기회 1-2개"],
        "threats": ["오후 장 주의할 위협 1-2개"]
    }},
    "sector_signals": {{
        "섹터명": "bullish/neutral/bearish"
    }},
    "key_events": ["오전장에 발생한 주요 이슈 3-4개 (현재 진행 중인 것 위주)"],
    "risk_factors": ["오후 장에서 주의할 리스크 요인"],
    "opportunity": "오후 투자 기회나 주목 포인트 (1문장)"
}}

=== 필수 규칙 ===
1. ⚠️ 이것은 "장중 상황 체크"입니다. 현재 실시간 지수 데이터가 제공된 경우 이를 최우선으로 반영하세요.
2. 오전 예측(morning_prediction)이 제공된 경우, 실제 지수 방향과 비교하여 morning_accuracy를 평가하세요.
3. sector_signals에는 위 "분석 대상 섹터"에 나열된 섹터명만 사용하세요.
4. 각 섹터는 독립적으로 판단하세요.
5. ETF 시세가 실시간 지수 방향과 크게 다르면(예: 코스피 -8%인데 ETF 전부 양수), ETF 데이터는 무시하고 실시간 지수를 기준으로 판단하세요.
6. key_events에는 오전장에 실제 일어난 이슈(서킷브레이커, 급등락 등)를 넣으세요.
7. risk_factors와 opportunity에는 오후 장에 대한 전망을 넣으세요.

시그널 기준 (현재 장 상황):
- strong_bullish: 현재 강한 상승세 (+3% 이상)
- bullish: 현재 상승세 (+0.5% ~ +3%)
- neutral: 보합/혼조세 (-0.5% ~ +0.5%)
- bearish: 현재 하락세 (-0.5% ~ -3%)
- strong_bearish: 현재 강한 하락세 (-3% 이상)"""

    def _build_afternoon_prompt(
        self,
        news_text: str,
        sector_context: str,
        etf_context: str,
        target_sectors: list[str],
        live_market_data=None,
        morning_signal_cache: dict = None,
    ) -> str:
        """장 마감 브리핑용 프롬프트 (오늘 장 복기)"""
        close_context = self._build_market_close_context(live_market_data)
        morning_context = self._build_morning_prediction_context(morning_signal_cache)

        return f"""당신의 임무: 오늘 한국 장이 마감됐습니다. 오늘 장을 복기하세요.
오늘 하루 뉴스와 실제 장 마감 데이터를 종합하여 "오늘 장 마감 분석"을 수행합니다.
{close_context}
{morning_context}
=== 오늘의 주요 뉴스 ===
{news_text}

=== 섹터별 관련 뉴스 ===
{sector_context}
{etf_context}
=== 분석 대상 섹터 (이 섹터들만 분석하세요) ===
{', '.join(target_sectors)}

다음 JSON 형식으로 응답해주세요:
{{
    "overall_signal": "strong_bullish/bullish/neutral/bearish/strong_bearish 중 하나 (오늘 장 결과)",
    "signal_strength": 0.0에서 1.0 사이 (확신도),
    "market_sentiment": "오늘 장 마감 요약 (1-2문장, '오늘 장은 ~했어요' 형태)",
    "morning_accuracy": "적중/불일치/부분적중 (오전 예측 대비 최종 결과)",
    "morning_accuracy_comment": "오전 예측이 최종적으로 어떻게 됐는지 코멘트 (1문장, 해요체)",
    "swot": {{
        "strengths": ["오늘 장에서 긍정적이었던 요인 1-2개 (출처 포함)"],
        "weaknesses": ["오늘 장에서 부정적이었던 요인 1-2개"],
        "opportunities": ["내일 주목할 투자 기회 1-2개"],
        "threats": ["내일 주의할 위협 요인 1-2개"]
    }},
    "sector_signals": {{
        "섹터명": "bullish/neutral/bearish"
    }},
    "key_events": ["오늘 장에서 실제 일어난 주요 이슈 3-4개"],
    "risk_factors": ["오늘의 교훈 또는 주의점"],
    "opportunity": "내일 주목할 포인트 (1문장)"
}}

=== 필수 규칙 ===
1. ⚠️ 이것은 "장 마감 복기"입니다. 장 마감 데이터가 제공된 경우 이를 최우선으로 반영하세요.
2. overall_signal은 오늘 장의 실제 결과를 반영해야 합니다 (예측이 아님).
3. 오전 예측(morning_prediction)이 제공된 경우, 장 마감 결과와 비교하여 morning_accuracy를 평가하세요.
4. sector_signals에는 위 "분석 대상 섹터"에 나열된 섹터명만 사용하세요.
5. 각 섹터는 독립적으로 판단하세요.
6. key_events에는 오늘 실제 일어난 이슈를 넣으세요 (서킷브레이커, 급등락, 주요 종목 이슈 등).
7. risk_factors에는 오늘 장에서 배울 교훈이나 주의점을 넣으세요.
8. opportunity에는 내일 장에 대한 간략한 포인트를 넣으세요.

시그널 기준 (오늘 장 결과):
- strong_bullish: 오늘 강한 상승 마감 (+3% 이상)
- bullish: 오늘 상승 마감 (+0.5% ~ +3%)
- neutral: 보합 마감 (-0.5% ~ +0.5%)
- bearish: 오늘 하락 마감 (-0.5% ~ -3%)
- strong_bearish: 오늘 강한 하락 마감 (-3% 이상)"""

    def _build_market_close_context(self, live_market_data=None) -> str:
        """장 마감 데이터를 AI에게 전달할 컨텍스트로 구성"""
        if not live_market_data:
            return ""

        lines = ["\n=== 📊 장 마감 데이터 (오늘의 실제 결과 - 최우선 반영) ==="]

        kospi = live_market_data.get("kospi")
        if kospi:
            sign = "+" if kospi.is_up else ""
            arrow = "📈" if kospi.is_up else "📉"
            lines.append(f"- 코스피: {kospi.value:,.2f} ({sign}{kospi.change_percent:.2f}%) {arrow}")

        kosdaq = live_market_data.get("kosdaq")
        if kosdaq:
            sign = "+" if kosdaq.is_up else ""
            arrow = "📈" if kosdaq.is_up else "📉"
            lines.append(f"- 코스닥: {kosdaq.value:,.2f} ({sign}{kosdaq.change_percent:.2f}%) {arrow}")

        usd_krw = live_market_data.get("usd_krw")
        if usd_krw:
            sign = "+" if usd_krw.is_up else ""
            arrow = "📈" if usd_krw.is_up else "📉"
            lines.append(f"- 원/달러: {usd_krw.value:,.2f} ({sign}{usd_krw.change_percent:.2f}%) {arrow}")

        lines.append("")
        lines.append("⚠️ 위는 오늘 장 마감 실제 결과입니다. overall_signal은 이 데이터를 기준으로 판단하세요.")
        return "\n".join(lines)

    def _build_live_market_context(self, live_market_data=None) -> str:
        """실시간 시장 데이터를 AI에게 전달할 컨텍스트로 구성"""
        if not live_market_data:
            return ""

        lines = ["\n=== 🇰🇷 실시간 지수 (가장 중요한 데이터) ==="]

        kospi = live_market_data.get("kospi")
        if kospi:
            sign = "+" if kospi.is_up else ""
            arrow = "📈" if kospi.is_up else "📉"
            lines.append(f"- 코스피: {kospi.value:,.2f} ({sign}{kospi.change_percent:.2f}%) {arrow}")

        kosdaq = live_market_data.get("kosdaq")
        if kosdaq:
            sign = "+" if kosdaq.is_up else ""
            arrow = "📈" if kosdaq.is_up else "📉"
            lines.append(f"- 코스닥: {kosdaq.value:,.2f} ({sign}{kosdaq.change_percent:.2f}%) {arrow}")

        usd_krw = live_market_data.get("usd_krw")
        if usd_krw:
            sign = "+" if usd_krw.is_up else ""
            arrow = "📈" if usd_krw.is_up else "📉"
            lines.append(f"- 원/달러: {usd_krw.value:,.2f} ({sign}{usd_krw.change_percent:.2f}%) {arrow}")

        lines.append("")
        lines.append("⚠️ 위 실시간 지수가 현재 시장의 실제 방향입니다. 이 데이터를 최우선으로 반영하세요.")
        return "\n".join(lines)

    def _build_morning_prediction_context(self, morning_signal_cache: dict = None) -> str:
        """오전 예측 데이터를 AI에게 전달할 컨텍스트로 구성"""
        if not morning_signal_cache:
            return ""

        signal_kr = {
            "strong_bullish": "강한 상승",
            "bullish": "상승",
            "neutral": "중립",
            "bearish": "하락",
            "strong_bearish": "강한 하락",
        }

        overall = morning_signal_cache.get("overall_signal", "neutral")
        strength = morning_signal_cache.get("signal_strength", 0.5)
        sentiment = morning_signal_cache.get("market_sentiment", "")

        lines = ["\n=== 📋 오전 7시 예측 (비교용) ==="]
        lines.append(f"- 예측 시그널: {signal_kr.get(overall, overall)} ({int(strength*100)}%)")
        if sentiment:
            lines.append(f"- 예측 요약: {sentiment}")
        lines.append("(위 예측과 실제 지수를 비교하여 morning_accuracy를 평가하세요.)")
        lines.append("")
        return "\n".join(lines)

    def _format_news_for_analysis(self, items: list[ContentItem]) -> str:
        """분석용 뉴스 포맷팅 (시간대별 구분)"""
        from datetime import datetime, timedelta

        now = datetime.now()
        # 전일 장 마감 기준 (15:30)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0) - timedelta(days=1)

        recent_lines = []   # 장 마감 후 ~ 현재 (더 중요)
        older_lines = []    # 그 이전 (이미 반영된 뉴스)

        for i, item in enumerate(items, 1):
            source = item.source or "Unknown"
            title = item.title
            desc = item.description[:150] if item.description else ""

            # 발행 시간 확인
            time_label = ""
            is_recent = True
            if item.published_at:
                # aware datetime → naive 변환 (timezone 혼재 대응)
                pub = item.published_at
                if pub.tzinfo is not None:
                    pub = pub.replace(tzinfo=None)
                if pub >= market_close:
                    time_label = " [장 마감 후]"
                else:
                    time_label = " [장중/이전]"
                    is_recent = False

            line = f"{i}. [{source}]{time_label} {title}"
            if desc:
                line += f" - {desc}"

            if is_recent:
                recent_lines.append(line)
            else:
                older_lines.append(line)

        result_lines = []
        if recent_lines:
            result_lines.append("--- 장 마감 후 ~ 새벽 뉴스 (오늘 장에 아직 미반영, 더 중요) ---")
            result_lines.extend(recent_lines)
        if older_lines:
            result_lines.append("\n--- 장중/이전 뉴스 (이미 시장에 반영되었을 수 있음) ---")
            result_lines.extend(older_lines)

        return "\n".join(result_lines) if result_lines else "\n".join(
            f"{i}. [{item.source or 'Unknown'}] {item.title}" for i, item in enumerate(items, 1)
        )


# 전역 인스턴스
market_signal_analyzer = MarketSignalAnalyzer()
