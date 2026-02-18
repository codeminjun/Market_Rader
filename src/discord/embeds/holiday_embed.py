"""
시장 휴장일 Discord Embed 빌더
"""
from datetime import datetime

from discord_webhook import DiscordEmbed

from src.utils.market_holiday import MarketHolidayInfo


HOLIDAY_COLOR = "95a5a6"  # 회색 - 비활성/휴장 느낌


def create_holiday_embed(
    holiday_info: MarketHolidayInfo,
    date: datetime,
) -> DiscordEmbed:
    """
    휴장일 안내 Embed 생성

    Args:
        holiday_info: 휴장일 정보
        date: 날짜

    Returns:
        DiscordEmbed
    """
    date_str = date.strftime("%Y년 %m월 %d일 (%a)")

    # 본문 구성
    lines = [f"**{date_str}**\n"]

    if holiday_info.krx_closed and holiday_info.nyse_closed:
        lines.append("한국(KRX)과 미국(NYSE) 시장이 모두 휴장입니다.\n")
    elif holiday_info.krx_closed:
        lines.append("한국(KRX) 시장이 휴장입니다.\n")
    elif holiday_info.nyse_closed:
        lines.append("미국(NYSE) 시장이 휴장입니다.\n")

    # 휴일 상세
    details = []
    if holiday_info.krx_closed:
        details.append(f"🇰🇷 **KRX 휴장** — {holiday_info.krx_holiday_name}")
    else:
        details.append("🇰🇷 **KRX** — 정상 개장")

    if holiday_info.nyse_closed:
        details.append(f"🇺🇸 **NYSE 휴장** — {holiday_info.nyse_holiday_name}")
    else:
        details.append("🇺🇸 **NYSE** — 정상 개장")

    lines.append("\n".join(details))

    embed = DiscordEmbed(
        title="🏖️ 시장 휴일 안내",
        description="\n".join(lines),
        color=HOLIDAY_COLOR,
    )

    embed.set_footer(text="다음 영업일에 다시 찾아올게요 👋")
    embed.set_timestamp(date.isoformat())

    return embed
