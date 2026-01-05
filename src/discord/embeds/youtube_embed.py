"""
유튜브용 Discord Embed 빌더
"""
from discord_webhook import DiscordEmbed

from src.collectors.base import ContentItem, Priority


def get_priority_indicator(priority: Priority) -> str:
    """우선순위 표시"""
    if priority == Priority.HIGH:
        return "⭐⭐⭐ [필수 시청]"
    elif priority == Priority.MEDIUM:
        return "⭐⭐ [추천]"
    else:
        return "⭐ [참고]"


def create_youtube_header_embed(video_count: int) -> DiscordEmbed:
    """
    유튜브 섹션 헤더 Embed 생성

    Args:
        video_count: 영상 개수
    """
    embed = DiscordEmbed(
        title=f"🎬 새 유튜브 영상 ({video_count}건)",
        description="구독 중인 채널의 새 영상입니다.",
        color="e74c3c",  # 빨간색 (YouTube 색상)
    )

    return embed


def create_youtube_item_embed(
    item: ContentItem,
    summary: dict = None,
) -> DiscordEmbed:
    """
    단일 유튜브 영상 Embed 생성

    Args:
        item: 유튜브 영상 항목
        summary: AI 요약 결과
    """
    # 제목
    title = item.title
    if len(title) > 200:
        title = title[:197] + "..."

    # 우선순위 표시
    priority_text = get_priority_indicator(item.priority)

    embed = DiscordEmbed(
        title=f"🎬 {title}",
        url=item.url,
        color="e74c3c",  # YouTube 빨간색
    )

    # 채널명
    embed.add_embed_field(
        name="채널",
        value=f"📺 {item.source}",
        inline=True,
    )

    # 중요도
    embed.add_embed_field(
        name="중요도",
        value=priority_text,
        inline=True,
    )

    # 업로드 시간
    if item.published_at:
        time_str = item.published_at.strftime("%m/%d %H:%M")
        embed.add_embed_field(
            name="업로드",
            value=time_str,
            inline=True,
        )

    # AI 요약
    if summary:
        if "summary" in summary:
            embed.add_embed_field(
                name="📝 영상 요약",
                value=summary["summary"][:800],
                inline=False,
            )

        if "key_points" in summary and summary["key_points"]:
            points_text = "\n".join([f"• {p}" for p in summary["key_points"][:4]])
            embed.add_embed_field(
                name="🎯 핵심 포인트",
                value=points_text[:500],
                inline=False,
            )

        if "investment_relevance" in summary:
            embed.add_embed_field(
                name="💡 투자 시사점",
                value=summary["investment_relevance"][:300],
                inline=False,
            )
    elif item.description:
        # 요약이 없으면 설명 사용
        desc = item.description[:400]
        if len(item.description) > 400:
            desc += "..."
        embed.add_embed_field(
            name="설명",
            value=desc,
            inline=False,
        )

    # 썸네일
    if item.thumbnail_url:
        embed.set_thumbnail(url=item.thumbnail_url)

    return embed


def create_youtube_list_embed(
    items: list[ContentItem],
    title: str = "🎬 새 유튜브 영상",
    max_items: int = 10,
) -> DiscordEmbed:
    """
    유튜브 목록 Embed 생성 (압축형)

    Args:
        items: 유튜브 항목 리스트
        title: Embed 제목
        max_items: 최대 표시 개수
    """
    embed = DiscordEmbed(
        title=title,
        color="e74c3c",
    )

    video_lines = []
    for item in items[:max_items]:
        # 우선순위 이모지
        if item.priority == Priority.HIGH:
            priority_emoji = "⭐⭐⭐"
        elif item.priority == Priority.MEDIUM:
            priority_emoji = "⭐⭐"
        else:
            priority_emoji = "⭐"

        # 채널명
        channel = item.source
        if len(channel) > 15:
            channel = channel[:12] + "..."

        # 제목 길이 제한
        item_title = item.title
        if len(item_title) > 45:
            item_title = item_title[:42] + "..."

        line = f"{priority_emoji} **{channel}**\n└ [{item_title}]({item.url})"
        video_lines.append(line)

    if video_lines:
        embed.description = "\n\n".join(video_lines)

    if len(items) > max_items:
        embed.set_footer(text=f"외 {len(items) - max_items}건 더 있음")

    return embed


def create_youtube_quick_embed(
    item: ContentItem,
    quick_summary: str = None,
) -> DiscordEmbed:
    """
    간단한 유튜브 알림 Embed (빠른 알림용)

    Args:
        item: 유튜브 영상 항목
        quick_summary: 빠른 요약
    """
    priority_text = get_priority_indicator(item.priority)

    title = item.title
    if len(title) > 150:
        title = title[:147] + "..."

    embed = DiscordEmbed(
        title=f"🎬 {item.source}",
        description=f"**{title}**\n\n{priority_text}",
        url=item.url,
        color="e74c3c",
    )

    if quick_summary:
        embed.add_embed_field(
            name="📝 한줄 요약",
            value=quick_summary[:300],
            inline=False,
        )

    if item.thumbnail_url:
        embed.set_thumbnail(url=item.thumbnail_url)

    return embed
