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
class MarketSummary:
    """시장 종합 데이터"""
    kospi: Optional[IndexData] = None
    kosdaq: Optional[IndexData] = None
    usd_krw: Optional[ExchangeRate] = None
    jpy_krw: Optional[ExchangeRate] = None
    eur_krw: Optional[ExchangeRate] = None
    wti: Optional[IndexData] = None  # 유가
    gold: Optional[IndexData] = None  # 금
    timestamp: Optional[str] = None


class MarketDataCollector:
    """시장 데이터 수집기"""

    SISE_URL = "https://finance.naver.com/sise/"
    MARKETINDEX_URL = "https://finance.naver.com/marketindex/"

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


# 전역 인스턴스
market_data_collector = MarketDataCollector()
