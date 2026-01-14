"""
Morning Brief용 Discord Embed 빌더
"""
from discord_webhook import DiscordEmbed

from src.collectors.base import ContentItem


# Morning Brief 전용 색상 (골드)
MORNING_BRIEF_COLOR = "f1c40f"


def create_morning_brief_embed(
    items: list[ContentItem],
    combined_summary: dict = None,
    show_individual_analysis: bool = True,
) -> list[DiscordEmbed]:
    """
    Morning Brief Embed 생성

    Args:
        items: Morning Brief 항목 리스트
        combined_summary: 종합 요약 결과
        show_individual_analysis: 개별 Brief 상세 분석 표시 여부

    Returns:
        Embed 리스트
    """
    embeds = []

    if not items:
        return embeds

    # 1. 헤더 Embed (종합 요약)
    header_embed = DiscordEmbed(
        title="☀️ 오늘의 Morning Brief",
        color=MORNING_BRIEF_COLOR,
    )

    if combined_summary:
        # 종합 요약
        if "overall_summary" in combined_summary:
            header_embed.add_embed_field(
                name="📋 오늘 시황을 요약했어요",
                value=combined_summary["overall_summary"][:1000],
                inline=False,
            )

        # 공통 테마
        if "common_themes" in combined_summary and combined_summary["common_themes"]:
            themes_text = "\n".join([f"• {t}" for t in combined_summary["common_themes"][:4]])
            header_embed.add_embed_field(
                name="🎯 증권사들이 공통으로 주목해요",
                value=themes_text[:500],
                inline=False,
            )

        # 시장 컨센서스
        if "market_consensus" in combined_summary:
            header_embed.add_embed_field(
                name="📈 시장은 이렇게 보고 있어요",
                value=combined_summary["market_consensus"][:500],
                inline=False,
            )

        # 핵심 투자 포인트
        if "key_recommendations" in combined_summary and combined_summary["key_recommendations"]:
            rec_text = "\n".join([f"💡 {r}" for r in combined_summary["key_recommendations"][:4]])
            header_embed.add_embed_field(
                name="🔑 이런 점을 눈여겨보세요",
                value=rec_text[:500],
                inline=False,
            )

    embeds.append(header_embed)

    # 2. 개별 Morning Brief 상세 분석 (AI 분석 결과가 있는 경우)
    if show_individual_analysis:
        for item in items[:3]:  # 최대 3개
            analysis = item.extra_data.get("ai_analysis")
            if analysis:
                brief_embed = _create_detailed_brief_embed(item, analysis)
                embeds.append(brief_embed)

    # 3. 나머지 Morning Brief 목록 (분석 없는 것들)
    remaining_items = [
        item for item in items
        if not item.extra_data.get("ai_analysis") or not show_individual_analysis
    ]

    if remaining_items:
        brief_lines = []
        for item in remaining_items[:5]:
            broker = item.source
            title = item.title
            if len(title) > 50:
                title = title[:47] + "..."

            line = f"📄 **[{broker}]** [{title}]({item.url})"
            brief_lines.append(line)

        if brief_lines:
            list_embed = DiscordEmbed(
                title="📑 더 많은 Morning Brief도 있어요",
                description="\n".join(brief_lines),
                color=MORNING_BRIEF_COLOR,
            )
            embeds.append(list_embed)

    return embeds


def _create_detailed_brief_embed(item: ContentItem, analysis: dict) -> DiscordEmbed:
    """개별 Morning Brief 상세 분석 Embed 생성 (토스 스타일)"""
    broker = item.source

    embed = DiscordEmbed(
        title=f"📊 {broker}",
        url=item.url,
        color=MORNING_BRIEF_COLOR,
    )

    # 문장 형식으로 통합된 description 구성
    description_parts = []

    # 요약
    if analysis.get("summary"):
        description_parts.append(f"**{analysis['summary'][:400]}**")

    # 핵심 포인트
    if analysis.get("key_points") and len(analysis["key_points"]) > 0:
        points_text = "\n".join([f"• {p}" for p in analysis["key_points"][:3]])
        description_parts.append(f"\n\n{points_text}")

    # 시장 전망 + 주목 종목을 한 문장으로
    outlook_parts = []
    if analysis.get("market_outlook"):
        outlook_parts.append(f"📈 {analysis['market_outlook'][:200]}")

    if analysis.get("attention_stocks") and len(analysis["attention_stocks"]) > 0:
        stocks_text = ", ".join(analysis["attention_stocks"][:4])
        outlook_parts.append(f"🎯 주목할 종목: {stocks_text}")

    if outlook_parts:
        description_parts.append("\n\n" + "\n".join(outlook_parts))

    # 투자 인사이트
    if analysis.get("insights"):
        description_parts.append(f"\n\n💡 {analysis['insights'][:200]}")

    # PDF 링크
    pdf_url = item.extra_data.get("pdf_url")
    if pdf_url:
        description_parts.append(f"\n\n[📎 원문 PDF 보기]({pdf_url})")

    if description_parts:
        embed.description = "".join(description_parts)

    return embed


def create_single_morning_brief_embed(
    item: ContentItem,
    summary: dict = None,
) -> DiscordEmbed:
    """
    단일 Morning Brief Embed 생성

    Args:
        item: Morning Brief 항목
        summary: AI 요약 결과

    Returns:
        DiscordEmbed
    """
    broker = item.source
    title = item.title
    if len(title) > 200:
        title = title[:197] + "..."

    embed = DiscordEmbed(
        title=f"☀️ {title}",
        url=item.url,
        color=MORNING_BRIEF_COLOR,
    )

    embed.add_embed_field(
        name="증권사",
        value=broker,
        inline=True,
    )

    if item.published_at:
        date_str = item.published_at.strftime("%Y-%m-%d")
        embed.add_embed_field(
            name="발행일",
            value=date_str,
            inline=True,
        )

    if summary:
        # 요약
        if "summary" in summary:
            embed.add_embed_field(
                name="📋 요약",
                value=summary["summary"][:1000],
                inline=False,
            )

        # 핵심 포인트
        if "key_points" in summary and summary["key_points"]:
            points_text = "\n".join([f"• {p}" for p in summary["key_points"][:5]])
            embed.add_embed_field(
                name="🔑 핵심 포인트",
                value=points_text[:1000],
                inline=False,
            )

        # 시장 전망
        if "market_outlook" in summary:
            embed.add_embed_field(
                name="📈 시장 전망",
                value=summary["market_outlook"][:500],
                inline=False,
            )

        # 주목 종목
        if "attention_stocks" in summary and summary["attention_stocks"]:
            stocks_text = ", ".join(summary["attention_stocks"][:5])
            embed.add_embed_field(
                name="🎯 주목 종목/섹터",
                value=stocks_text[:500],
                inline=False,
            )

        # 인사이트
        if "insights" in summary:
            embed.add_embed_field(
                name="💡 투자 인사이트",
                value=summary["insights"][:500],
                inline=False,
            )

    # PDF 링크
    pdf_url = item.extra_data.get("pdf_url")
    if pdf_url:
        embed.add_embed_field(
            name="📎 원문 PDF",
            value=f"[PDF 다운로드]({pdf_url})",
            inline=False,
        )

    return embed
