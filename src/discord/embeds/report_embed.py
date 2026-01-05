"""
애널리스트 리포트용 Discord Embed 빌더
"""
from discord_webhook import DiscordEmbed

from src.collectors.base import ContentItem


def create_reports_header_embed(
    report_count: int,
    summary: dict = None,
) -> DiscordEmbed:
    """
    리포트 섹션 헤더 Embed 생성

    Args:
        report_count: 리포트 개수
        summary: AI 요약 결과
    """
    embed = DiscordEmbed(
        title=f"📊 애널리스트 리포트 ({report_count}건)",
        color="9b59b6",  # 보라색
    )

    if summary:
        if "summary" in summary:
            embed.add_embed_field(
                name="📋 리포트 요약",
                value=summary["summary"][:1000],
                inline=False,
            )

        if "recommendations" in summary and summary["recommendations"]:
            rec_text = "\n".join([f"• {r}" for r in summary["recommendations"][:5]])
            embed.add_embed_field(
                name="💡 주요 추천",
                value=rec_text[:1000],
                inline=False,
            )

        if "sectors_focus" in summary and summary["sectors_focus"]:
            sectors_text = ", ".join(summary["sectors_focus"][:5])
            embed.add_embed_field(
                name="🎯 주목 섹터",
                value=sectors_text,
                inline=False,
            )

    return embed


def create_report_item_embed(item: ContentItem) -> DiscordEmbed:
    """
    단일 리포트 Embed 생성

    Args:
        item: 리포트 항목
    """
    title = item.title
    if len(title) > 250:
        title = title[:247] + "..."

    embed = DiscordEmbed(
        title=f"📄 {title}",
        url=item.url,
        color="9b59b6",  # 보라색
    )

    # 출처 (증권사)
    embed.add_embed_field(
        name="증권사",
        value=item.source,
        inline=True,
    )

    # 카테고리
    if item.extra_data.get("category"):
        embed.add_embed_field(
            name="분류",
            value=item.extra_data["category"],
            inline=True,
        )

    # 종목명 (기업분석의 경우)
    if item.extra_data.get("stock_name"):
        embed.add_embed_field(
            name="종목",
            value=item.extra_data["stock_name"],
            inline=True,
        )

    # 날짜
    if item.published_at:
        date_str = item.published_at.strftime("%Y-%m-%d")
        embed.add_embed_field(
            name="발행일",
            value=date_str,
            inline=True,
        )

    return embed


def create_reports_list_embed(
    items: list[ContentItem],
    title: str = "📊 애널리스트 리포트",
    max_items: int = 10,
) -> DiscordEmbed:
    """
    리포트 목록 Embed 생성 (압축형)

    Args:
        items: 리포트 항목 리스트
        title: Embed 제목
        max_items: 최대 표시 개수
    """
    embed = DiscordEmbed(
        title=title,
        color="9b59b6",
    )

    report_lines = []
    for item in items[:max_items]:
        # 증권사 추출
        broker = item.extra_data.get("broker", "")
        if broker:
            broker_tag = f"[{broker}]"
        else:
            broker_tag = ""

        # 종목명
        stock = item.extra_data.get("stock_name", "")
        if stock:
            stock_tag = f"[{stock}]"
        else:
            stock_tag = ""

        # 제목 길이 제한
        item_title = item.title
        if len(item_title) > 50:
            item_title = item_title[:47] + "..."

        line = f"📄 {broker_tag}{stock_tag} [{item_title}]({item.url})"
        report_lines.append(line)

    if report_lines:
        embed.description = "\n".join(report_lines)

    if len(items) > max_items:
        embed.set_footer(text=f"외 {len(items) - max_items}건 더 있음")

    return embed
