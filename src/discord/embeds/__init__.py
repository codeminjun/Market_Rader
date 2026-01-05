"""
Discord Embed 빌더 모듈
"""
from src.discord.embeds.news_embed import (
    create_news_header_embed,
    create_news_item_embed,
    create_news_list_embed,
    get_importance_emoji,
    get_priority_stars,
)
from src.discord.embeds.report_embed import (
    create_reports_header_embed,
    create_report_item_embed,
    create_reports_list_embed,
)
from src.discord.embeds.youtube_embed import (
    create_youtube_header_embed,
    create_youtube_item_embed,
    create_youtube_list_embed,
    create_youtube_quick_embed,
)

__all__ = [
    # News
    "create_news_header_embed",
    "create_news_item_embed",
    "create_news_list_embed",
    "get_importance_emoji",
    "get_priority_stars",
    # Reports
    "create_reports_header_embed",
    "create_report_item_embed",
    "create_reports_list_embed",
    # YouTube
    "create_youtube_header_embed",
    "create_youtube_item_embed",
    "create_youtube_list_embed",
    "create_youtube_quick_embed",
]
