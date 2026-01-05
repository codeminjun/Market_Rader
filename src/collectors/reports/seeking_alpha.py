"""
Seeking Alpha RSS 수집기
해외 애널리스트 분석글 수집
"""
from datetime import datetime
from typing import Optional
import feedparser
from dateutil import parser as date_parser

from src.collectors.base import BaseCollector, ContentItem, ContentType, Priority
from src.utils.logger import logger


class SeekingAlphaCollector(BaseCollector):
    """Seeking Alpha RSS 수집기"""

    RSS_FEEDS = {
        "market_currents": {
            "url": "https://seekingalpha.com/market_currents.xml",
            "name": "Market Currents",
        },
        "market_news": {
            "url": "https://seekingalpha.com/market-news/all/all/feed",
            "name": "Market News",
        },
    }

    def __init__(self, feeds: Optional[list[str]] = None):
        super().__init__("Seeking Alpha", ContentType.REPORT)
        self.feeds = feeds or ["market_currents"]

    def collect(self) -> list[ContentItem]:
        """Seeking Alpha RSS 수집"""
        items = []

        for feed_key in self.feeds:
            if feed_key in self.RSS_FEEDS:
                feed_info = self.RSS_FEEDS[feed_key]
                feed_items = self._collect_feed(feed_info)
                items.extend(feed_items)

        logger.info(f"Collected {len(items)} items from {self.name}")
        return items

    def _collect_feed(self, feed_info: dict) -> list[ContentItem]:
        """개별 피드 수집"""
        items = []

        try:
            logger.debug(f"Fetching {feed_info['name']} from Seeking Alpha")
            feed = feedparser.parse(feed_info["url"])

            if feed.bozo and feed.bozo_exception:
                logger.warning(f"RSS parse warning: {feed.bozo_exception}")

            for entry in feed.entries[:15]:
                item = self._parse_entry(entry, feed_info["name"])
                if item:
                    items.append(item)

        except Exception as e:
            logger.error(f"Failed to collect from {feed_info['name']}: {e}")

        return items

    def _parse_entry(self, entry, feed_name: str) -> Optional[ContentItem]:
        """RSS 엔트리 파싱"""
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                return None

            # 발행일 파싱
            published_at = self._parse_date(entry)

            # 설명
            description = ""
            if "summary" in entry:
                description = self._strip_html(entry.summary)[:500]
            elif "description" in entry:
                description = self._strip_html(entry.description)[:500]

            # 작성자
            author = entry.get("author", "")

            return ContentItem(
                id=self.generate_id(link),
                title=title,
                url=link,
                source=f"Seeking Alpha - {feed_name}",
                content_type=ContentType.REPORT,
                published_at=published_at,
                description=description,
                priority=Priority.MEDIUM,
                extra_data={
                    "author": author,
                    "feed": feed_name,
                },
            )

        except Exception as e:
            logger.debug(f"Failed to parse entry: {e}")
            return None

    def _parse_date(self, entry) -> Optional[datetime]:
        """날짜 파싱"""
        for field in ["published", "updated", "created"]:
            if field in entry:
                try:
                    return date_parser.parse(entry[field])
                except (ValueError, TypeError):
                    continue
        return None

    def _strip_html(self, text: str) -> str:
        """HTML 태그 제거"""
        import re
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text).strip()
