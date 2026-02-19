"""
콘텐츠 수집 모듈
뉴스, 애널리스트 리포트, 유튜브 영상 수집
"""
from src.collectors.base import BaseCollector, ContentItem, ContentType, Priority
from src.collectors.news import (
    RSSNewsCollector,
    create_rss_collectors,
    NaverFinanceNewsCollector,
    NaverSearchNewsCollector,
)
from src.collectors.reports import NaverResearchCollector, SeekingAlphaCollector
from src.collectors.youtube import (
    YouTubeChannelMonitor,
    transcript_extractor,
    extract_video_id,
)
from src.collectors.market import (
    MarketDataCollector,
    market_data_collector,
    MarketSummary,
    IndexData,
    ExchangeRate,
    SectorETFData,
)

__all__ = [
    # Base
    "BaseCollector",
    "ContentItem",
    "ContentType",
    "Priority",
    # News
    "RSSNewsCollector",
    "create_rss_collectors",
    "NaverFinanceNewsCollector",
    "NaverSearchNewsCollector",
    # Reports
    "NaverResearchCollector",
    "SeekingAlphaCollector",
    # YouTube
    "YouTubeChannelMonitor",
    "transcript_extractor",
    "extract_video_id",
    # Market Data
    "MarketDataCollector",
    "market_data_collector",
    "MarketSummary",
    "IndexData",
    "ExchangeRate",
    "SectorETFData",
]
