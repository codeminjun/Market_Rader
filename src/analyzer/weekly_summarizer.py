"""
주말 전용 요약 모듈
토요일: 한 주간 시장 리뷰 / 일요일: 다음 주 시장 전망
"""
from datetime import datetime, timedelta
from typing import Optional

from src.collectors.base import ContentItem
from src.analyzer.gemini_client import gemini_client
from src.utils.logger import logger


class WeeklySummarizer:
    """토요일용 - 한 주간 시장 리뷰 요약기 (정성적 분석만 담당, 수치는 크롤링 데이터 사용)"""

    SYSTEM_PROMPT = """당신은 한국 금융 시장 전문 애널리스트입니다.
한 주간의 시장 동향을 분석하여 투자자에게 명확한 인사이트를 제공합니다.
응답은 항상 한국어로 작성합니다.

절대적 규칙:
- 구체적 수치(코스피/코스닥 지수, 환율, ETF 등락률 등)는 별도로 표시되므로 절대 언급하지 마세요
- 수치 대신 "상승세를 보였다", "하락 전환했다" 같은 정성적 표현을 사용하세요
- 뉴스에 언급되지 않은 이벤트를 추측하거나 지어내지 마세요
- 인과관계와 맥락 중심으로 서술하세요
- 데이터가 부족하면 "확인된 데이터 없음"이라고 솔직하게 명시하세요"""

    def __init__(self):
        self.client = gemini_client

    def generate_weekly_review(
        self,
        archived_items: list[dict] = None,
        live_news: list[ContentItem] = None,
        news_items: list[ContentItem] = None,
        report_items: list[ContentItem] = None,
        sector_etf_history: dict = None,
        market_index_history: dict = None,
    ) -> Optional[dict]:
        """
        한 주간 시장 리뷰 생성 (토요일용) - 정성적 분석만

        Returns:
            {
                "weekly_summary": "정성적 시장 총평 (수치 제외, 인과관계/맥락만)",
                "sector_insights": {"반도체": "원인 분석 2-3문장", ...},
                "next_week_watchpoints": "다음 주 주목 포인트 2-3문장"
            }
        """
        # 아카이브 데이터가 있으면 우선 사용
        if archived_items:
            news_text = self._format_archived_items(archived_items)
        elif news_items:
            news_text = self._format_items_for_prompt(news_items[:25])
            if report_items:
                news_text += f"\n\n주요 애널리스트 리포트:\n{self._format_items_for_prompt(report_items[:10])}"
        else:
            return None

        # 실시간 뉴스 보완
        live_text = ""
        if live_news:
            live_text = f"\n\n오늘 추가 수집된 뉴스:\n{self._format_items_for_prompt(live_news[:10])}"

        # 이번 주 날짜 범위 계산
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=4)
        date_range = f"{week_start.strftime('%m/%d')} ~ {week_end.strftime('%m/%d')}"

        # 섹터 ETF 목록 (AI에게 어떤 섹터를 분석할지 알려줌)
        sector_list_text = ""
        if sector_etf_history:
            sectors = set()
            for day_data in sector_etf_history.values():
                sectors.update(day_data.keys())
            if sectors:
                sector_list_text = f"\n\n분석 대상 섹터: {', '.join(sorted(sectors))}"

        # 다음 주 휴장일 정보
        from src.utils.market_holiday import get_next_week_holidays
        next_week_holidays = get_next_week_holidays(today.date())
        holiday_text = ""
        if next_week_holidays:
            holiday_lines = []
            for h in next_week_holidays:
                parts = []
                if h["krx"]:
                    parts.append(f"KRX 휴장({h['krx']})")
                if h["nyse"]:
                    parts.append(f"NYSE 휴장({h['nyse']})")
                holiday_lines.append(f"  - {h['date']}: {', '.join(parts)}")
            holiday_text = "\n\n⚠️ 다음 주 시장 휴장일:\n" + "\n".join(holiday_lines)

        prompt = f"""다음은 이번 주({date_range}) 동안 수집된 주요 금융/경제 뉴스입니다.

{news_text}{live_text}{sector_list_text}{holiday_text}

위 뉴스를 바탕으로 정성적 시장 분석을 해주세요.
⚠️ 중요: 코스피/코스닥 지수, 환율, ETF 등락률 등 구체적 수치는 별도로 표시되므로 절대 언급하지 마세요.
수치 대신 "상승세", "하락 전환", "강세", "약세" 같은 정성적 표현만 사용하세요.

다음 JSON 형식으로 응답:
{{
    "weekly_summary": "이번 주 시장 전체 흐름을 4-5문장으로 총평. 수치 없이 인과관계와 맥락만 서술. (1) 주요 이슈가 시장에 미친 영향 (2) 외국인/기관 수급 동향 (3) 시장 심리와 투자자 반응",
    "sector_insights": {{
        "섹터명": "해당 섹터의 등락 원인을 2-3문장으로 분석. 관련 뉴스를 근거로 구체적 종목명/이벤트 포함. 수치는 제외.",
        "섹터명2": "분석..."
    }},
    "next_week_watchpoints": "다음 주 주목 포인트 2-3문장 (이번 주 흐름의 연장선, 예정된 이벤트, 휴장일 영향 등)"
}}

핵심 규칙:
1. weekly_summary에 절대로 구체적 숫자를 쓰지 마세요 (지수, 환율, 등락률 등)
2. sector_insights: 위 "분석 대상 섹터"에 해당하는 섹터만 분석하세요. 없으면 뉴스에서 언급된 주요 섹터를 분석하세요.
3. 모든 서술에서 단순 나열이 아닌, 인과관계와 맥락을 설명하세요.
4. 뉴스에 언급되지 않은 이벤트를 추측하거나 지어내지 마세요."""

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

    # 섹터 키워드 매핑 (market_signal.py와 동일)
    SECTOR_KEYWORDS = {
        "반도체": ["삼성전자", "SK하이닉스", "엔비디아", "TSMC", "인텔", "AMD", "HBM", "D램", "낸드", "파운드리"],
        "2차전지": ["LG에너지", "삼성SDI", "SK온", "CATL", "배터리", "리튬", "양극재", "음극재", "전고체"],
        "AI/소프트웨어": ["AI", "인공지능", "LLM", "챗GPT", "클라우드", "데이터센터", "마이크로소프트", "구글"],
        "자동차": ["현대차", "기아", "테슬라", "전기차", "자율주행", "EV"],
        "바이오": ["바이오", "신약", "임상", "FDA", "셀트리온", "삼성바이오"],
        "금융": ["금리", "은행", "증권", "보험", "KB", "신한", "하나"],
        "방산": ["방산", "한화에어로", "LIG넥스원", "한국항공우주", "무기", "수출"],
        "조선": ["조선", "HD한국조선", "삼성중공업", "한화오션", "LNG선"],
        "에너지": ["정유", "석유", "가스", "LNG", "신재생", "태양광", "풍력"],
    }

    def _format_archived_items(self, items: list[dict]) -> str:
        """아카이브 아이템을 날짜별로 그룹핑하여 프롬프트용 텍스트 생성"""
        from collections import defaultdict

        # 날짜별 그룹핑
        by_date = defaultdict(list)
        for item in items:
            pub_date = item.get("published_at", "")
            if pub_date:
                try:
                    date_key = datetime.fromisoformat(pub_date).strftime("%m/%d (%a)")
                except (ValueError, TypeError):
                    date_key = "날짜 미상"
            else:
                date_key = "날짜 미상"
            by_date[date_key].append(item)

        # 날짜순 정렬 후 텍스트 생성
        lines = []
        for date_key in sorted(by_date.keys()):
            lines.append(f"\n--- {date_key} ---")
            date_items = by_date[date_key]
            # 같은 날짜 내에서 중요도 순 정렬
            date_items.sort(key=lambda x: x.get("importance_score", 0), reverse=True)
            for i, item in enumerate(date_items, 1):
                source = item.get("source", "Unknown")
                title = item.get("title", "")
                content_type = item.get("content_type", "news")
                type_label = "리포트" if content_type == "report" else "뉴스"
                score = item.get("importance_score", 0)

                line = f"  {i}. [{type_label}][{source}] {title} (중요도: {score:.1f})"

                # 설명이 있으면 간략히 추가
                desc = item.get("description", "")
                if desc:
                    # 설명이 너무 길면 200자로 자르기
                    desc_short = desc[:200].strip()
                    if len(desc) > 200:
                        desc_short += "..."
                    line += f"\n     → {desc_short}"

                lines.append(line)

        return "\n".join(lines)

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

            # 설명이 있으면 간략히 추가
            if item.description:
                desc_short = item.description[:200].strip()
                if len(item.description) > 200:
                    desc_short += "..."
                line += f"\n   → {desc_short}"

            lines.append(line)

        return "\n".join(lines)


class WeeklyPreview:
    """일요일용 - 다음 주 시장 전망 생성기"""

    SYSTEM_PROMPT = """당신은 금융 시장 전략가입니다.
다가오는 한 주의 시장을 전망하고 투자자가 주목해야 할 이벤트와 전략을 제시합니다.
현실적이고 균형 잡힌 시각으로 분석하며, 과도한 낙관이나 비관은 피합니다.
응답은 항상 한국어로 작성합니다.

중요 지침:
- 반드시 제공된 뉴스/리포트 데이터에만 기반하여 분석하세요
- 뉴스에 언급되지 않은 이벤트나 수치를 추측하지 마세요
- 투자 전략과 리스크는 반드시 근거가 되는 뉴스/리포트 출처를 명시하세요
- 데이터가 부족하면 "확인된 데이터 없음"이라고 솔직하게 명시하세요"""

    def __init__(self):
        self.client = gemini_client

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
                "key_events": ["M/DD(요일) 이벤트 설명", ...],
                "watch_sectors": ["주목 섹터 1", ...],
                "risk_factors": ["리스크 (출처: [매체명] '기사 제목')", ...],
                "trading_strategy": "투자 전략 (출처 명시)",
                "key_levels": "주요 지수/종목 관심 가격대"
            }
        """
        if not recent_news:
            return None

        news_text = self._format_items_for_prompt(recent_news[:20])
        reports_text = ""
        if recent_reports:
            reports_text = f"\n\n최근 애널리스트 전망:\n{self._format_items_for_prompt(recent_reports[:10])}"

        # 다음 주 날짜 범위 계산 (구체적 날짜 포함)
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        next_friday = next_monday + timedelta(days=4)

        weekday_names = ["월", "화", "수", "목", "금"]
        date_labels = []
        for i in range(5):
            day = next_monday + timedelta(days=i)
            date_labels.append(f"{day.strftime('%m/%d')}({weekday_names[i]})")
        dates_list = ", ".join(date_labels)
        date_range = f"{date_labels[0]} ~ {date_labels[4]}"

        # 다음 주 휴장일 정보
        from src.utils.market_holiday import get_next_week_holidays
        next_week_holidays = get_next_week_holidays(today.date())
        holiday_text = ""
        if next_week_holidays:
            holiday_lines = []
            for h in next_week_holidays:
                parts = []
                if h["krx"]:
                    parts.append(f"KRX 휴장({h['krx']})")
                if h["nyse"]:
                    parts.append(f"NYSE 휴장({h['nyse']})")
                holiday_lines.append(f"  - {h['date']}: {', '.join(parts)}")
            holiday_text = "\n\n⚠️ 다음 주 시장 휴장일:\n" + "\n".join(holiday_lines)

        prompt = f"""다음은 최근 주요 금융/경제 뉴스와 리포트입니다:

{news_text}{reports_text}{holiday_text}

위 내용을 바탕으로 다음 주({date_range}) 시장을 전망해주세요.

다음 주 각 거래일: {dates_list}

다음 JSON 형식으로 응답:
{{
    "week_outlook": "다음 주 시장 전체 전망 (3-4문장, 예상되는 흐름과 주요 변수)",
    "key_events": [
        "M/DD(요일) 구체적 이벤트 설명 (예: 2/24(월) FOMC 의사록 공개)",
        "M/DD(요일) 구체적 이벤트 설명",
        "M/DD(요일) 구체적 이벤트 설명",
        "M/DD(요일) 구체적 이벤트 설명"
    ],
    "watch_sectors": ["주목 섹터/테마 - 주목 이유 간략 설명", "섹터 2", "섹터 3"],
    "risk_factors": [
        "리스크 요인 설명 [1]",
        "리스크 요인 설명 [2]"
    ],
    "trading_strategy": "투자 전략 제안 (2-3문장). 본문에 [3][4] 같은 번호로 근거 표시",
    "key_levels": "코스피/코스닥 주요 지지/저항선 [5]",
    "sources": [
        "[매체명] 기사 제목",
        "[매체명] 기사 제목",
        "[매체명] 기사 제목",
        "[매체명] 기사 제목",
        "[매체명] 기사 제목"
    ]
}}

중요 지침:
- key_events: 각 이벤트는 반드시 구체적인 날짜(M/DD(요일))로 시작해야 합니다. 위 거래일 목록을 참고하세요.
- 출처 표기 규칙:
  * risk_factors, trading_strategy, key_levels 본문에는 [1], [2], [3] 같은 번호만 표기하세요.
  * sources 배열에 번호 순서대로 실제 출처를 나열하세요. (1번부터 시작)
  * 출처 형식: "[매체명] 기사 제목" (예: "[한국경제] 코스피 6000선 돌파 전망")
  * 본문과 sources 번호가 반드시 1:1로 매칭되어야 합니다.
- 제공된 뉴스에 언급되지 않은 이벤트를 추측하여 포함하지 마세요.
- 휴장일이 있으면 key_events에 포함하고, 거래일 축소에 따른 영향도 전략에 반영하세요."""

        result = self.client.generate_json(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=2000,
        )

        if result:
            logger.info("Weekly preview generated successfully")
        else:
            logger.warning("Failed to generate weekly preview")

        return result

    def _format_items_for_prompt(self, items: list[ContentItem]) -> str:
        """프롬프트용 아이템 포맷 (출처 참조용 설명 포함)"""
        lines = []
        for i, item in enumerate(items, 1):
            source = item.source or "Unknown"
            title = item.title
            date_str = ""
            if item.published_at:
                date_str = f" ({item.published_at.strftime('%m/%d')})"

            line = f"{i}. [{source}] {title}{date_str}"

            # 설명 포함 (AI가 출처로 참조할 수 있도록)
            if item.description:
                desc_short = item.description[:200].strip()
                if len(item.description) > 200:
                    desc_short += "..."
                line += f"\n   → {desc_short}"

            lines.append(line)

        return "\n".join(lines)


# 전역 인스턴스
weekly_summarizer = WeeklySummarizer()
weekly_preview = WeeklyPreview()
