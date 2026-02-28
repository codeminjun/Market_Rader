"""
주말용 Discord Embed 빌더
토요일: 주간 리뷰 / 일요일: 주간 전망
"""
from datetime import datetime, timedelta
from discord_webhook import DiscordEmbed

from src.utils.constants import EmbedColors, ScheduleSettings


class WeekendEmbedColors:
    """주말 Embed 색상"""
    SATURDAY_REVIEW = "2ecc71"   # 초록 (리뷰/회고)
    SUNDAY_PREVIEW = "9b59b6"   # 보라 (전망/예측)


def _match_source_url(source_text: str, source_items: list[dict]) -> str | None:
    """AI가 출력한 출처 텍스트를 원본 뉴스 URL과 매칭

    Args:
        source_text: "[매체명] 기사 제목" 형식
        source_items: [{"title": ..., "url": ..., "source": ...}, ...]

    Returns:
        매칭된 URL 또는 None
    """
    if not source_items:
        return None

    # "[매체명] 기사 제목"에서 기사 제목 부분 추출
    title_part = source_text
    if "]" in source_text:
        title_part = source_text.split("]", 1)[1].strip()

    # 1. 제목 완전 포함 매칭
    for item in source_items:
        if title_part and title_part in item["title"]:
            return item["url"]

    # 2. 원본 제목이 출처 텍스트에 포함되는지
    for item in source_items:
        if item["title"] in source_text:
            return item["url"]

    # 3. 핵심 키워드 매칭 (제목에서 주요 단어 추출 후 비교)
    title_words = [w for w in title_part.split() if len(w) >= 2]
    if title_words:
        best_match = None
        best_score = 0
        for item in source_items:
            score = sum(1 for w in title_words if w in item["title"])
            if score > best_score and score >= max(2, len(title_words) // 2):
                best_score = score
                best_match = item
        if best_match:
            return best_match["url"]

    return None


def _format_market_index_table(market_index_history: dict, ref_date: datetime) -> str:
    """시장 지수를 월~금 테이블 형태로 포맷 (7개 지표)"""
    if not market_index_history:
        return ""

    # 이번 주 월~금 날짜 목록 생성
    week_start = ref_date - timedelta(days=ref_date.weekday())
    weekdays = []
    for i in range(5):
        day = week_start + timedelta(days=i)
        weekdays.append(day.strftime("%Y-%m-%d"))

    day_labels = ["월", "화", "수", "목", "금"]

    def format_index_row(name: str, key: str) -> str:
        """한 지수의 월~금 행 포맷"""
        parts = []
        for i, date_key in enumerate(weekdays):
            day_data = market_index_history.get(date_key, {}).get(key)
            if day_data:
                sign = "+" if day_data["change_percent"] >= 0 else ""
                arrow = "▲" if day_data["change_percent"] >= 0 else "▼"
                parts.append(f"`{day_labels[i]}` {day_data['value']:,.2f} {arrow}{abs(day_data['change_percent']):.1f}%")
            else:
                parts.append(f"`{day_labels[i]}` 휴장")
        return f"**{name}**\n" + " ┃ ".join(parts)

    def format_weekly_change(name: str, key: str, weekly_summary: dict) -> str:
        """주간 변동률 한 줄 요약"""
        data = weekly_summary.get(key)
        if not data:
            return ""
        sign = "+" if data["change_pct"] >= 0 else ""
        arrow = "▲" if data["change_pct"] >= 0 else "▼"
        return f"**{name}** {data['end']:,.2f} ({arrow}{abs(data['change_pct']):.2f}%)"

    # 7개 지표 정의
    indicators = [
        ("코스피", "kospi"),
        ("코스닥", "kosdaq"),
        ("USD/KRW", "usd_krw"),
        ("JPY/KRW", "jpy_krw"),
        ("EUR/KRW", "eur_krw"),
        ("WTI", "wti"),
        ("Gold", "gold"),
    ]

    lines = []

    # 주요 지표 (코스피/코스닥/USD) - 일별 상세 테이블
    for name, key in indicators[:3]:
        has_data = any(market_index_history.get(d, {}).get(key) for d in weekdays)
        if has_data:
            lines.append(format_index_row(name, key))

    return "\n\n".join(lines)


def _format_weekly_summary_text(market_index_history: dict, weekly_summary: dict) -> str:
    """주간 변동률 요약 텍스트 (JPY/EUR/WTI/Gold 등 보조 지표)"""
    if not weekly_summary:
        return ""

    # 보조 지표들의 주간 변동 한 줄 요약
    sub_indicators = [
        ("JPY/KRW", "jpy_krw"),
        ("EUR/KRW", "eur_krw"),
        ("WTI", "wti"),
        ("Gold", "gold"),
    ]

    lines = []
    for name, key in sub_indicators:
        data = weekly_summary.get(key)
        if data:
            sign = "+" if data["change_pct"] >= 0 else ""
            arrow = "▲" if data["change_pct"] >= 0 else "▼"
            lines.append(f"{arrow} **{name}** {data['end']:,.2f} ({sign}{data['change_pct']:.2f}%)")

    return "\n".join(lines)


def _format_sector_etf_for_embed(sector_etf_history: dict) -> str:
    """섹터 ETF 주간 이력을 Discord Embed 텍스트로 포맷"""
    if not sector_etf_history:
        return ""

    sorted_dates = sorted(sector_etf_history.keys())

    # 모든 섹터 수집 + 주간 누적 등락률 계산
    sector_totals = {}
    for date_key in sorted_dates:
        for sector, data in sector_etf_history[date_key].items():
            if sector not in sector_totals:
                sector_totals[sector] = {
                    "etf_name": data.get("etf_name", ""),
                    "total": 0,
                    "days": 0,
                }
            sector_totals[sector]["total"] += data["change_percent"]
            sector_totals[sector]["days"] += 1

    # 주간 등락률 순으로 정렬 (강세 → 약세)
    sorted_sectors = sorted(sector_totals.items(), key=lambda x: x[1]["total"], reverse=True)

    lines = []
    for sector, info in sorted_sectors:
        total = info["total"]
        sign = "+" if total >= 0 else ""
        # 등락 이모지
        if total >= 3:
            emoji = "🔴"
        elif total >= 1:
            emoji = "🟠"
        elif total >= -1:
            emoji = "⚪"
        elif total >= -3:
            emoji = "🔵"
        else:
            emoji = "⬇️"
        lines.append(f"{emoji} **{sector}** ({info['etf_name']}): {sign}{total:.2f}%")

    return "\n".join(lines)


def _build_events_from_archive(archived_items: list[dict]) -> str:
    """아카이브 뉴스에서 날짜별 핵심 이벤트 목록 생성 (크롤링 100%)"""
    if not archived_items:
        return ""

    from collections import defaultdict

    # 날짜별 그룹핑
    by_date = defaultdict(list)
    weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
    for item in archived_items:
        pub_date = item.get("published_at", "")
        if pub_date:
            try:
                dt = datetime.fromisoformat(pub_date)
                date_key = f"{dt.strftime('%m/%d')}({weekday_names[dt.weekday()]})"
            except (ValueError, TypeError):
                continue
        else:
            continue
        by_date[date_key].append(item)

    # 날짜순 정렬, 각 날짜에서 중요도 상위 2개만
    lines = []
    for date_key in sorted(by_date.keys()):
        items = by_date[date_key]
        items.sort(key=lambda x: x.get("importance_score", 0), reverse=True)
        for item in items[:2]:
            source = item.get("source", "")
            title = item.get("title", "")
            source_tag = f" ({source})" if source else ""
            lines.append(f"📌 **{date_key}** {title}{source_tag}")

    return "\n".join(lines[:10])  # 최대 10개


def _build_sources_list(archived_items: list[dict]) -> str:
    """중요도 순 출처 목록 생성 (크롤링 100%, 클릭 가능 링크)"""
    if not archived_items:
        return ""

    # 중요도 순 정렬
    sorted_items = sorted(archived_items, key=lambda x: x.get("importance_score", 0), reverse=True)

    lines = []
    for item in sorted_items[:8]:
        source = item.get("source", "")
        title = item.get("title", "")
        url = item.get("url", "")
        # Discord 마크다운 대괄호 이스케이프
        safe_title = title.replace("[", "\\[").replace("]", "\\]")
        if url:
            lines.append(f"• [{source}] [{safe_title}]({url})")
        else:
            lines.append(f"• [{source}] {title}")

    return "\n".join(lines)


def create_weekly_review_embed(
    date: datetime,
    review_data: dict,
    archived_items: list[dict] = None,
    weekly_summary_data: dict = None,
    market_index_history: dict = None,
    sector_etf_history: dict = None,
) -> list[DiscordEmbed]:
    """
    토요일 주간 리뷰 Embed 생성 (데이터 기반 4-Embed 구조)

    Args:
        date: 날짜
        review_data: AI 정성적 분석 결과 (weekly_summary, sector_insights, next_week_watchpoints)
        archived_items: 주간 아카이브 뉴스/리포트
        weekly_summary_data: 주간 변동률 자동 계산 데이터
        market_index_history: 시장 지수 일별 이력 (크롤링)
        sector_etf_history: 섹터 ETF 일별 이력 (크롤링)

    Returns:
        DiscordEmbed 리스트
    """
    embeds = []

    # 이번 주 날짜 범위
    week_start = date - timedelta(days=date.weekday())
    week_end = week_start + timedelta(days=4)
    date_range = f"{week_start.strftime('%m/%d')} ~ {week_end.strftime('%m/%d')}"

    # --- Embed 1: 주간 총평 (AI 정성적 요약) ---
    header_embed = DiscordEmbed(
        title=f"{ScheduleSettings.SATURDAY_TITLE} ({date_range})",
        description="한 주간 시장을 돌아봅니다.",
        color=WeekendEmbedColors.SATURDAY_REVIEW,
    )

    if review_data:
        summary_text = review_data.get("weekly_summary", "")
        if summary_text:
            header_embed.add_embed_field(
                name="📋 이번 주 시장 총평",
                value=summary_text[:1000],
                inline=False,
            )

        # 다음 주 주목 포인트 (AI)
        watchpoints = review_data.get("next_week_watchpoints", "")
        if watchpoints:
            header_embed.add_embed_field(
                name="👀 다음 주 주목 포인트",
                value=watchpoints[:500],
                inline=False,
            )

    header_embed.set_footer(text="Market Rader - 주간 리뷰")
    header_embed.set_timestamp()
    embeds.append(header_embed)

    # --- Embed 2: 주요 지표 (크롤링 100%) ---
    market_index_history = market_index_history or {}
    weekly_summary_data = weekly_summary_data or {}

    if market_index_history or weekly_summary_data:
        index_embed = DiscordEmbed(
            title="📈 주요 지표 (월~금)",
            color=WeekendEmbedColors.SATURDAY_REVIEW,
        )

        # 코스피/코스닥/USD 일별 테이블
        if market_index_history:
            table_text = _format_market_index_table(market_index_history, date)
            if table_text:
                index_embed.add_embed_field(
                    name="📊 주요 시장 지표",
                    value=table_text[:1024],
                    inline=False,
                )

        # 보조 지표 (JPY/EUR/WTI/Gold) 주간 변동 요약
        sub_text = _format_weekly_summary_text(market_index_history, weekly_summary_data)
        if sub_text:
            index_embed.add_embed_field(
                name="🌐 기타 지표 (주간 변동)",
                value=sub_text[:1024],
                inline=False,
            )

        # 주요 지표 주간 변동률 요약 한 줄
        main_summary_parts = []
        for name, key in [("코스피", "kospi"), ("코스닥", "kosdaq"), ("USD/KRW", "usd_krw")]:
            data = weekly_summary_data.get(key)
            if data:
                sign = "+" if data["change_pct"] >= 0 else ""
                main_summary_parts.append(f"{name} {sign}{data['change_pct']:.2f}%")
        if main_summary_parts:
            index_embed.add_embed_field(
                name="📉 주간 등락",
                value=" ┃ ".join(main_summary_parts),
                inline=False,
            )

        embeds.append(index_embed)

    # --- Embed 3: 섹터 분석 (ETF 등락률 크롤링 + AI 원인 분석 혼합) ---
    sector_etf_history = sector_etf_history or {}
    if sector_etf_history or (review_data and review_data.get("sector_insights")):
        sector_embed = DiscordEmbed(
            title="📊 섹터 분석",
            color=WeekendEmbedColors.SATURDAY_REVIEW,
        )

        # 섹터 ETF 등락률 (크롤링)
        if sector_etf_history:
            etf_lines = _format_sector_etf_for_embed(sector_etf_history)
            if etf_lines:
                sector_embed.add_embed_field(
                    name="📈 섹터 ETF 주간 등락률",
                    value=etf_lines[:1024],
                    inline=False,
                )

        # AI 섹터 인사이트 (원인 분석)
        if review_data:
            sector_insights = review_data.get("sector_insights", {})
            if sector_insights and isinstance(sector_insights, dict):
                insight_lines = []
                for sector, insight in sector_insights.items():
                    insight_lines.append(f"**{sector}**\n> {insight}")
                if insight_lines:
                    sector_embed.add_embed_field(
                        name="🔍 섹터별 원인 분석",
                        value="\n\n".join(insight_lines)[:1024],
                        inline=False,
                    )

        embeds.append(sector_embed)

    # --- Embed 4: 핵심 이벤트 & 출처 (크롤링 100%) ---
    archived_items = archived_items or []
    if archived_items:
        events_embed = DiscordEmbed(
            title="📌 이번 주 핵심 이벤트 & 출처",
            color=WeekendEmbedColors.SATURDAY_REVIEW,
        )

        # 날짜별 주요 이벤트
        events_text = _build_events_from_archive(archived_items)
        if events_text:
            events_embed.add_embed_field(
                name="🔥 주요 이벤트",
                value=events_text[:1024],
                inline=False,
            )

        # 중요도 순 출처 목록
        sources_text = _build_sources_list(archived_items)
        if sources_text:
            events_embed.add_embed_field(
                name="📎 주요 출처",
                value=sources_text[:1024],
                inline=False,
            )

        events_embed.set_footer(text="Market Rader - 주간 리뷰")
        events_embed.set_timestamp()
        embeds.append(events_embed)

    return embeds


def create_weekly_preview_embed(
    date: datetime,
    preview_data: dict,
) -> list[DiscordEmbed]:
    """
    일요일 주간 전망 Embed 생성

    Args:
        date: 날짜
        preview_data: WeeklyPreview.generate_weekly_preview() 결과

    Returns:
        DiscordEmbed 리스트
    """
    embeds = []

    # 다음 주 날짜 범위
    days_until_monday = (7 - date.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = date + timedelta(days=days_until_monday)
    next_friday = next_monday + timedelta(days=4)
    date_range = f"{next_monday.strftime('%m/%d')} ~ {next_friday.strftime('%m/%d')}"

    # 1. 메인 헤더 Embed
    header_embed = DiscordEmbed(
        title=f"{ScheduleSettings.SUNDAY_TITLE} ({date_range})",
        description="새로운 한 주를 준비합니다. 다가오는 주의 주요 이벤트와 투자 전략을 안내합니다.",
        color=WeekendEmbedColors.SUNDAY_PREVIEW,
    )

    if preview_data:
        # 주간 전망
        if "week_outlook" in preview_data:
            header_embed.add_embed_field(
                name="🔮 다음 주 시장 전망",
                value=preview_data["week_outlook"][:1000],
                inline=False,
            )

    header_embed.set_footer(text="Market Rader - 주간 전망")
    header_embed.set_timestamp()
    embeds.append(header_embed)

    # 2. 주요 이벤트 & 주목 섹터 Embed
    if preview_data:
        events_embed = DiscordEmbed(
            title="📅 다음 주 주목 포인트",
            color=WeekendEmbedColors.SUNDAY_PREVIEW,
        )

        # 주요 이벤트
        if "key_events" in preview_data and preview_data["key_events"]:
            events_text = "\n".join([f"📌 {e}" for e in preview_data["key_events"][:5]])
            events_embed.add_embed_field(
                name="🗓️ 주요 일정",
                value=events_text[:1000],
                inline=False,
            )

        # 주목 섹터
        if "watch_sectors" in preview_data and preview_data["watch_sectors"]:
            sectors_text = "\n".join([f"🎯 {s}" for s in preview_data["watch_sectors"][:5]])
            events_embed.add_embed_field(
                name="🏭 주목 섹터",
                value=sectors_text[:800],
                inline=False,
            )

        embeds.append(events_embed)

    # 3. 리스크 & 전략 Embed
    if preview_data:
        strategy_embed = DiscordEmbed(
            title="⚔️ 투자 전략 & 리스크",
            color=WeekendEmbedColors.SUNDAY_PREVIEW,
        )

        # 리스크 요인
        if "risk_factors" in preview_data and preview_data["risk_factors"]:
            risk_text = "\n".join([f"⚠️ {r}" for r in preview_data["risk_factors"][:4]])
            strategy_embed.add_embed_field(
                name="🚨 리스크 요인",
                value=risk_text[:1024],
                inline=False,
            )

        # 투자 전략
        if "trading_strategy" in preview_data:
            strategy_embed.add_embed_field(
                name="💼 투자 전략 제안",
                value=preview_data["trading_strategy"][:1024],
                inline=False,
            )

        # 주요 가격대
        if "key_levels" in preview_data:
            strategy_embed.add_embed_field(
                name="📊 주요 가격대",
                value=preview_data["key_levels"][:1024],
                inline=False,
            )

        # 출처 목록 (번호 참조 + 클릭 가능 링크)
        sources = preview_data.get("sources", [])
        if sources:
            source_items = preview_data.get("_source_items", [])
            sources_lines = []
            for i, source_text in enumerate(sources):
                url = _match_source_url(source_text, source_items)
                if url:
                    sources_lines.append(f"`[{i+1}]` [{source_text}]({url})")
                else:
                    sources_lines.append(f"`[{i+1}]` {source_text}")
            strategy_embed.add_embed_field(
                name="📎 참고 출처",
                value="\n".join(sources_lines)[:1024],
                inline=False,
            )

        embeds.append(strategy_embed)

    return embeds
