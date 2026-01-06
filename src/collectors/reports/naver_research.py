"""
네이버 증권 리서치 수집기
증권사 애널리스트 리포트 수집 + 시총 50위 종목 필터링
"""
from datetime import datetime
from typing import Optional
import re
import requests
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector, ContentItem, ContentType, Priority
from src.utils.logger import logger
from config.settings import get_top_companies


class NaverResearchCollector(BaseCollector):
    """네이버 증권 리서치 수집기"""

    BASE_URL = "https://finance.naver.com/research/"

    CATEGORIES = {
        "invest": {"url": "invest_list.naver", "name": "투자정보"},
        "company": {"url": "company_list.naver", "name": "기업분석"},
        "industry": {"url": "industry_list.naver", "name": "산업분석"},
        "market": {"url": "market_info_list.naver", "name": "시황정보"},
    }

    def __init__(self, categories: Optional[list[str]] = None, filter_top50: bool = True):
        super().__init__("네이버 증권 리서치", ContentType.REPORT)
        self.categories = categories or ["invest", "company", "market"]
        self.filter_top50 = filter_top50
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        # 시총 50위 기업 목록 로드
        self._load_top50_companies()

    def _load_top50_companies(self):
        """시총 50위 기업 목록 로드"""
        try:
            config = get_top_companies()
            self.top50_codes = set()
            self.top50_names = set()

            for company in config.get("korean_top50", []):
                if "code" in company:
                    self.top50_codes.add(company["code"])
                if "name" in company:
                    self.top50_names.add(company["name"])
        except Exception as e:
            logger.warning(f"Failed to load top50 companies: {e}")
            self.top50_codes = set()
            self.top50_names = set()

    def _is_top50_stock(self, stock_name: str, stock_code: str = "") -> bool:
        """시총 50위 종목인지 확인"""
        if not self.filter_top50:
            return True

        if stock_code and stock_code in self.top50_codes:
            return True

        # 종목명으로 검색 (부분 매칭)
        for name in self.top50_names:
            if name in stock_name or stock_name in name:
                return True

        return False

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
        """리포트 행 파싱 (목표가 변동 포함)"""
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

            # 종목명 및 종목코드 추출
            stock_name = ""
            stock_code = ""
            target_price = None
            price_change = None
            opinion = ""

            if category_name == "기업분석" and len(cells) > 0:
                stock_name = cells[0].get_text(strip=True)

                # 종목코드 추출 (링크에서)
                stock_link = cells[0].select_one("a")
                if stock_link:
                    stock_href = stock_link.get("href", "")
                    code_match = re.search(r'code=(\d{6})', stock_href)
                    if code_match:
                        stock_code = code_match.group(1)

                # 시총 50위 필터링
                if self.filter_top50 and not self._is_top50_stock(stock_name, stock_code):
                    return None

                # 목표가 추출 (있는 경우)
                if len(cells) >= 5:
                    # 의견 (매수/보유/매도 등)
                    opinion_cell = cells[3] if len(cells) > 3 else None
                    if opinion_cell:
                        opinion = opinion_cell.get_text(strip=True)

                    # 목표가
                    target_cell = cells[4] if len(cells) > 4 else None
                    if target_cell:
                        target_text = target_cell.get_text(strip=True).replace(",", "")
                        try:
                            target_price = int(re.sub(r'[^\d]', '', target_text))
                        except (ValueError, TypeError):
                            pass

                if stock_name:
                    # 목표가 변동 표시
                    if target_price and opinion:
                        title = f"[{stock_name}] {title} | {opinion} 목표가 {target_price:,}원"
                    elif target_price:
                        title = f"[{stock_name}] {title} | 목표가 {target_price:,}원"
                    else:
                        title = f"[{stock_name}] {title}"

            return ContentItem(
                id=self.generate_id(url),
                title=title,
                url=url,
                source=f"{broker} ({category_name})" if broker else f"증권 리서치 ({category_name})",
                content_type=ContentType.REPORT,
                published_at=published_at,
                priority=Priority.HIGH if stock_name else Priority.MEDIUM,
                extra_data={
                    "broker": broker,
                    "category": category_name,
                    "stock_name": stock_name,
                    "stock_code": stock_code,
                    "target_price": target_price,
                    "opinion": opinion,
                    "is_top50": bool(stock_name and self._is_top50_stock(stock_name, stock_code)),
                },
            )

        except Exception as e:
            logger.debug(f"Failed to parse report row: {e}")
            return None
