"""
네이버 증권 리서치 수집기
증권사 애널리스트 리포트 수집 + 시총 50위 종목 필터링 + PDF OCR 텍스트 추출
"""
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional
import re
import requests
from bs4 import BeautifulSoup

# PDF/OCR 라이브러리
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None

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

    def __init__(
        self,
        categories: Optional[list[str]] = None,
        filter_top50: bool = True,
        extract_pdf: bool = False,
        max_pdf_extract: int = 5,
    ):
        super().__init__("네이버 증권 리서치", ContentType.REPORT)
        self.categories = categories or ["invest", "company", "market"]
        self.filter_top50 = filter_top50
        self.extract_pdf = extract_pdf  # PDF 텍스트 추출 여부
        self.max_pdf_extract = max_pdf_extract  # PDF 추출 최대 개수
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        # 세션 재사용으로 TCP 연결 오버헤드 감소
        self._session = requests.Session()
        self._session.headers.update(self.headers)
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
        """리서치 리포트 수집 (병렬 처리)"""
        items = []

        # 카테고리별 병렬 수집
        valid_categories = [c for c in self.categories if c in self.CATEGORIES]

        with ThreadPoolExecutor(max_workers=len(valid_categories)) as executor:
            futures = {
                executor.submit(self._collect_category, category): category
                for category in valid_categories
            }

            for future in as_completed(futures):
                category = futures[future]
                try:
                    category_items = future.result()
                    items.extend(category_items)
                except Exception as e:
                    logger.error(f"Failed to collect {category} reports: {e}")

        # PDF 텍스트 추출 (설정된 경우)
        if self.extract_pdf and items:
            items = self._extract_pdf_for_top_items(items)

        logger.info(f"Collected {len(items)} reports from {self.name}")
        return items

    def _extract_pdf_for_top_items(self, items: list[ContentItem]) -> list[ContentItem]:
        """상위 N개 리포트의 PDF 텍스트 추출 (병렬 처리)"""
        # 1순위: 기업분석 리포트 (목표가 있는 것)
        tier1 = [
            item for item in items
            if item.extra_data.get("stock_name") and item.extra_data.get("target_price")
        ]

        # 2순위: 기업분석 리포트 (종목명만 있는 것)
        tier2 = [
            item for item in items
            if item.extra_data.get("stock_name") and item not in tier1
        ]

        # 3순위: 시황정보/투자정보 리포트
        tier3 = [
            item for item in items
            if item.extra_data.get("category") in ("시황정보", "투자정보") and item not in tier1 and item not in tier2
        ]

        # 우선순위 순서로 합침
        priority_items = (tier1 + tier2 + tier3)[:self.max_pdf_extract]

        if not priority_items:
            priority_items = items[:self.max_pdf_extract]

        logger.info(f"Extracting PDF text for {len(priority_items)} reports")

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._extract_single_pdf, item): item
                for item in priority_items
            }

            for future in as_completed(futures):
                item = futures[future]
                try:
                    pdf_data = future.result()
                    if pdf_data:
                        item.extra_data["pdf_url"] = pdf_data.get("pdf_url")
                        item.extra_data["pdf_text"] = pdf_data.get("pdf_text")
                        item.extra_data["pdf_extracted"] = True
                except Exception as e:
                    logger.debug(f"PDF extraction failed for {item.title[:30]}: {e}")

        return items

    def _extract_single_pdf(self, item: ContentItem) -> Optional[dict]:
        """단일 리포트 PDF 추출"""
        try:
            # 상세 페이지에서 PDF URL 추출
            response = self._session.get(item.url, timeout=10)
            response.raise_for_status()
            response.encoding = "euc-kr"

            soup = BeautifulSoup(response.text, "lxml")
            pdf_link = soup.select_one("a[href*='.pdf']")

            if not pdf_link:
                return None

            pdf_url = pdf_link.get("href")
            if not pdf_url:
                return None

            # PDF 텍스트 추출
            pdf_text = self._extract_pdf_text(pdf_url)

            return {
                "pdf_url": pdf_url,
                "pdf_text": pdf_text,
            }

        except Exception as e:
            logger.debug(f"Failed to extract PDF for {item.url}: {e}")
            return None

    def _extract_pdf_text(self, pdf_url: str) -> Optional[str]:
        """PDF에서 텍스트 추출 (OCR 포함)"""
        if not fitz:
            logger.warning("PyMuPDF not available for PDF extraction")
            return None

        try:
            response = self._session.get(pdf_url, timeout=60)
            response.raise_for_status()

            pdf_bytes = io.BytesIO(response.content)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            text_parts = []
            max_pages = min(3, len(doc))  # 최대 3페이지만 (리포트는 첫 페이지가 중요)

            for page_num in range(max_pages):
                page = doc[page_num]
                text = page.get_text("text")

                # 텍스트가 적으면 OCR 시도
                if len(text.strip()) < 100 and pytesseract and Image:
                    try:
                        mat = fitz.Matrix(2.0, 2.0)
                        pix = page.get_pixmap(matrix=mat)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        ocr_text = pytesseract.image_to_string(
                            img, lang='kor+eng', config='--psm 6'
                        )
                        if ocr_text.strip():
                            text = ocr_text
                    except Exception as ocr_err:
                        logger.debug(f"OCR failed for page {page_num}: {ocr_err}")

                if text.strip():
                    text_parts.append(text)

            doc.close()

            full_text = "\n\n".join(text_parts)
            # 텍스트 정리
            full_text = re.sub(r'[ \t]+', ' ', full_text)
            full_text = re.sub(r'\n{3,}', '\n\n', full_text)

            logger.debug(f"Extracted {len(full_text)} chars from {pdf_url[:50]}...")
            return full_text.strip() if full_text else None

        except Exception as e:
            logger.debug(f"Failed to extract PDF text: {e}")
            return None

    def _collect_category(self, category: str) -> list[ContentItem]:
        """카테고리별 리포트 수집"""
        items = []
        cat_info = self.CATEGORIES[category]

        try:
            url = f"{self.BASE_URL}{cat_info['url']}"
            response = self._session.get(url, timeout=10)
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
