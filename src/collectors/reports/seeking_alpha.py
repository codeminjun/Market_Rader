"""
Seeking Alpha RSS 수집기
해외 애널리스트 분석글 수집 + 시총 50위 종목 필터링
"""
from datetime import datetime
from typing import Optional
import re
import feedparser
from dateutil import parser as date_parser

from src.collectors.base import BaseCollector, ContentItem, ContentType, Priority
from src.utils.logger import logger
from config.settings import get_top_companies


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

    def __init__(self, feeds: Optional[list[str]] = None, filter_top50: bool = True):
        super().__init__("Seeking Alpha", ContentType.REPORT)
        self.feeds = feeds or ["market_currents"]
        self.filter_top50 = filter_top50
        self._load_top50_companies()

    def _load_top50_companies(self):
        """해외 시총 50위 기업 목록 로드"""
        try:
            config = get_top_companies()
            self.top50_tickers = set()
            self.top50_names = set()

            for company in config.get("international_top50", []):
                if "ticker" in company:
                    self.top50_tickers.add(company["ticker"].upper())
                if "name" in company:
                    self.top50_names.add(company["name"].lower())
        except Exception as e:
            logger.warning(f"Failed to load top50 companies: {e}")
            self.top50_tickers = set()
            self.top50_names = set()

    def _extract_ticker(self, title: str, description: str = "") -> Optional[str]:
        """제목/설명에서 티커 추출"""
        text = f"{title} {description}"

        # $AAPL 형태의 티커 추출
        ticker_match = re.search(r'\$([A-Z]{1,5})\b', text)
        if ticker_match:
            return ticker_match.group(1)

        # (AAPL) 형태의 티커 추출
        paren_match = re.search(r'\(([A-Z]{1,5})\)', text)
        if paren_match:
            return paren_match.group(1)

        # NASDAQ:AAPL 형태
        nasdaq_match = re.search(r'(?:NASDAQ|NYSE|AMEX):([A-Z]{1,5})\b', text)
        if nasdaq_match:
            return nasdaq_match.group(1)

        return None

    def _is_top50_stock(self, title: str, description: str = "") -> tuple[bool, Optional[str]]:
        """시총 50위 종목인지 확인"""
        if not self.filter_top50:
            return True, None

        # 티커 추출
        ticker = self._extract_ticker(title, description)
        if ticker and ticker in self.top50_tickers:
            return True, ticker

        # 회사명으로 검색
        text_lower = f"{title} {description}".lower()
        for name in self.top50_names:
            if name in text_lower:
                # 해당 회사의 티커 찾기
                config = get_top_companies()
                for company in config.get("international_top50", []):
                    if company.get("name", "").lower() == name:
                        return True, company.get("ticker")
                return True, None

        return False, ticker

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
        """RSS 엔트리 파싱 (시총 50위 필터링 포함)"""
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                return None

            # 설명
            description = ""
            if "summary" in entry:
                description = self._strip_html(entry.summary)[:500]
            elif "description" in entry:
                description = self._strip_html(entry.description)[:500]

            # 시총 50위 필터링
            is_top50, ticker = self._is_top50_stock(title, description)
            if self.filter_top50 and not is_top50:
                return None

            # 발행일 파싱
            published_at = self._parse_date(entry)

            # 작성자
            author = entry.get("author", "")

            # 티커가 있으면 제목에 추가
            display_title = title
            if ticker:
                display_title = f"[${ticker}] {title}"

            return ContentItem(
                id=self.generate_id(link),
                title=display_title,
                url=link,
                source=f"Seeking Alpha - {feed_name}",
                content_type=ContentType.REPORT,
                published_at=published_at,
                description=description,
                priority=Priority.HIGH if is_top50 and ticker else Priority.MEDIUM,
                extra_data={
                    "author": author,
                    "feed": feed_name,
                    "ticker": ticker,
                    "is_top50": is_top50,
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
