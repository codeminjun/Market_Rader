"""
Discord 전송 모듈
Webhook 전송 및 Embed 빌더
"""
from src.discord.webhook import DiscordSender, discord_sender
from src.discord.embeds import (
    create_news_header_embed,
    create_news_item_embed,
    create_news_list_embed,
    create_news_list_embeds,
    create_reports_header_embed,
    create_report_item_embed,
    create_reports_list_embed,
    create_youtube_header_embed,
    create_youtube_item_embed,
    create_youtube_list_embed,
    create_youtube_quick_embed,
)

__all__ = [
    # Sender
    "DiscordSender",
    "discord_sender",
    # News Embeds
    "create_news_header_embed",
    "create_news_item_embed",
    "create_news_list_embed",
    "create_news_list_embeds",
    # Report Embeds
    "create_reports_header_embed",
    "create_report_item_embed",
    "create_reports_list_embed",
    # YouTube Embeds
    "create_youtube_header_embed",
    "create_youtube_item_embed",
    "create_youtube_list_embed",
    "create_youtube_quick_embed",
]
