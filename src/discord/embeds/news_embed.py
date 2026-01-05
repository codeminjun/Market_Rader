"""
뉴스용 Discord Embed 빌더
"""
from datetime import datetime
from discord_webhook import DiscordEmbed

from src.collectors.base import ContentItem, Priority


def get_importance_emoji(score: float) -> str:
    """중요도 점수에 따른 이모지"""
    if score >= 0.8:
        return "🔴"  # 긴급
    elif score >= 0.6:
        return "🟠"  # 중요
    elif score >= 0.4:
        return "🟡"  # 일반
    else:
        return "⚪"  # 참고


def get_priority_stars(priority: Priority) -> str:
    """우선순위에 따른 별 표시"""
    if priority == Priority.HIGH:
        return "⭐⭐⭐"
    elif priority == Priority.MEDIUM:
        return "⭐⭐"
    else:
        return "⭐"


def create_news_header_embed(
    date: datetime,
    news_count: int,
    summary: dict = None,
) -> DiscordEmbed:
    """
    뉴스 헤더 Embed 생성

    Args:
        date: 날짜
        news_count: 뉴스 개수
        summary: AI 요약 결과
    """
    date_str = date.strftime("%Y년 %m월 %d일 (%a)")

    embed = DiscordEmbed(
        title=f"📰 {date_str} 주식 뉴스 브리핑",
        description=f"오늘의 주요 뉴스 {news_count}건을 정리했습니다.",
        color="3498db",  # 파란색
    )

    if summary:
        # AI 요약 추가
        if "summary" in summary:
            embed.add_embed_field(
                name="📋 오늘의 요약",
                value=summary["summary"][:1000],
                inline=False,
            )

        if "key_points" in summary and summary["key_points"]:
            points_text = "\n".join([f"• {p}" for p in summary["key_points"][:5]])
            embed.add_embed_field(
                name="🎯 핵심 포인트",
                value=points_text[:1000],
                inline=False,
            )

        if "investment_insight" in summary:
            embed.add_embed_field(
                name="💡 투자 인사이트",
                value=summary["investment_insight"][:500],
                inline=False,
            )

    embed.set_footer(text="Market Rader Bot")
    embed.set_timestamp()

    return embed


def create_news_item_embed(
    item: ContentItem,
    show_summary: bool = True,
) -> DiscordEmbed:
    """
    단일 뉴스 Embed 생성

    Args:
        item: 뉴스 항목
        show_summary: 요약 표시 여부
    """
    # 제목에 중요도 표시
    importance_emoji = get_importance_emoji(item.importance_score)
    priority_stars = get_priority_stars(item.priority)

    title = f"{importance_emoji} {item.title}"
    if len(title) > 250:
        title = title[:247] + "..."

    # 색상 설정
    color_map = {
        Priority.HIGH: "e74c3c",    # 빨강
        Priority.MEDIUM: "f39c12",  # 주황
        Priority.LOW: "95a5a6",     # 회색
    }
    color = color_map.get(item.priority, "3498db")

    embed = DiscordEmbed(
        title=title,
        url=item.url,
        color=color,
    )

    # 출처 및 시간
    time_str = ""
    if item.published_at:
        time_str = item.published_at.strftime("%H:%M")

    source_text = f"📌 {item.source}"
    if time_str:
        source_text += f" | {time_str}"

    embed.add_embed_field(
        name="출처",
        value=source_text,
        inline=True,
    )

    embed.add_embed_field(
        name="중요도",
        value=priority_stars,
        inline=True,
    )

    # 요약/설명
    if show_summary and item.summary:
        embed.add_embed_field(
            name="💬 요약",
            value=item.summary[:500],
            inline=False,
        )
    elif item.description:
        desc = item.description[:300]
        if len(item.description) > 300:
            desc += "..."
        embed.add_embed_field(
            name="내용",
            value=desc,
            inline=False,
        )

    return embed


def create_news_list_embed(
    items: list[ContentItem],
    title: str = "📰 주요 뉴스",
    max_items: int = 10,
) -> DiscordEmbed:
    """
    뉴스 목록 Embed 생성 (압축형)

    Args:
        items: 뉴스 항목 리스트
        title: Embed 제목
        max_items: 최대 표시 개수
    """
    embed = DiscordEmbed(
        title=title,
        color="3498db",
    )

    news_lines = []
    for item in items[:max_items]:
        emoji = get_importance_emoji(item.importance_score)
        stars = get_priority_stars(item.priority)

        # 제목 길이 제한
        item_title = item.title
        if len(item_title) > 60:
            item_title = item_title[:57] + "..."

        line = f"{emoji} [{item_title}]({item.url})"
        news_lines.append(line)

    if news_lines:
        embed.description = "\n".join(news_lines)

    if len(items) > max_items:
        embed.set_footer(text=f"외 {len(items) - max_items}건 더 있음")

    return embed
