"""
네이버 증권 리서치 수집기
증권사 애널리스트 리포트 수집
"""
from datetime import datetime
from typing import Optional
import requests
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector, ContentItem, ContentType, Priority
from src.utils.logger import logger


class NaverResearchCollector(BaseCollector):
    """네이버 증권 리서치 수집기"""

    BASE_URL = "https://finance.naver.com/research/"

    CATEGORIES = {
        "invest": {"url": "invest_list.naver", "name": "투자정보"},
        "company": {"url": "company_list.naver", "name": "기업분석"},
        "industry": {"url": "industry_list.naver", "name": "산업분석"},
        "market": {"url": "market_list.naver", "name": "시황정보"},
    }

    def __init__(self, categories: Optional[list[str]] = None):
        super().__init__("네이버 증권 리서치", ContentType.REPORT)
        self.categories = categories or ["invest", "company", "market"]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    def collect(self) -> list[ContentItem]:
        """리서치 리포트 수집"""
        items = []

        for category in self.categories:
            if category in self.CATEGORIES:
                category_items = self._collect_category(category)
                items.extend(category_items)

        logger.info(f"Collected {len(items)} reports from {self.name}")
        return items

    def _collect_category(self, category: str) -> list[ContentItem]:
        """카테고리별 리포트 수집"""
        items = []
        cat_info = self.CATEGORIES[category]

        try:
            url = f"{self.BASE_URL}{cat_info['url']}"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            response.encoding = "euc-kr"

            soup = BeautifulSoup(response.text, "lxml")

            # 리포트 테이블 파싱
            table = soup.select_one("table.type_1")
            if not table:
                return items

            rows = table.select("tr")[1:]  # 헤더 제외

            for row in rows[:15]:  # 최대 15개
                item = self._parse_report_row(row, cat_info["name"])
                if item:
                    items.append(item)

        except requests.RequestException as e:
            logger.error(f"Failed to fetch {category} reports: {e}")
        except Exception as e:
            logger.error(f"Error parsing {category} reports: {e}")

        return items

    def _parse_report_row(self, row, category_name: str) -> Optional[ContentItem]:
        """리포트 행 파싱"""
        try:
            cells = row.select("td")
            if len(cells) < 4:
                return None

            # 제목과 링크
            title_cell = cells[0] if category_name != "기업분석" else cells[1]
            title_elem = title_cell.select_one("a")

            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            href = title_elem.get("href", "")

            if not href or not title:
                return None

            # 전체 URL 생성
            if href.startswith("/"):
                url = f"https://finance.naver.com{href}"
            else:
                url = f"{self.BASE_URL}{href}"

            # 증권사
            broker_cell = cells[1] if category_name != "기업분석" else cells[2]
            broker = broker_cell.get_text(strip=True) if broker_cell else ""

            # 날짜
            date_cell = cells[-1]
            published_at = None
            if date_cell:
                date_str = date_cell.get_text(strip=True)
                try:
                    published_at = datetime.strptime(date_str, "%y.%m.%d")
                except ValueError:
                    try:
                        published_at = datetime.strptime(date_str, "%Y.%m.%d")
                    except ValueError:
                        pass

            # 종목명 (기업분석의 경우)
            stock_name = ""
            if category_name == "기업분석" and len(cells) > 0:
                stock_name = cells[0].get_text(strip=True)
                if stock_name:
                    title = f"[{stock_name}] {title}"

            return ContentItem(
                id=self.generate_id(url),
                title=title,
                url=url,
                source=f"{broker} ({category_name})" if broker else f"증권 리서치 ({category_name})",
                content_type=ContentType.REPORT,
                published_at=published_at,
                priority=Priority.MEDIUM,
                extra_data={
                    "broker": broker,
                    "category": category_name,
                    "stock_name": stock_name,
                },
            )

        except Exception as e:
            logger.debug(f"Failed to parse report row: {e}")
            return None
