"""
RSS 뉴스 수집기
다양한 RSS 피드에서 뉴스 수집
"""
from datetime import datetime
from typing import Optional
import feedparser
from dateutil import parser as date_parser

from src.collectors.base import BaseCollector, ContentItem, ContentType, Priority
from src.utils.logger import logger


class RSSNewsCollector(BaseCollector):
    """RSS 피드 뉴스 수집기"""

    def __init__(self, name: str, url: str, priority: Priority = Priority.MEDIUM):
        super().__init__(name, ContentType.NEWS)
        self.url = url
        self.default_priority = priority

    def collect(self) -> list[ContentItem]:
        """RSS 피드에서 뉴스 수집"""
        items = []

        try:
            logger.info(f"Collecting news from RSS: {self.name}")
            feed = feedparser.parse(self.url)

            if feed.bozo and feed.bozo_exception:
                logger.warning(f"RSS parse warning for {self.name}: {feed.bozo_exception}")

            for entry in feed.entries[:20]:  # 최대 20개
                item = self._parse_entry(entry)
                if item:
                    items.append(item)

            logger.info(f"Collected {len(items)} items from {self.name}")

        except Exception as e:
            logger.error(f"Failed to collect from {self.name}: {e}")

        return items

    def _parse_entry(self, entry) -> Optional[ContentItem]:
        """RSS 엔트리 파싱"""
        try:
            # 필수 필드 확인
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                return None

            # 발행일 파싱
            published_at = self._parse_date(entry)

            # 설명/내용
            description = ""
            if "summary" in entry:
                description = entry.summary
            elif "description" in entry:
                description = entry.description

            # HTML 태그 제거
            description = self._strip_html(description)[:500]

            return ContentItem(
                id=self.generate_id(link),
                title=title,
                url=link,
                source=self.name,
                content_type=ContentType.NEWS,
                published_at=published_at,
                description=description,
                priority=self.default_priority,
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
        """HTML 태그 제거 (중앙 유틸리티 사용)"""
        from src.utils.constants import strip_html
        return strip_html(text)


def create_rss_collectors(sources: list[dict]) -> list[RSSNewsCollector]:
    """설정에서 RSS 수집기 목록 생성"""
    from src.utils.constants import get_priority_from_string

    collectors = []
    for source in sources:
        if source.get("type") == "rss" and source.get("enabled", True):
            priority = get_priority_from_string(source.get("priority", "medium"))
            collectors.append(
                RSSNewsCollector(
                    name=source["name"],
                    url=source["url"],
                    priority=priority,
                )
            )
    return collectors
