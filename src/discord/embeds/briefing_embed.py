"""
AI 비서 브리핑 Discord Embed 빌더
장 마감 리뷰 및 아침 전략 브리핑용
"""
from datetime import datetime
from discord_webhook import DiscordEmbed

from src.analyzer.market_briefing import MarketBriefing


class BriefingColors:
    """브리핑 색상"""
    POSITIVE = 0x00D26A   # 녹색 (긍정적)
    NEUTRAL = 0x5865F2    # 파란색 (중립)
    NEGATIVE = 0xED4245   # 빨간색 (부정적)
    MORNING = 0xFFA500    # 주황색 (아침)
    EVENING = 0x9B59B6    # 보라색 (저녁)


def get_mood_color(mood: str, is_morning: bool = False) -> int:
    """분위기에 따른 색상 반환"""
    if mood == "positive":
        return BriefingColors.POSITIVE
    elif mood == "negative":
        return BriefingColors.NEGATIVE
    else:
        return BriefingColors.MORNING if is_morning else BriefingColors.EVENING


def get_mood_emoji(mood: str) -> str:
    """분위기에 따른 이모지 반환"""
    if mood == "positive":
        return "😊"
    elif mood == "negative":
        return "😟"
    else:
        return "🤔"


def create_assistant_briefing_embed(
    briefing: MarketBriefing,
    briefing_type: str = "closing",  # "closing" or "morning"
    date: datetime = None,
) -> DiscordEmbed:
    """
    AI 비서 브리핑 Embed 생성

    Args:
        briefing: MarketBriefing 객체
        briefing_type: "closing" (장 마감) 또는 "morning" (아침)
        date: 날짜

    Returns:
        DiscordEmbed 객체
    """
    date = date or datetime.now()
    is_morning = briefing_type == "morning"

    # 제목 설정
    if is_morning:
        title = f"🌅 오늘의 시장 전략 브리핑"
        date_str = date.strftime("%m월 %d일 아침")
    else:
        title = f"🌆 오늘의 장 마감 리뷰"
        date_str = date.strftime("%m월 %d일 장 마감")

    # 색상 설정
    color = get_mood_color(briefing.mood, is_morning)
    mood_emoji = get_mood_emoji(briefing.mood)

    embed = DiscordEmbed(
        title=title,
        description=f"**{briefing.greeting}** {mood_emoji}",
        color=color,
    )

    # 날짜 표시
    embed.set_author(name=f"📅 {date_str}")

    # 1. 핵심 요약
    if briefing.summary:
        embed.add_embed_field(
            name="📋 이렇게 요약했어요",
            value=briefing.summary,
            inline=False,
        )

    # 2. 주요 포인트
    if briefing.key_points:
        points_text = "\n".join([f"• {point}" for point in briefing.key_points[:5]])
        field_name = "🎯 오늘 이런 점을 주목하세요" if is_morning else "📌 오늘 이런 일이 있었어요"
        embed.add_embed_field(
            name=field_name,
            value=points_text,
            inline=False,
        )

    # 3. 액션 아이템 / 주의사항
    if briefing.action_items:
        actions_text = "\n".join([f"✓ {item}" for item in briefing.action_items[:3]])
        field_name = "💡 오늘은 이걸 체크하세요" if is_morning else "⚡ 내일은 이걸 눈여겨보세요"
        embed.add_embed_field(
            name=field_name,
            value=actions_text,
            inline=False,
        )

    # 4. 참고 출처 (있는 경우)
    if briefing.sources:
        sources_text = " | ".join(briefing.sources[:4])
        embed.add_embed_field(
            name="📰 이 자료들을 참고했어요",
            value=sources_text,
            inline=False,
        )

    # 5. 마무리 멘트
    if briefing.closing:
        embed.set_footer(text=f"💬 {briefing.closing}")

    return embed


def create_closing_review_embed(
    briefing: MarketBriefing,
    date: datetime = None,
) -> DiscordEmbed:
    """장 마감 리뷰 Embed 생성 (단축 함수)"""
    return create_assistant_briefing_embed(briefing, "closing", date)


def create_morning_strategy_embed(
    briefing: MarketBriefing,
    date: datetime = None,
) -> DiscordEmbed:
    """아침 전략 Embed 생성 (단축 함수)"""
    return create_assistant_briefing_embed(briefing, "morning", date)
