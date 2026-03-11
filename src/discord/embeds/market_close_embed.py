"""
장 마감 시장 요약 Discord Embed 빌더
"""
from datetime import datetime
from discord_webhook import DiscordEmbed

from src.collectors.market.market_data import MarketSummary, IndexData, ExchangeRate
from src.utils.constants import EmbedColors


def get_change_emoji(is_up: bool, change_percent: float) -> str:
    """변동에 따른 이모지 반환"""
    if abs(change_percent) < 0.1:
        return "➡️"  # 보합
    elif is_up:
        if change_percent >= 2.0:
            return "🔺"  # 급등
        return "📈"  # 상승
    else:
        if change_percent <= -2.0:
            return "🔻"  # 급락
        return "📉"  # 하락


def format_index_value(data: IndexData) -> str:
    """지수 데이터 포맷팅"""
    emoji = get_change_emoji(data.is_up, data.change_percent)
    sign = "+" if data.change >= 0 else ""
    return f"{emoji} **{data.value:,.2f}** ({sign}{data.change:,.2f}, {sign}{data.change_percent:.2f}%)"


def format_exchange_value(data: ExchangeRate) -> str:
    """환율 데이터 포맷팅"""
    emoji = get_change_emoji(data.is_up, data.change_percent)
    sign = "+" if data.change >= 0 else ""
    return f"{emoji} **{data.value:,.2f}** ({sign}{data.change:.2f})"


def format_commodity_value(data: IndexData) -> str:
    """원자재 데이터 포맷팅"""
    emoji = get_change_emoji(data.is_up, data.change_percent)
    sign = "+" if data.change >= 0 else ""
    return f"{emoji} **{data.value:,.2f}** ({sign}{data.change:.2f})"


def create_market_close_embed(
    market_data: MarketSummary,
    date: datetime = None,
) -> DiscordEmbed:
    """
    장 마감 시장 요약 Embed 생성

    Args:
        market_data: 시장 데이터
        date: 날짜 (기본값: 현재)
    """
    date = date or datetime.now()
    date_str = date.strftime("%Y년 %m월 %d일")

    # 전체 시장 분위기 판단 (코스피 가중 70%)
    market_mood = "🟢"  # 기본
    if market_data.kospi and market_data.kosdaq:
        weighted_change = (
            market_data.kospi.change_percent * 0.7
            + market_data.kosdaq.change_percent * 0.3
        )
        if weighted_change >= 2.0:
            market_mood = "🟢 강세"
        elif weighted_change >= 0.5:
            market_mood = "🟢 상승세"
        elif weighted_change >= -0.5:
            market_mood = "🟡 보합세"
        elif weighted_change >= -2.0:
            market_mood = "🟠 약세"
        else:
            market_mood = "🔴 약세"

    embed = DiscordEmbed(
        title=f"📊 {date_str} 장 마감 시황",
        description=f"오늘의 시장: **{market_mood}**",
        color=EmbedColors.NEWS_KOREAN,
    )

    # 1. 국내 증시
    index_lines = []
    if market_data.kospi:
        index_lines.append(f"**코스피**: {format_index_value(market_data.kospi)}")
    if market_data.kosdaq:
        index_lines.append(f"**코스닥**: {format_index_value(market_data.kosdaq)}")

    if index_lines:
        embed.add_embed_field(
            name="🇰🇷 국내 증시",
            value="\n".join(index_lines),
            inline=False,
        )

    # 2. 환율
    exchange_lines = []
    if market_data.usd_krw:
        exchange_lines.append(f"**USD/KRW**: {format_exchange_value(market_data.usd_krw)}")
    if market_data.jpy_krw:
        # 일본 엔화는 100엔 기준이므로 표시 조정
        exchange_lines.append(f"**JPY/KRW (100엔)**: {format_exchange_value(market_data.jpy_krw)}")
    if market_data.eur_krw:
        exchange_lines.append(f"**EUR/KRW**: {format_exchange_value(market_data.eur_krw)}")

    if exchange_lines:
        embed.add_embed_field(
            name="💱 환율",
            value="\n".join(exchange_lines),
            inline=False,
        )

    # 3. 원자재
    commodity_lines = []
    if market_data.wti:
        commodity_lines.append(f"**WTI 유가**: {format_commodity_value(market_data.wti)}")
    if market_data.gold:
        commodity_lines.append(f"**국제 금**: {format_commodity_value(market_data.gold)}")

    if commodity_lines:
        embed.add_embed_field(
            name="🛢️ 원자재",
            value="\n".join(commodity_lines),
            inline=False,
        )

    # 푸터
    if market_data.timestamp:
        embed.set_footer(text=f"📅 {market_data.timestamp} 기준 | 네이버 금융")

    return embed


def create_market_summary_text(market_data: MarketSummary) -> str:
    """
    시장 요약 텍스트 생성 (간략 버전)

    Args:
        market_data: 시장 데이터

    Returns:
        한 줄 요약 텍스트
    """
    parts = []

    if market_data.kospi:
        sign = "+" if market_data.kospi.change >= 0 else ""
        emoji = "📈" if market_data.kospi.is_up else "📉"
        parts.append(f"코스피 {market_data.kospi.value:,.0f} ({sign}{market_data.kospi.change_percent:.1f}%){emoji}")

    if market_data.usd_krw:
        sign = "+" if market_data.usd_krw.change >= 0 else ""
        emoji = "↑" if market_data.usd_krw.is_up else "↓"
        parts.append(f"원/달러 {market_data.usd_krw.value:,.0f}{emoji}")

    return " | ".join(parts) if parts else ""
