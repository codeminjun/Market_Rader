"""
뉴스용 Discord Embed 빌더
"""
from datetime import datetime
from discord_webhook import DiscordEmbed

from src.collectors.base import ContentItem, Priority
from src.utils.constants import EmbedColors


# 시그널별 색상 (16진수 문자열)
SIGNAL_COLORS = {
    "strong_bullish": "00FF00",  # 밝은 초록
    "bullish": "32CD32",          # 라임그린
    "neutral": "808080",          # 회색
    "bearish": "FFA500",          # 주황
    "strong_bearish": "FF0000",   # 빨강
}

# 시그널별 이모지
SIGNAL_EMOJIS = {
    "strong_bullish": "🚀",
    "bullish": "📈",
    "neutral": "➡️",
    "bearish": "📉",
    "strong_bearish": "💥",
}

# 시그널별 한글
SIGNAL_NAMES = {
    "strong_bullish": "강한 상승",
    "bullish": "상승",
    "neutral": "중립",
    "bearish": "하락",
    "strong_bearish": "강한 하락",
}


def sanitize_title_for_link(title: str) -> str:
    """Discord 마크다운 링크용 제목 정리 - 대괄호를 제거/치환하여 링크 깨짐 방지"""
    # [속보], [마켓PRO] 등 대괄호가 마크다운 링크 [제목](URL)과 충돌
    title = title.replace("[", "").replace("]", "")
    # 괄호도 URL 부분과 충돌 가능
    title = title.replace("(", "（").replace(")", "）")
    return title


def get_importance_emoji(score: float, item: "ContentItem" = None) -> str:
    """중요도 점수에 따른 이모지 (커버드콜/배당 특별 강조)"""
    # 커버드콜/배당 뉴스 특별 강조
    if item and item.extra_data.get("is_covered_call"):
        return "💰🔥"  # 배당/커버드콜 강조

    if score >= 0.8:
        return "🔴"  # 긴급
    elif score >= 0.6:
        return "🟠"  # 중요
    elif score >= 0.4:
        return "🟡"  # 일반
    else:
        return "⚪"  # 참고


def get_covered_call_label(item: "ContentItem") -> str:
    """커버드콜/배당 뉴스 라벨"""
    if item.extra_data.get("is_covered_call"):
        return " **[배당/커버드콜]**"
    return ""


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
    title_override: str = None,
) -> DiscordEmbed:
    """
    뉴스 헤더 Embed 생성

    Args:
        date: 날짜
        news_count: 뉴스 개수
        summary: AI 요약 결과
        title_override: 커스텀 제목 (시간대별 분기용)
    """
    # 요일 한글 변환
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    weekday_kr = weekdays[date.weekday()]
    date_str = date.strftime(f"%Y년 %m월 %d일 ({weekday_kr})")

    # 제목 설정 (오버라이드 또는 기본)
    if title_override:
        title = f"{title_override} - {date_str}"
    else:
        title = f"📰 {date_str} 주식 뉴스 브리핑"

    embed = DiscordEmbed(
        title=title,
        description=f"오늘의 주요 뉴스 {news_count}건을 정리했어요.",
        color=EmbedColors.DEFAULT,
    )

    if summary:
        # AI 요약 추가
        if "summary" in summary:
            embed.add_embed_field(
                name="📋 이렇게 요약했어요",
                value=summary["summary"][:1000],
                inline=False,
            )

        if "key_points" in summary and summary["key_points"]:
            points_text = "\n".join([f"• {p}" for p in summary["key_points"][:5]])
            embed.add_embed_field(
                name="🎯 이런 점이 중요해요",
                value=points_text[:1000],
                inline=False,
            )

        if "investment_insight" in summary:
            embed.add_embed_field(
                name="💡 이런 인사이트가 있어요",
                value=summary["investment_insight"][:500],
                inline=False,
            )

    embed.set_footer(text="Market Rader Bot")
    embed.set_timestamp()

    return embed


def create_market_signal_embed(
    date: datetime,
    signal_data: dict,
    news_count: int = 0,
    title_override: str = None,
) -> DiscordEmbed:
    """
    시장 시그널 헤더 Embed 생성

    Args:
        date: 날짜
        signal_data: AI 분석 시그널 데이터
        news_count: 뉴스 개수
        title_override: 커스텀 제목
    """
    # 요일 한글 변환
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    weekday_kr = weekdays[date.weekday()]
    date_str = date.strftime(f"%Y년 %m월 %d일 ({weekday_kr})")

    # 시그널 정보
    overall_signal = signal_data.get("overall_signal", "neutral")
    signal_emoji = SIGNAL_EMOJIS.get(overall_signal, "➡️")
    signal_name = SIGNAL_NAMES.get(overall_signal, "중립")
    signal_color = SIGNAL_COLORS.get(overall_signal, "808080")
    signal_strength = signal_data.get("signal_strength", 0.5)

    # 강도 바 생성
    strength_bar = "█" * int(signal_strength * 10) + "░" * (10 - int(signal_strength * 10))

    # 제목 설정
    if title_override:
        title = f"{signal_emoji} {title_override} - {date_str}"
    else:
        title = f"{signal_emoji} {date_str} 시장 시그널: {signal_name}"

    embed = DiscordEmbed(
        title=title,
        color=signal_color,
    )

    # 시그널 강도 표시
    embed.add_embed_field(
        name="📊 시장 시그널",
        value=f"**{signal_emoji} {signal_name}** `{strength_bar}` {int(signal_strength * 100)}%",
        inline=False,
    )

    # 야간 선물 마감 데이터
    night_futures = signal_data.get("night_futures", [])
    if night_futures:
        futures_lines = []
        for nf in night_futures:
            sign = "+" if nf.change_percent >= 0 else ""
            arrow = "📈" if nf.is_up else "📉"
            futures_lines.append(
                f"**{nf.name}**: {nf.price:,.2f} ({sign}{nf.change_percent:.2f}%) {arrow}"
            )
        embed.add_embed_field(
            name="🌙 야간 선물 마감",
            value="\n".join(futures_lines),
            inline=False,
        )

    # SWOT 분석
    swot = signal_data.get("swot", {})
    if swot:
        swot_lines = []
        strengths = swot.get("strengths", [])
        weaknesses = swot.get("weaknesses", [])
        opportunities = swot.get("opportunities", [])
        threats = swot.get("threats", [])
        if strengths:
            swot_lines.append(f"💪 **강점**: {', '.join(strengths[:2])}")
        if weaknesses:
            swot_lines.append(f"😥 **약점**: {', '.join(weaknesses[:2])}")
        if opportunities:
            swot_lines.append(f"🌟 **기회**: {', '.join(opportunities[:2])}")
        if threats:
            swot_lines.append(f"⚠️ **위협**: {', '.join(threats[:2])}")
        if swot_lines:
            embed.add_embed_field(
                name="📊 SWOT 분석",
                value="\n".join(swot_lines),
                inline=False,
            )

    # 섹터별 시그널 → BCG 매트릭스
    sector_signals = signal_data.get("sector_signals", {})
    sector_etf_data = signal_data.get("sector_etf_data", {})
    if sector_signals:
        bcg = _classify_bcg(sector_signals, sector_etf_data)
        bcg_lines = []
        if bcg["star"]:
            bcg_lines.append(f"⭐ **Star**: {', '.join(bcg['star'])}")
        if bcg["cash_cow"]:
            bcg_lines.append(f"💰 **Cash Cow**: {', '.join(bcg['cash_cow'])}")
        if bcg["question_mark"]:
            bcg_lines.append(f"❓ **Question Mark**: {', '.join(bcg['question_mark'])}")
        if bcg["dog"]:
            bcg_lines.append(f"🐕 **Dog**: {', '.join(bcg['dog'])}")

        if bcg_lines:
            embed.add_embed_field(
                name="🏭 섹터 BCG 분류",
                value="\n".join(bcg_lines),
                inline=False,
            )

    # 핵심 이벤트
    key_events = signal_data.get("key_events", [])
    if key_events:
        events_text = "\n".join([f"• {e}" for e in key_events[:4]])
        embed.add_embed_field(
            name="🎯 오늘 이런 일이 있어요",
            value=events_text[:500],
            inline=False,
        )

    # 리스크 요인
    risk_factors = signal_data.get("risk_factors", [])
    if risk_factors:
        risk_text = "\n".join([f"⚠️ {r}" for r in risk_factors[:3]])
        embed.add_embed_field(
            name="🛡️ 이런 점은 주의하세요",
            value=risk_text[:300],
            inline=True,
        )

    # 투자 기회
    if "opportunity" in signal_data:
        embed.add_embed_field(
            name="💡 이런 기회가 보여요",
            value=signal_data["opportunity"][:300],
            inline=True,
        )

    embed.set_footer(text=f"Market Rader Bot | 분석 뉴스 {news_count}건")
    embed.set_timestamp()

    return embed


def create_breaking_news_embed(
    items: list[ContentItem],
) -> DiscordEmbed:
    """
    긴급 뉴스 Embed 생성

    Args:
        items: 긴급 뉴스 항목 리스트
    """
    if not items:
        return None

    embed = DiscordEmbed(
        title="🚨 긴급 뉴스 속보",
        color="FF0000",
    )

    news_lines = []
    for item in items[:5]:
        keyword = item.extra_data.get("breaking_keyword", "속보")
        safe_title = sanitize_title_for_link(item.title[:40])
        line = f"🔴 **[{keyword.upper()}]** [{safe_title}...]({item.url})"
        news_lines.append(line)

    embed.description = "\n\n".join(news_lines)
    embed.set_footer(text="⚡ 시장 급변 가능성 - 주의 필요")

    return embed


def create_sector_news_embed(
    sector: str,
    items: list[ContentItem],
    sector_signal: str = None,
) -> DiscordEmbed:
    """
    섹터별 뉴스 Embed 생성

    Args:
        sector: 섹터명
        items: 해당 섹터 뉴스 리스트
        sector_signal: 섹터 시그널 (bullish/bearish/neutral)
    """
    signal_emoji = SIGNAL_EMOJIS.get(sector_signal, "📰") if sector_signal else "📰"
    signal_color = SIGNAL_COLORS.get(sector_signal, EmbedColors.DEFAULT) if sector_signal else EmbedColors.DEFAULT

    embed = DiscordEmbed(
        title=f"{signal_emoji} {sector} 섹터 뉴스 ({len(items)}건)",
        color=signal_color,
    )

    news_lines = []
    for i, item in enumerate(items[:5], 1):
        importance_emoji = get_importance_emoji(item.importance_score, item)
        title = sanitize_title_for_link(item.title)
        title = title[:40] + "..." if len(title) > 40 else title
        news_lines.append(f"{importance_emoji} **{i}.** [{title}]({item.url})")

    embed.description = "\n".join(news_lines)

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
        Priority.HIGH: EmbedColors.NEWS_KOREAN,
        Priority.MEDIUM: "f39c12",
        Priority.LOW: "95a5a6",
    }
    color = color_map.get(item.priority, EmbedColors.DEFAULT)

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


def _classify_bcg(
    sector_signals: dict[str, str],
    sector_etf_data: dict = None,
) -> dict[str, list[str]]:
    """
    섹터별 시그널과 ETF 데이터를 BCG 매트릭스로 분류

    Rules:
    - Star: signal=bullish/strong_bullish AND etf_change > 0
    - Cash Cow: signal=neutral AND 대형섹터
    - Question Mark: signal=bullish BUT 소형섹터 OR etf 혼조
    - Dog: signal=bearish/strong_bearish AND etf_change < 0
    """
    LARGE_SECTORS = {"반도체", "금융", "자동차", "에너지", "2차전지"}
    sector_etf_data = sector_etf_data or {}

    bcg = {"star": [], "cash_cow": [], "question_mark": [], "dog": []}

    for sector, signal in sector_signals.items():
        etf = sector_etf_data.get(sector)
        etf_change = etf.change_percent if etf else 0.0
        etf_sign = f"({'+' if etf_change >= 0 else ''}{etf_change:.1f}%)" if etf else ""
        label = f"{sector}{etf_sign}"

        if signal in ("bearish", "strong_bearish") and etf_change < 0:
            bcg["dog"].append(label)
        elif signal in ("bullish", "strong_bullish"):
            if etf_change > 0:
                bcg["star"].append(label)
            else:
                bcg["question_mark"].append(label)
        elif signal == "neutral" and sector in LARGE_SECTORS:
            bcg["cash_cow"].append(label)
        elif signal == "neutral":
            bcg["question_mark"].append(label)
        else:
            bcg["question_mark"].append(label)

    return bcg


def create_sentiment_news_embeds(
    positive_news: list[ContentItem],
    negative_news: list[ContentItem],
) -> list[DiscordEmbed]:
    """
    긍정 뉴스 + 부정 뉴스 각각 1개 Embed 반환

    Args:
        positive_news: 긍정 뉴스 리스트 (최대 5건)
        negative_news: 부정 뉴스 리스트 (최대 5건)

    Returns:
        DiscordEmbed 리스트 (1~2개)
    """
    embeds = []

    if positive_news:
        pos_embed = DiscordEmbed(
            title=f"📈 긍정 뉴스 ({len(positive_news)}건)",
            color="32CD32",  # 라임그린
        )
        pos_lines = []
        for i, item in enumerate(positive_news, 1):
            item_title = sanitize_title_for_link(item.title)
            if len(item_title) > 45:
                item_title = item_title[:42] + "..."
            source_short = item.source.split("(")[0].strip()[:12]
            pos_lines.append(
                f"📈 **{i}.** [{item_title}]({item.url})\n└ `{source_short}`"
            )
        pos_embed.description = "\n".join(pos_lines)
        pos_embed.set_footer(text="Market Rader Bot")
        embeds.append(pos_embed)

    if negative_news:
        neg_embed = DiscordEmbed(
            title=f"📉 부정 뉴스 ({len(negative_news)}건)",
            color="FFA500",  # 주황
        )
        neg_lines = []
        for i, item in enumerate(negative_news, 1):
            item_title = sanitize_title_for_link(item.title)
            if len(item_title) > 45:
                item_title = item_title[:42] + "..."
            source_short = item.source.split("(")[0].strip()[:12]
            neg_lines.append(
                f"📉 **{i}.** [{item_title}]({item.url})\n└ `{source_short}`"
            )
        neg_embed.description = "\n".join(neg_lines)
        neg_embed.set_footer(text="Market Rader Bot")
        embeds.append(neg_embed)

    return embeds


def create_news_list_embed(
    items: list[ContentItem],
    title: str = "📰 주요 뉴스",
    max_items: int = 10,
    color: str = "3498db",
) -> DiscordEmbed:
    """단일 뉴스 목록 Embed 생성 (하위 호환용)"""
    embeds = create_news_list_embeds(items, title, max_items, color)
    return embeds[0] if embeds else DiscordEmbed(title=title, color=color)


def create_news_list_embeds(
    items: list[ContentItem],
    title: str = "📰 주요 뉴스",
    items_per_embed: int = 15,
    color: str = "3498db",
) -> list[DiscordEmbed]:
    """
    뉴스 목록 Embed 여러 개 생성 (글자 수 제한 대응)

    Args:
        items: 뉴스 항목 리스트
        title: Embed 제목
        items_per_embed: Embed당 최대 항목 수
        color: Embed 색상

    Returns:
        DiscordEmbed 리스트
    """
    if not items:
        return []

    embeds = []
    total_items = len(items)

    for batch_idx, start in enumerate(range(0, total_items, items_per_embed)):
        batch = items[start:start + items_per_embed]

        # 첫 번째 Embed에만 제목 표시, 나머지는 "계속"
        if batch_idx == 0:
            embed_title = title
        else:
            embed_title = f"{title} (계속)"

        embed = DiscordEmbed(
            title=embed_title,
            color=color,
        )

        news_lines = []
        for i, item in enumerate(batch, start + 1):
            emoji = get_importance_emoji(item.importance_score, item)
            covered_call_label = get_covered_call_label(item)

            # 제목 길이 제한 + 마크다운 링크 깨짐 방지
            item_title = sanitize_title_for_link(item.title)
            if len(item_title) > 45:
                item_title = item_title[:42] + "..."

            # 출처 간략화
            source_short = item.source.split("(")[0].strip()[:12]

            line = f"{emoji} **{i}.** [{item_title}]({item.url}){covered_call_label}\n└ `{source_short}`"
            news_lines.append(line)

        if news_lines:
            embed.description = "\n".join(news_lines)

        embeds.append(embed)

    return embeds
