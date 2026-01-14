"""
증권사 Morning Brief 수집기
네이버 증권 시황정보에서 Morning Brief PDF 수집 및 OCR 텍스트 추출
"""
import io
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Optional
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


class MorningBriefCollector(BaseCollector):
    """증권사 Morning Brief 수집기"""

    BASE_URL = "https://finance.naver.com/research/"
    MARKET_INFO_URL = "https://finance.naver.com/research/market_info_list.naver"

    # 우선 수집 대상 증권사 (Morning Brief 제공)
    PRIORITY_BROKERS = [
        "SK증권",
        "신한투자증권",
        "다올투자증권",
        "유안타증권",
        "DS투자증권",
        "IBK투자증권",
        "키움증권",
        "한화투자증권",
    ]

    # Morning Brief 키워드
    MORNING_KEYWORDS = [
        "Morning Brief",
        "Morning Snapshot",
        "모닝 브리프",
        "아침",
        "Daily",
        "데일리",
        "시황",
    ]

    def __init__(self, max_briefs: int = 3, use_ocr: bool = True):
        super().__init__("Morning Brief", ContentType.REPORT)
        self.max_briefs = max_briefs
        self.use_ocr = use_ocr
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        # 세션 재사용으로 TCP 연결 오버헤드 감소
        self._session = requests.Session()
        self._session.headers.update(self.headers)

    def collect(self) -> list[ContentItem]:
        """Morning Brief 수집 (병렬 PDF 처리)"""
        items = []

        try:
            # 시황정보 목록 페이지 가져오기
            response = self._session.get(self.MARKET_INFO_URL, timeout=10)
            response.raise_for_status()
            response.encoding = "euc-kr"

            soup = BeautifulSoup(response.text, "lxml")
            table = soup.select_one("table.type_1")

            if not table:
                logger.warning("Could not find market info table")
                return items

            rows = table.select("tr")[1:]  # 헤더 제외

            # 1단계: 후보 행 필터링 (PDF URL 가져오기 전)
            candidate_rows = []
            for row in rows:
                if len(candidate_rows) >= self.max_briefs * 2:  # 여유분 확보
                    break
                brief_info = self._preparse_morning_brief(row)
                if brief_info:
                    candidate_rows.append(brief_info)

            # 2단계: 병렬로 PDF URL 조회 및 텍스트 추출
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(self._process_brief, info): info
                    for info in candidate_rows[:self.max_briefs]
                }

                for future in as_completed(futures):
                    try:
                        item = future.result()
                        if item:
                            items.append(item)
                    except Exception as e:
                        logger.debug(f"Failed to process brief: {e}")

            logger.info(f"Collected {len(items)} Morning Briefs")

        except Exception as e:
            logger.error(f"Failed to collect Morning Briefs: {e}")

        return items

    def _preparse_morning_brief(self, row) -> Optional[dict]:
        """Morning Brief 행 사전 파싱 (PDF 처리 전)"""
        try:
            cells = row.select("td")
            if len(cells) < 4:
                return None

            title_elem = cells[0].select_one("a")
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            href = title_elem.get("href", "")
            broker = cells[1].get_text(strip=True) if len(cells) > 1 else ""

            if not self._is_morning_brief(title, broker):
                return None

            # 날짜 확인
            date_cell = cells[-1]
            if date_cell:
                date_str = date_cell.get_text(strip=True)
                try:
                    pub_date = datetime.strptime(date_str, "%y.%m.%d")
                    yesterday = datetime.now() - timedelta(days=1)
                    if pub_date.date() < yesterday.date():
                        return None
                except ValueError:
                    pass

            if not href or not title:
                return None

            detail_url = f"https://finance.naver.com/research/{href}"

            return {
                "title": title,
                "broker": broker,
                "detail_url": detail_url,
                "href": href,
            }

        except Exception as e:
            logger.debug(f"Failed to preparse morning brief row: {e}")
            return None

    def _process_brief(self, info: dict) -> Optional[ContentItem]:
        """단일 Brief 처리 (PDF URL 조회 + 텍스트 추출)"""
        try:
            pdf_url = self._get_pdf_url(info["detail_url"])
            if not pdf_url:
                return None

            pdf_text = self._extract_pdf_text(pdf_url)

            return ContentItem(
                id=self.generate_id(pdf_url),
                title=f"[{info['broker']}] {info['title']}",
                url=info["detail_url"],
                source=info["broker"],
                content_type=ContentType.REPORT,
                published_at=datetime.now(),
                priority=Priority.HIGH,
                description=pdf_text[:2000] if pdf_text else None,
                extra_data={
                    "broker": info["broker"],
                    "pdf_url": pdf_url,
                    "pdf_text": pdf_text,
                    "is_morning_brief": True,
                },
            )

        except Exception as e:
            logger.debug(f"Failed to process brief: {e}")
            return None

    def _is_morning_brief(self, title: str, broker: str) -> bool:
        """Morning Brief 여부 확인"""
        title_lower = title.lower()

        # 키워드 매칭
        for keyword in self.MORNING_KEYWORDS:
            if keyword.lower() in title_lower:
                return True

        return False

    def _get_pdf_url(self, detail_url: str) -> Optional[str]:
        """상세 페이지에서 PDF URL 추출"""
        try:
            response = self._session.get(detail_url, timeout=10)
            response.raise_for_status()
            response.encoding = "euc-kr"

            soup = BeautifulSoup(response.text, "lxml")

            # PDF 링크 찾기
            pdf_link = soup.select_one("a[href*='.pdf']")
            if pdf_link:
                return pdf_link.get("href")

            return None

        except Exception as e:
            logger.debug(f"Failed to get PDF URL: {e}")
            return None

    def _extract_pdf_text(self, pdf_url: str) -> Optional[str]:
        """PDF에서 텍스트 추출 (OCR 우선)"""
        if self.use_ocr and pytesseract and fitz:
            return self._extract_with_ocr(pdf_url)
        elif fitz:
            return self._extract_with_pymupdf(pdf_url)
        else:
            logger.warning("No PDF extraction library available")
            return None

    def _extract_with_ocr(self, pdf_url: str) -> Optional[str]:
        """OCR을 사용한 PDF 텍스트 추출 (도표/이미지 지원)"""
        try:
            # PDF 다운로드 (세션 재사용)
            response = self._session.get(pdf_url, timeout=60)
            response.raise_for_status()

            # PDF 열기
            pdf_bytes = io.BytesIO(response.content)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            text_parts = []
            max_pages = min(5, len(doc))  # 최대 5페이지

            for page_num in range(max_pages):
                page = doc[page_num]

                # 1. 먼저 일반 텍스트 추출 시도
                text = page.get_text("text")

                # 2. 텍스트가 적으면 OCR 시도 (이미지/도표 많은 경우)
                if len(text.strip()) < 100:
                    # 페이지를 고해상도 이미지로 변환
                    mat = fitz.Matrix(2.0, 2.0)  # 2x 스케일 (더 선명한 OCR)
                    pix = page.get_pixmap(matrix=mat)

                    # PIL Image로 변환
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                    # OCR 실행 (한국어 + 영어)
                    try:
                        ocr_text = pytesseract.image_to_string(
                            img,
                            lang='kor+eng',
                            config='--psm 6'  # 블록 단위 텍스트 인식
                        )
                        if ocr_text.strip():
                            text = ocr_text
                    except Exception as ocr_err:
                        logger.debug(f"OCR failed for page {page_num}: {ocr_err}")

                if text.strip():
                    text_parts.append(f"[페이지 {page_num + 1}]\n{text}")

            doc.close()

            full_text = "\n\n".join(text_parts)
            full_text = self._clean_pdf_text(full_text)

            logger.info(f"Extracted {len(full_text)} chars using OCR from {pdf_url[:50]}...")
            return full_text if full_text else None

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            # 폴백: 일반 텍스트 추출
            return self._extract_with_pymupdf(pdf_url)

    def _extract_with_pymupdf(self, pdf_url: str) -> Optional[str]:
        """PyMuPDF를 사용한 기본 텍스트 추출"""
        try:
            # PDF 다운로드 (세션 재사용)
            response = self._session.get(pdf_url, timeout=30)
            response.raise_for_status()

            # PDF 열기
            pdf_bytes = io.BytesIO(response.content)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            # 모든 페이지에서 텍스트 추출
            text_parts = []
            for page_num in range(min(5, len(doc))):  # 최대 5페이지만
                page = doc[page_num]
                text = page.get_text()
                if text:
                    text_parts.append(text)

            doc.close()

            full_text = "\n".join(text_parts)
            full_text = self._clean_pdf_text(full_text)

            return full_text if full_text else None

        except Exception as e:
            logger.debug(f"Failed to extract PDF text: {e}")
            return None

    def _clean_pdf_text(self, text: str) -> str:
        """PDF 텍스트 정리"""
        # 불필요한 공백 제거
        text = re.sub(r'[ \t]+', ' ', text)
        # 연속된 줄바꿈 정리
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 앞뒤 공백 제거
        text = text.strip()
        return text


# 전역 인스턴스
morning_brief_collector = MorningBriefCollector()
