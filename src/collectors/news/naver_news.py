"""
네이버 금융 뉴스 수집기
네이버 금융에서 주요 뉴스 수집
"""
from datetime import datetime
from typing import Optional
import requests
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector, ContentItem, ContentType, Priority
from src.utils.logger import logger


class NaverFinanceNewsCollector(BaseCollector):
    """네이버 금융 뉴스 수집기"""

    BASE_URL = "https://finance.naver.com/news/"
    NEWS_LIST_URL = "https://finance.naver.com/news/news_list.naver"

    CATEGORIES = {
        "stock": {"category": "stock_news", "name": "증시"},
        "economy": {"category": "economy_news", "name": "경제"},
        "world": {"category": "world_news", "name": "국제"},
    }

    def __init__(self, categories: Optional[list[str]] = None):
        super().__init__("네이버 금융", ContentType.NEWS)
        self.categories = categories or ["stock", "economy"]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    def collect(self) -> list[ContentItem]:
        """네이버 금융 뉴스 수집"""
        items = []

        for category in self.categories:
            if category in self.CATEGORIES:
                category_items = self._collect_category(category)
                items.extend(category_items)

        logger.info(f"Collected {len(items)} items from {self.name}")
        return items

    def _collect_category(self, category: str) -> list[ContentItem]:
        """카테고리별 뉴스 수집"""
        items = []
        cat_info = self.CATEGORIES[category]

        try:
            # 메인 뉴스 페이지에서 수집
            url = f"{self.BASE_URL}mainnews.naver"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # 뉴스 목록 파싱 - dl 구조에서 각 기사 찾기
            # articleSubject(제목), articleSummary(요약/언론사/날짜) 구조
            article_subjects = soup.select("dd.articleSubject")

            for idx, subject_dd in enumerate(article_subjects[:15]):
                # 다음 sibling에서 summary 정보 가져오기
                summary_dd = subject_dd.find_next_sibling("dd", class_="articleSummary")
                item = self._parse_news_item(subject_dd, summary_dd, cat_info["name"])
                if item:
                    items.append(item)

        except requests.RequestException as e:
            logger.error(f"Failed to fetch {category} news: {e}")
        except Exception as e:
            logger.error(f"Error parsing {category} news: {e}")

        return items

    def _parse_news_item(self, subject_dd, summary_dd, category_name: str) -> Optional[ContentItem]:
        """뉴스 항목 파싱 (새로운 구조)"""
        try:
            # 제목과 링크
            title_elem = subject_dd.select_one("a")
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            href = title_elem.get("href", "")

            # 제목이나 링크가 없으면 스킵
            if not href or not title:
                return None

            # 전체 URL 생성
            if href.startswith("/"):
                url = f"https://finance.naver.com{href}"
            elif not href.startswith("http"):
                url = f"https://finance.naver.com/news/{href}"
            else:
                url = href

            # summary_dd에서 언론사와 날짜 추출
            source = "네이버 금융"
            published_at = None

            if summary_dd:
                # 언론사
                source_elem = summary_dd.select_one(".press")
                if source_elem:
                    source = source_elem.get_text(strip=True)

                # 날짜
                date_elem = summary_dd.select_one(".wdate")
                if date_elem:
                    try:
                        date_str = date_elem.get_text(strip=True)
                        published_at = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        try:
                            published_at = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                        except ValueError:
                            pass

            return ContentItem(
                id=self.generate_id(url),
                title=title,
                url=url,
                source=f"{source} ({category_name})",
                content_type=ContentType.NEWS,
                published_at=published_at,
                priority=Priority.MEDIUM,
            )

        except Exception as e:
            logger.debug(f"Failed to parse news item: {e}")
            return None


class NaverSearchNewsCollector(BaseCollector):
    """네이버 검색 API를 이용한 뉴스 수집 (API 키 필요)"""

    API_URL = "https://openapi.naver.com/v1/search/news.json"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        query: str = "주식 증시",
        display: int = 20,
    ):
        super().__init__("네이버 검색", ContentType.NEWS)
        self.client_id = client_id
        self.client_secret = client_secret
        self.query = query
        self.display = display

    def collect(self) -> list[ContentItem]:
        """네이버 검색 API로 뉴스 수집"""
        if not self.client_id or not self.client_secret:
            logger.warning("Naver API credentials not configured")
            return []

        items = []

        try:
            headers = {
                "X-Naver-Client-Id": self.client_id,
                "X-Naver-Client-Secret": self.client_secret,
            }
            params = {
                "query": self.query,
                "display": self.display,
                "sort": "date",
            }

            response = requests.get(self.API_URL, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            for item in data.get("items", []):
                content_item = self._parse_api_item(item)
                if content_item:
                    items.append(content_item)

            logger.info(f"Collected {len(items)} items from Naver Search API")

        except requests.RequestException as e:
            logger.error(f"Naver API request failed: {e}")
        except Exception as e:
            logger.error(f"Error processing Naver API response: {e}")

        return items

    def _parse_api_item(self, item: dict) -> Optional[ContentItem]:
        """API 응답 항목 파싱"""
        try:
            title = self._clean_html(item.get("title", ""))
            link = item.get("link", "")
            description = self._clean_html(item.get("description", ""))

            if not title or not link:
                return None

            # 날짜 파싱
            pub_date = item.get("pubDate", "")
            published_at = None
            if pub_date:
                try:
                    from dateutil import parser as date_parser
                    published_at = date_parser.parse(pub_date)
                except ValueError:
                    pass

            return ContentItem(
                id=self.generate_id(link),
                title=title,
                url=link,
                source="네이버 검색",
                content_type=ContentType.NEWS,
                published_at=published_at,
                description=description,
                priority=Priority.MEDIUM,
            )

        except Exception as e:
            logger.debug(f"Failed to parse API item: {e}")
            return None

    def _clean_html(self, text: str) -> str:
        """HTML 엔티티 및 태그 제거"""
        import re
        import html
        text = html.unescape(text)
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()
