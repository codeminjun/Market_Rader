"""
네이버 금융 뉴스 수집기
네이버 금융에서 주요 뉴스 수집
"""
import re
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
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

    # 기자명 추출 패턴
    JOURNALIST_PATTERNS = [
        re.compile(r'([가-힣]{2,4})\s*기자'),           # "홍길동 기자"
        re.compile(r'([가-힣]{2,4})\s*특파원'),         # "홍길동 특파원"
        re.compile(r'([가-힣]{2,4})\s*대표'),           # "홍길동 대표"
        re.compile(r'([가-힣]{2,4})\s*편집장'),         # "홍길동 편집장"
        re.compile(r'([가-힣]{2,4})\s*에디터'),         # "홍길동 에디터"
        re.compile(r'기자\s*:\s*([가-힣]{2,4})'),       # "기자: 홍길동"
        re.compile(r'By\s+([가-힣]{2,4})'),             # "By 홍길동"
    ]

    def __init__(self, categories: Optional[list[str]] = None, extract_journalist: bool = True):
        super().__init__("네이버 금융", ContentType.NEWS)
        self.categories = categories or ["stock", "economy"]
        self.extract_journalist = extract_journalist
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        # 세션 재사용으로 TCP 연결 오버헤드 감소
        self._session = requests.Session()
        self._session.headers.update(self.headers)

    def collect(self) -> list[ContentItem]:
        """네이버 금융 뉴스 수집"""
        items = []

        for category in self.categories:
            if category in self.CATEGORIES:
                category_items = self._collect_category(category)
                items.extend(category_items)

        # 기자명 추출 (병렬 처리)
        if self.extract_journalist and items:
            self._extract_journalists_parallel(items)

        logger.info(f"Collected {len(items)} items from {self.name}")
        return items

    def _extract_journalists_parallel(self, items: list[ContentItem], max_workers: int = 5):
        """기자명 병렬 추출 (상위 N개 기사만)"""
        # 상위 20개 기사만 기자명 추출 (성능 최적화)
        target_items = items[:20]

        def fetch_journalist(item: ContentItem):
            try:
                journalist, description = self._fetch_article_details(item.url)
                if journalist:
                    item.extra_data["journalist"] = journalist
                if description:
                    item.description = description
            except Exception as e:
                logger.debug(f"Failed to extract journalist for {item.title[:30]}: {e}")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fetch_journalist, item) for item in target_items]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    pass

        journalist_count = sum(1 for item in target_items if item.extra_data.get("journalist"))
        logger.info(f"Extracted journalists from {journalist_count}/{len(target_items)} articles")

    def _fetch_article_details(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """기사 본문에서 기자명과 설명 추출"""
        try:
            response = self._session.get(url, timeout=5, allow_redirects=False)

            # 리다이렉트 처리 (네이버 금융 → 네이버 뉴스)
            if response.status_code in (301, 302, 303, 307, 308):
                redirect_url = response.headers.get("Location")
                if redirect_url:
                    response = self._session.get(redirect_url, timeout=5)
            elif "top.location.href" in response.text:
                # JavaScript 리다이렉트 처리
                match = re.search(r"top\.location\.href='([^']+)'", response.text)
                if match:
                    redirect_url = match.group(1)
                    response = self._session.get(redirect_url, timeout=5)

            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            journalist = None
            description = None

            # 1. 기자명 추출 - 네이버 뉴스 페이지 구조
            # 네이버 뉴스: .media_end_head_journalist, .byline_s, .journalistCard
            byline_selectors = [
                ".media_end_head_journalist_name",  # 네이버 뉴스 기자명
                ".byline_s",                         # 구 버전
                ".journalistCard_journalist_name",   # 기자 카드
                ".journalist_name",
                ".reporter_name",
                "em.media_end_head_journalist_name",
            ]

            for selector in byline_selectors:
                elem = soup.select_one(selector)
                if elem:
                    text = elem.get_text(strip=True)
                    journalist = self._extract_journalist_name(text)
                    if journalist:
                        break

            # byline에서 못 찾으면 본문 마지막 부분에서 시도
            if not journalist:
                article_body = soup.select_one("#dic_area, #newsct_article, .newsct_article, #articeBody")
                if article_body:
                    # 본문 텍스트의 마지막 500자에서 기자명 추출
                    body_text = article_body.get_text()
                    last_part = body_text[-500:] if len(body_text) > 500 else body_text
                    journalist = self._extract_journalist_name(last_part)

            # 2. 본문 요약 추출 (첫 200자)
            article_body = soup.select_one("#dic_area, #newsct_article, .newsct_article, #articeBody")
            if article_body:
                body_text = article_body.get_text(strip=True)
                # 앞부분 200자 정도를 description으로
                if len(body_text) > 50:
                    description = body_text[:200].strip()
                    if len(body_text) > 200:
                        description += "..."

            return journalist, description

        except Exception as e:
            logger.debug(f"Failed to fetch article details: {e}")
            return None, None

    def _extract_journalist_name(self, text: str) -> Optional[str]:
        """텍스트에서 기자명 추출"""
        for pattern in self.JOURNALIST_PATTERNS:
            match = pattern.search(text)
            if match:
                name = match.group(1)
                # 2~4글자 한글 이름만 허용
                if 2 <= len(name) <= 4:
                    return name
        return None

    def _collect_category(self, category: str) -> list[ContentItem]:
        """카테고리별 뉴스 수집"""
        items = []
        cat_info = self.CATEGORIES[category]

        try:
            # 메인 뉴스 페이지에서 수집
            url = f"{self.BASE_URL}mainnews.naver"
            response = self._session.get(url, timeout=10)
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
