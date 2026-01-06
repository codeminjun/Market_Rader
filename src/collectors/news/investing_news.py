"""
인베스팅닷컴 인기 뉴스 수집기
조회수 기준 인기 뉴스 수집
"""
from datetime import datetime
from typing import Optional
import requests
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector, ContentItem, ContentType, Priority
from src.utils.logger import logger


class InvestingNewsCollector(BaseCollector):
    """인베스팅닷컴 인기 뉴스 수집기"""

    # 인베스팅닷컴 인기 뉴스 페이지
    BASE_URL = "https://kr.investing.com"
    POPULAR_NEWS_URL = "https://kr.investing.com/news/most-popular-news"

    def __init__(self, max_items: int = 15):
        super().__init__("인베스팅닷컴", ContentType.NEWS)
        self.max_items = max_items
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def collect(self) -> list[ContentItem]:
        """인기 뉴스 수집"""
        items = []

        try:
            logger.info(f"Collecting popular news from {self.name}")
            response = requests.get(
                self.POPULAR_NEWS_URL,
                headers=self.headers,
                timeout=15,
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # 인기 뉴스 목록 파싱
            news_list = soup.select("article.js-article-item")

            if not news_list:
                # 대체 선택자 시도
                news_list = soup.select("div.largeTitle article")

            if not news_list:
                # 다른 대체 선택자
                news_list = soup.select("a[data-test='article-title-link']")

            for idx, news in enumerate(news_list[:self.max_items]):
                item = self._parse_news_item(news, idx + 1)
                if item:
                    items.append(item)

            logger.info(f"Collected {len(items)} popular items from {self.name}")

        except requests.RequestException as e:
            logger.error(f"Failed to fetch popular news: {e}")
        except Exception as e:
            logger.error(f"Error parsing popular news: {e}")

        return items

    def _parse_news_item(self, element, rank: int) -> Optional[ContentItem]:
        """뉴스 항목 파싱"""
        try:
            # 제목과 링크 추출
            title_elem = element.select_one("a.title") or element.select_one("a[data-test='article-title-link']")

            if not title_elem:
                # 직접 a 태그인 경우
                if element.name == "a":
                    title_elem = element
                else:
                    title_elem = element.select_one("a")

            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            href = title_elem.get("href", "")

            if not title or not href:
                return None

            # 전체 URL 생성
            if href.startswith("/"):
                url = f"{self.BASE_URL}{href}"
            elif not href.startswith("http"):
                url = f"{self.BASE_URL}/{href}"
            else:
                url = href

            # 날짜 추출
            date_elem = element.select_one("time") or element.select_one("span.date")
            published_at = None
            if date_elem:
                try:
                    date_str = date_elem.get("datetime") or date_elem.get_text(strip=True)
                    if date_str:
                        from dateutil import parser as date_parser
                        published_at = date_parser.parse(date_str)
                except (ValueError, TypeError):
                    pass

            # 설명 추출
            desc_elem = element.select_one("p") or element.select_one("span.articleDetails")
            description = desc_elem.get_text(strip=True)[:300] if desc_elem else ""

            # 조회수/인기도 순위 저장
            extra_data = {
                "popularity_rank": rank,
                "region": "korean",
            }

            # 인기 뉴스는 높은 우선순위
            priority = Priority.HIGH if rank <= 5 else Priority.MEDIUM

            return ContentItem(
                id=self.generate_id(url),
                title=title,
                url=url,
                source=f"{self.name} (인기 #{rank})",
                content_type=ContentType.NEWS,
                published_at=published_at,
                description=description,
                priority=priority,
                extra_data=extra_data,
            )

        except Exception as e:
            logger.debug(f"Failed to parse news item: {e}")
            return None
