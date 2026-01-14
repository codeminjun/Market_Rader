"""
Discord Embed 빌더 모듈
"""
from src.discord.embeds.news_embed import (
    create_news_header_embed,
    create_news_item_embed,
    create_news_list_embed,
    create_news_list_embeds,
    create_market_signal_embed,
    create_breaking_news_embed,
    create_sector_news_embed,
    get_importance_emoji,
    get_priority_stars,
)
from src.discord.embeds.report_embed import (
    create_reports_header_embed,
    create_report_item_embed,
    create_reports_list_embed,
    create_detailed_report_embed,
    create_reports_with_analysis_embeds,
)
from src.discord.embeds.youtube_embed import (
    create_youtube_header_embed,
    create_youtube_item_embed,
    create_youtube_list_embed,
    create_youtube_quick_embed,
)
from src.discord.embeds.morning_brief_embed import (
    create_morning_brief_embed,
    create_single_morning_brief_embed,
)
from src.discord.embeds.market_close_embed import (
    create_market_close_embed,
    create_market_summary_text,
)
from src.discord.embeds.briefing_embed import (
    create_assistant_briefing_embed,
    create_closing_review_embed,
    create_morning_strategy_embed,
)

__all__ = [
    # News
    "create_news_header_embed",
    "create_news_item_embed",
    "create_news_list_embed",
    "create_news_list_embeds",
    "create_market_signal_embed",
    "create_breaking_news_embed",
    "create_sector_news_embed",
    "get_importance_emoji",
    "get_priority_stars",
    # Reports
    "create_reports_header_embed",
    "create_report_item_embed",
    "create_reports_list_embed",
    "create_detailed_report_embed",
    "create_reports_with_analysis_embeds",
    # YouTube
    "create_youtube_header_embed",
    "create_youtube_item_embed",
    "create_youtube_list_embed",
    "create_youtube_quick_embed",
    # Morning Brief
    "create_morning_brief_embed",
    "create_single_morning_brief_embed",
    # Market Close
    "create_market_close_embed",
    "create_market_summary_text",
    # AI Briefing
    "create_assistant_briefing_embed",
    "create_closing_review_embed",
    "create_morning_strategy_embed",
]
