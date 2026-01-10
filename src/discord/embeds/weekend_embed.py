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


def create_weekly_review_embed(
    date: datetime,
    review_data: dict,
) -> list[DiscordEmbed]:
    """
    토요일 주간 리뷰 Embed 생성

    Args:
        date: 날짜
        review_data: WeeklySummarizer.generate_weekly_review() 결과

    Returns:
        DiscordEmbed 리스트
    """
    embeds = []

    # 이번 주 날짜 범위
    week_start = date - timedelta(days=date.weekday())
    week_end = week_start + timedelta(days=4)
    date_range = f"{week_start.strftime('%m/%d')} ~ {week_end.strftime('%m/%d')}"

    # 1. 메인 헤더 Embed
    header_embed = DiscordEmbed(
        title=f"{ScheduleSettings.SATURDAY_TITLE} ({date_range})",
        description="한 주간 시장을 돌아봅니다. 주요 이벤트와 시장 흐름을 정리했습니다.",
        color=WeekendEmbedColors.SATURDAY_REVIEW,
    )

    if review_data:
        # 주간 총평
        if "week_summary" in review_data:
            header_embed.add_embed_field(
                name="📋 이번 주 시장 총평",
                value=review_data["week_summary"][:1000],
                inline=False,
            )

        # 시장 심리
        if "market_sentiment" in review_data:
            header_embed.add_embed_field(
                name="🎭 시장 심리",
                value=review_data["market_sentiment"][:500],
                inline=False,
            )

    header_embed.set_footer(text="Market Rader - 주간 리뷰")
    header_embed.set_timestamp()
    embeds.append(header_embed)

    # 2. 주요 이벤트 & 수치 Embed
    if review_data:
        events_embed = DiscordEmbed(
            title="📌 이번 주 주요 이벤트",
            color=WeekendEmbedColors.SATURDAY_REVIEW,
        )

        # 주요 이벤트
        if "major_events" in review_data and review_data["major_events"]:
            events_text = "\n".join([f"• {e}" for e in review_data["major_events"][:5]])
            events_embed.add_embed_field(
                name="🔥 핵심 이벤트",
                value=events_text[:1000],
                inline=False,
            )

        # 주요 수치
        if "key_numbers" in review_data and review_data["key_numbers"]:
            numbers_text = "\n".join([f"📊 {n}" for n in review_data["key_numbers"][:5]])
            events_embed.add_embed_field(
                name="📈 주요 지표",
                value=numbers_text[:1000],
                inline=False,
            )

        embeds.append(events_embed)

    # 3. 섹터 분석 & 교훈 Embed
    if review_data:
        analysis_embed = DiscordEmbed(
            title="📊 섹터 분석 & 인사이트",
            color=WeekendEmbedColors.SATURDAY_REVIEW,
        )

        # 섹터 성과
        if "sector_performance" in review_data:
            analysis_embed.add_embed_field(
                name="🏭 섹터별 성과",
                value=review_data["sector_performance"][:800],
                inline=False,
            )

        # 교훈
        if "lessons_learned" in review_data:
            analysis_embed.add_embed_field(
                name="💡 이번 주의 교훈",
                value=review_data["lessons_learned"][:500],
                inline=False,
            )

        embeds.append(analysis_embed)

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
                value=risk_text[:800],
                inline=False,
            )

        # 투자 전략
        if "trading_strategy" in preview_data:
            strategy_embed.add_embed_field(
                name="💼 투자 전략 제안",
                value=preview_data["trading_strategy"][:800],
                inline=False,
            )

        # 주요 가격대
        if "key_levels" in preview_data:
            strategy_embed.add_embed_field(
                name="📊 주요 가격대",
                value=preview_data["key_levels"][:500],
                inline=False,
            )

        embeds.append(strategy_embed)

    return embeds
