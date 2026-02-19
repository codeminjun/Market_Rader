"""
시장 데이터 수집기
코스피, 코스닥, 환율 등 실시간 시장 데이터 수집
"""
from dataclasses import dataclass
from typing import Optional
import requests
from bs4 import BeautifulSoup

from src.utils.logger import logger


@dataclass
class IndexData:
    """지수 데이터"""
    name: str           # 지수명 (코스피, 코스닥 등)
    value: float        # 현재값
    change: float       # 변동폭
    change_percent: float  # 변동률 (%)
    is_up: bool         # 상승 여부


@dataclass
class ExchangeRate:
    """환율 데이터"""
    name: str           # 통화명 (USD, JPY, EUR 등)
    value: float        # 현재값
    change: float       # 변동폭
    change_percent: float  # 변동률 (%)
    is_up: bool         # 상승 여부


@dataclass
class SectorETFData:
    """섹터 ETF 시세 데이터"""
    sector: str             # 섹터명 (반도체, 2차전지 등)
    etf_name: str           # ETF명 (KODEX 반도체 등)
    etf_code: str           # 종목코드 (091160 등)
    price: float            # 현재가
    change: float           # 변동폭
    change_percent: float   # 변동률 (%)
    is_up: bool             # 상승 여부


@dataclass
class MarketSummary:
    """시장 종합 데이터"""
    kospi: Optional[IndexData] = None
    kosdaq: Optional[IndexData] = None
    usd_krw: Optional[ExchangeRate] = None
    jpy_krw: Optional[ExchangeRate] = None
    eur_krw: Optional[ExchangeRate] = None
    wti: Optional[IndexData] = None  # 유가
    gold: Optional[IndexData] = None  # 금
    sector_etfs: Optional[dict] = None  # {섹터명: SectorETFData}
    timestamp: Optional[str] = None


class MarketDataCollector:
    """시장 데이터 수집기"""

    SISE_URL = "https://finance.naver.com/sise/"
    MARKETINDEX_URL = "https://finance.naver.com/marketindex/"

    # 섹터 → ETF 매핑
    SECTOR_ETF_MAP = {
        "반도체": ("KODEX 반도체", "091160"),
        "2차전지": ("KODEX 2차전지산업", "305720"),
        "AI/소프트웨어": ("KODEX AI반도체핵심장비", "395160"),
        "자동차": ("KODEX 자동차", "091180"),
        "바이오": ("KODEX 바이오", "244580"),
        "금융": ("KODEX 은행", "091170"),
        "방산": ("TIGER K방산&우주", "463250"),
        "조선": ("TIGER 조선TOP10", "494670"),
        "에너지": ("KODEX 에너지화학", "117460"),
    }

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        self._session = requests.Session()
        self._session.headers.update(self.headers)

    def collect(self) -> MarketSummary:
        """시장 데이터 수집"""
        summary = MarketSummary()

        # 1. 코스피/코스닥 수집
        indices = self._collect_indices()
        summary.kospi = indices.get("kospi")
        summary.kosdaq = indices.get("kosdaq")

        # 2. 환율 수집
        exchange = self._collect_exchange_rates()
        summary.usd_krw = exchange.get("usd")
        summary.jpy_krw = exchange.get("jpy")
        summary.eur_krw = exchange.get("eur")

        # 3. 원자재 (유가, 금)
        commodities = self._collect_commodities()
        summary.wti = commodities.get("wti")
        summary.gold = commodities.get("gold")

        # 4. 섹터 ETF 시세
        summary.sector_etfs = self.collect_sector_etfs()

        from datetime import datetime
        summary.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        return summary

    def _collect_indices(self) -> dict[str, IndexData]:
        """코스피/코스닥 지수 수집"""
        indices = {}

        try:
            response = self._session.get(self.SISE_URL, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            # 코스피
            kospi_area = soup.select_one("#KOSPI_now")
            if kospi_area:
                kospi = self._parse_index_from_sise(soup, "KOSPI", "코스피")
                if kospi:
                    indices["kospi"] = kospi

            # 코스닥
            kosdaq_area = soup.select_one("#KOSDAQ_now")
            if kosdaq_area:
                kosdaq = self._parse_index_from_sise(soup, "KOSDAQ", "코스닥")
                if kosdaq:
                    indices["kosdaq"] = kosdaq

        except Exception as e:
            logger.error(f"Failed to collect indices: {e}")

        return indices

    def _parse_index_from_sise(self, soup, index_id: str, name: str) -> Optional[IndexData]:
        """지수 데이터 파싱"""
        import re

        try:
            # 현재가
            value_elem = soup.select_one(f"#{index_id}_now")
            if not value_elem:
                return None
            value = float(value_elem.get_text(strip=True).replace(",", ""))

            # 변동폭 및 변동률 (하나의 요소에 포함)
            # 예: "30.46 +0.65%상승" 또는 "6.80 -0.72%하락"
            change_elem = soup.select_one(f"#{index_id}_change")
            change = 0.0
            change_percent = 0.0
            is_up = True

            if change_elem:
                change_text = change_elem.get_text(strip=True)
                # 상승/하락 판단: ndown/nup 아이콘 클래스로 확인
                ndown_elem = change_elem.select_one(".ndown")
                nup_elem = change_elem.select_one(".nup")
                if ndown_elem is not None:
                    is_up = False
                elif nup_elem is not None:
                    is_up = True
                else:
                    # fallback: 퍼센트 부호로 판단 (blind 텍스트 제외)
                    is_up = "-" not in change_text.split("%")[0] if "%" in change_text else True

                # 숫자 추출: "30.46 +0.65%상승" -> ["30.46", "0.65"]
                numbers = re.findall(r'[\d,]+\.?\d*', change_text)
                if len(numbers) >= 1:
                    change = float(numbers[0].replace(",", ""))
                if len(numbers) >= 2:
                    change_percent = float(numbers[1].replace(",", ""))

            # 부호 적용
            if not is_up:
                change = -abs(change)
                change_percent = -abs(change_percent)

            return IndexData(
                name=name,
                value=value,
                change=change,
                change_percent=change_percent,
                is_up=is_up,
            )

        except Exception as e:
            logger.debug(f"Failed to parse {name}: {e}")
            return None

    def _collect_exchange_rates(self) -> dict[str, ExchangeRate]:
        """환율 데이터 수집"""
        rates = {}

        try:
            response = self._session.get(self.MARKETINDEX_URL, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            # 환율 영역 찾기
            exchange_items = soup.select("#exchangeList li")

            for item in exchange_items:
                rate = self._parse_exchange_item(item)
                if rate:
                    name_upper = rate.name.upper()
                    if "USD" in name_upper or "달러" in rate.name or "미국" in rate.name:
                        rates["usd"] = rate
                    elif "JPY" in name_upper or "엔" in rate.name or "일본" in rate.name:
                        rates["jpy"] = rate
                    elif "EUR" in name_upper or "유로" in rate.name or "유럽" in rate.name:
                        rates["eur"] = rate

        except Exception as e:
            logger.error(f"Failed to collect exchange rates: {e}")

        return rates

    def _parse_exchange_item(self, item) -> Optional[ExchangeRate]:
        """환율 항목 파싱"""
        try:
            # 통화명 (.blind에서 추출)
            blind_elem = item.select_one(".blind")
            if not blind_elem:
                return None
            name = blind_elem.get_text(strip=True)

            # 현재가
            value_elem = item.select_one(".value")
            if not value_elem:
                return None
            value = float(value_elem.get_text(strip=True).replace(",", ""))

            # 변동폭
            change_elem = item.select_one(".change")
            change = 0.0
            if change_elem:
                change_text = change_elem.get_text(strip=True).replace(",", "")
                change = float(change_text) if change_text else 0.0

            # 상승/하락 판단 (head_info 클래스로)
            is_up = True
            head_info = item.select_one(".head_info")
            if head_info:
                head_classes = " ".join(head_info.get("class", []))
                if "point_dn" in head_classes:
                    is_up = False
                elif "point_up" in head_classes:
                    is_up = True
            else:
                # fallback: blind 텍스트 확인
                blind_texts = [b.get_text(strip=True) for b in item.select(".blind")]
                if "하락" in blind_texts:
                    is_up = False

            # 변동률 계산
            change_percent = (change / (value - change)) * 100 if value != change else 0.0

            # 부호 적용
            if not is_up:
                change = -abs(change)
                change_percent = -abs(change_percent)

            return ExchangeRate(
                name=name,
                value=value,
                change=change,
                change_percent=change_percent,
                is_up=is_up,
            )

        except Exception as e:
            logger.debug(f"Failed to parse exchange item: {e}")
            return None

    def _collect_commodities(self) -> dict[str, IndexData]:
        """원자재 데이터 수집 (유가, 금)"""
        commodities = {}

        try:
            response = self._session.get(self.MARKETINDEX_URL, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            # 원자재 영역
            commodity_items = soup.select("#oilGoldList li")

            for item in commodity_items:
                commodity = self._parse_commodity_item(item)
                if commodity:
                    if "WTI" in commodity.name.upper():
                        commodities["wti"] = commodity
                    elif "국제" in commodity.name and "금" in commodity.name:
                        commodities["gold"] = commodity

        except Exception as e:
            logger.error(f"Failed to collect commodities: {e}")

        return commodities

    def _parse_commodity_item(self, item) -> Optional[IndexData]:
        """원자재 항목 파싱"""
        try:
            # 이름 (.blind에서 추출)
            blind_elem = item.select_one(".blind")
            if not blind_elem:
                return None
            name = blind_elem.get_text(strip=True)

            # 현재가
            value_elem = item.select_one(".value")
            if not value_elem:
                return None
            value = float(value_elem.get_text(strip=True).replace(",", ""))

            # 변동폭
            change_elem = item.select_one(".change")
            change = 0.0
            if change_elem:
                change_text = change_elem.get_text(strip=True).replace(",", "")
                change = float(change_text) if change_text else 0.0

            # 상승/하락 판단 (head_info 클래스로)
            is_up = True
            head_info = item.select_one(".head_info")
            if head_info:
                head_classes = " ".join(head_info.get("class", []))
                if "point_dn" in head_classes:
                    is_up = False
                elif "point_up" in head_classes:
                    is_up = True
            else:
                # fallback: blind 텍스트 확인
                blind_texts = [b.get_text(strip=True) for b in item.select(".blind")]
                if "하락" in blind_texts:
                    is_up = False

            # 변동률 계산
            change_percent = (change / (value - change)) * 100 if value != change else 0.0

            # 부호 적용
            if not is_up:
                change = -abs(change)
                change_percent = -abs(change_percent)

            return IndexData(
                name=name,
                value=value,
                change=change,
                change_percent=change_percent,
                is_up=is_up,
            )

        except Exception as e:
            logger.debug(f"Failed to parse commodity item: {e}")
            return None

    def collect_sector_etfs(self) -> dict[str, SectorETFData]:
        """
        섹터 ETF 시세 수집 (Naver Finance Polling API)

        Returns:
            {"반도체": SectorETFData, "2차전지": SectorETFData, ...}
            실패 시 빈 dict 반환
        """
        etf_codes = [code for _, code in self.SECTOR_ETF_MAP.values()]
        query = ",".join(etf_codes)
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{query}"

        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # 종목코드 → 섹터 역매핑
            code_to_sector = {code: sector for sector, (_, code) in self.SECTOR_ETF_MAP.items()}

            result = {}
            items = data.get("result", {}).get("areas", [])
            for area in items:
                for item in area.get("datas", []):
                    code = item.get("cd", "")
                    if code not in code_to_sector:
                        continue

                    sector = code_to_sector[code]
                    etf_name, etf_code = self.SECTOR_ETF_MAP[sector]

                    price = float(item.get("nv", 0))       # 현재가
                    change = float(item.get("cv", 0))       # 변동폭
                    change_percent = float(item.get("cr", 0))  # 변동률
                    # aq: "상승"/"하락"/"보합" 또는 sv: 부호로 판단
                    is_up = change >= 0

                    result[sector] = SectorETFData(
                        sector=sector,
                        etf_name=etf_name,
                        etf_code=etf_code,
                        price=price,
                        change=change,
                        change_percent=change_percent,
                        is_up=is_up,
                    )

            if result:
                logger.info(f"Collected {len(result)} sector ETF prices via Polling API")
                return result

            # Polling API가 빈 결과를 반환한 경우 fallback
            logger.warning("Polling API returned empty data, trying HTML fallback")
            return self._collect_sector_etfs_html()

        except Exception as e:
            logger.warning(f"Polling API failed: {e}, trying HTML fallback")
            return self._collect_sector_etfs_html()

    def _collect_sector_etfs_html(self) -> dict[str, SectorETFData]:
        """
        섹터 ETF 시세 HTML 스크래핑 (fallback)

        개별 종목 페이지에서 시세를 가져옴
        """
        import re
        import time

        result = {}

        for i, (sector, (etf_name, etf_code)) in enumerate(self.SECTOR_ETF_MAP.items()):
            # rate limit 방지: 두 번째 요청부터 딜레이
            if i > 0:
                time.sleep(0.3)

            try:
                url = f"https://finance.naver.com/item/main.naver?code={etf_code}"
                response = self._session.get(url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "lxml")

                # 현재가
                price_elem = soup.select_one("p.no_today .blind")
                if not price_elem:
                    continue
                price = float(price_elem.get_text(strip=True).replace(",", ""))

                # 변동폭
                change_elem = soup.select_one("p.no_exday .blind")
                change = 0.0
                is_up = True
                if change_elem:
                    change_text = change_elem.get_text(strip=True)
                    # "하락 150 -0.54%" 또는 "상승 200 +0.72%" 형태
                    if "하락" in change_text:
                        is_up = False
                    numbers = re.findall(r'[\d,]+\.?\d*', change_text)
                    if numbers:
                        change = float(numbers[0].replace(",", ""))
                        if not is_up:
                            change = -change

                # 변동률 계산
                prev_price = price - change
                change_percent = (change / prev_price * 100) if prev_price != 0 else 0.0

                result[sector] = SectorETFData(
                    sector=sector,
                    etf_name=etf_name,
                    etf_code=etf_code,
                    price=price,
                    change=change,
                    change_percent=round(change_percent, 2),
                    is_up=is_up,
                )

            except Exception as e:
                logger.debug(f"Failed to scrape ETF {etf_name} ({etf_code}): {e}")
                continue

        if result:
            logger.info(f"Collected {len(result)} sector ETF prices via HTML fallback")

        return result


# 전역 인스턴스
market_data_collector = MarketDataCollector()
