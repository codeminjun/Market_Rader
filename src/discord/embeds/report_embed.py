"""
애널리스트 리포트용 Discord Embed 빌더
"""
from discord_webhook import DiscordEmbed

from src.collectors.base import ContentItem
from src.utils.constants import EmbedColors


def create_reports_header_embed(
    report_count: int,
    summary: dict = None,
) -> DiscordEmbed:
    """
    리포트 섹션 헤더 Embed 생성 (토스 스타일)

    Args:
        report_count: 리포트 개수
        summary: AI 요약 결과
    """
    embed = DiscordEmbed(
        title=f"📊 오늘의 애널리스트 리포트 {report_count}건이에요",
        color=EmbedColors.REPORTS,
    )

    if summary:
        if "summary" in summary:
            embed.add_embed_field(
                name="📋 이렇게 요약했어요",
                value=summary["summary"][:1000],
                inline=False,
            )

        if "recommendations" in summary and summary["recommendations"]:
            rec_text = "\n".join([f"• {r}" for r in summary["recommendations"][:5]])
            embed.add_embed_field(
                name="💡 애널리스트들이 추천해요",
                value=rec_text[:1000],
                inline=False,
            )

        if "sectors_focus" in summary and summary["sectors_focus"]:
            sectors_text = ", ".join(summary["sectors_focus"][:5])
            embed.add_embed_field(
                name="🎯 이 섹터를 주목하세요",
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
        color=EmbedColors.REPORTS,
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


def get_importance_indicator(score: float) -> str:
    """중요도 표시"""
    if score >= 0.7:
        return "🔴"
    elif score >= 0.5:
        return "🟠"
    else:
        return "🟡"


def format_target_price(item: ContentItem) -> str:
    """목표가 정보 포맷팅"""
    target_price = item.extra_data.get("target_price")
    opinion = item.extra_data.get("opinion", "")
    ticker = item.extra_data.get("ticker")

    if target_price:
        # 국내: 원화
        if ticker is None:
            return f"🎯{target_price:,}원" + (f" ({opinion})" if opinion else "")
        # 해외: 달러
        else:
            return f"🎯${target_price:,.0f}" if isinstance(target_price, (int, float)) else ""

    return ""


def create_reports_list_embed(
    items: list[ContentItem],
    title: str = "📊 애널리스트 리포트",
    max_items: int = 10,
) -> DiscordEmbed:
    """
    리포트 목록 Embed 생성 (간결한 형식)

    Args:
        items: 리포트 항목 리스트
        title: Embed 제목
        max_items: 최대 표시 개수
    """
    embed = DiscordEmbed(
        title=title,
        color=EmbedColors.REPORTS,
    )

    report_lines = []
    for item in items[:max_items]:
        # 중요도 표시
        importance = get_importance_indicator(item.importance_score)

        # 증권사 추출
        broker = item.extra_data.get("broker", "")
        if broker and len(broker) > 8:
            broker = broker[:7] + ".."

        # 제목 구성: 간결하게
        item_title = item.title
        if len(item_title) > 45:
            item_title = item_title[:42] + "..."

        # 한 줄로 간결하게: 🔴 [제목](링크) - 증권사
        line = f"{importance} [{item_title}]({item.url})"
        if broker:
            line += f"\n└ {broker}"

        report_lines.append(line)

    if report_lines:
        embed.description = "\n".join(report_lines)

    return embed


def create_detailed_report_embed(item: ContentItem) -> DiscordEmbed:
    """
    AI 분석된 상세 리포트 Embed 생성 (간결한 문장 형식)

    Args:
        item: AI 분석이 완료된 리포트 항목
    """
    analysis = item.extra_data.get("ai_analysis", {})
    stock_name = item.extra_data.get("stock_name", "")
    target_price = item.extra_data.get("target_price")
    opinion = item.extra_data.get("opinion", "")
    broker = item.extra_data.get("broker", "")

    # 의견에 따른 색상
    opinion_colors = {
        "매수": "00FF00",
        "적극매수": "00FF00",
        "보유": "FFA500",
        "중립": "808080",
        "매도": "FF0000",
    }
    color = opinion_colors.get(opinion, EmbedColors.REPORTS)

    # 제목 구성: 종목명 | 증권사 | 목표가
    title_parts = []
    if stock_name:
        title_parts.append(f"📄 {stock_name}")
    else:
        title_parts.append(f"📄 {item.title[:25]}")

    if broker:
        title_parts.append(broker)

    if target_price:
        price_str = f"목표가 {target_price:,}원"
        if opinion:
            price_str += f" ({opinion})"
        title_parts.append(price_str)

    title = " | ".join(title_parts)

    embed = DiscordEmbed(
        title=title,
        url=item.url,
        color=color,
    )

    # AI 분석 결과를 문장 형식으로 구성
    if analysis:
        description_parts = []

        # 한 줄 요약
        if analysis.get("one_line_summary"):
            description_parts.append(f"**{analysis['one_line_summary']}**")

        # 투자 포인트
        if analysis.get("investment_point"):
            description_parts.append(f"\n💡 {analysis['investment_point']}")

        # 리스크
        if analysis.get("risk_factor"):
            description_parts.append(f"\n⚠️ {analysis['risk_factor']}")

        # 키워드 (있으면 맨 아래 작게)
        keywords = analysis.get("keywords", [])
        if keywords:
            keyword_str = ", ".join(keywords[:4])
            description_parts.append(f"\n`{keyword_str}`")

        if description_parts:
            embed.description = "".join(description_parts)

    return embed


def create_reports_with_analysis_embeds(
    items: list[ContentItem],
    max_detailed: int = 3,
    max_list: int = 7,
) -> list[DiscordEmbed]:
    """
    AI 분석 포함 리포트 Embed 리스트 생성

    Args:
        items: 리포트 항목 리스트
        max_detailed: 상세 Embed 최대 개수
        max_list: 목록 Embed 최대 개수

    Returns:
        [헤더, 상세1, 상세2, ..., 목록] 형태의 Embed 리스트
    """
    embeds = []

    if not items:
        return embeds

    # AI 분석이 있는 항목 분리
    analyzed_items = [
        item for item in items
        if item.extra_data.get("ai_analysis")
    ]
    other_items = [
        item for item in items
        if not item.extra_data.get("ai_analysis")
    ]

    # 1. 상세 Embed (AI 분석된 항목)
    for item in analyzed_items[:max_detailed]:
        embed = create_detailed_report_embed(item)
        embeds.append(embed)

    # 2. 나머지 목록 Embed
    remaining = analyzed_items[max_detailed:] + other_items
    if remaining:
        list_embed = create_reports_list_embed(
            remaining[:max_list],
            title="📊 더 많은 리포트도 있어요",
        )
        embeds.append(list_embed)

    return embeds
