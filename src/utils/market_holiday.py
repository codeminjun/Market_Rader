"""
시장 휴장일 감지 유틸리티
한국(KRX) 및 미국(NYSE) 휴장일을 판별
"""
from dataclasses import dataclass, field
from datetime import date, datetime

import holidays


@dataclass
class MarketHolidayInfo:
    """시장 휴장일 정보"""
    is_holiday: bool = False
    krx_closed: bool = False
    nyse_closed: bool = False
    krx_holiday_name: str = ""
    nyse_holiday_name: str = ""

    @property
    def summary(self) -> str:
        """휴장 요약 문자열"""
        parts = []
        if self.krx_closed:
            parts.append(f"KRX: {self.krx_holiday_name}")
        if self.nyse_closed:
            parts.append(f"NYSE: {self.nyse_holiday_name}")
        return " / ".join(parts) if parts else "개장일"


def check_market_holidays(target_date: date | None = None) -> MarketHolidayInfo:
    """
    주어진 날짜의 KRX/NYSE 휴장 여부를 판별

    Args:
        target_date: 확인할 날짜 (None이면 오늘)

    Returns:
        MarketHolidayInfo 객체
    """
    if target_date is None:
        target_date = date.today()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    info = MarketHolidayInfo()

    # KRX 휴장일 (한국 공휴일 기반)
    kr_holidays = holidays.KR(years=target_date.year)
    if target_date in kr_holidays:
        info.krx_closed = True
        info.krx_holiday_name = kr_holidays.get(target_date, "공휴일")

    # NYSE 휴장일
    try:
        nyse_holidays = holidays.financial_holidays("NYSE", years=target_date.year)
    except Exception:
        # fallback: 미국 공휴일 사용
        nyse_holidays = holidays.US(years=target_date.year)

    if target_date in nyse_holidays:
        info.nyse_closed = True
        info.nyse_holiday_name = nyse_holidays.get(target_date, "Public Holiday")

    info.is_holiday = info.krx_closed or info.nyse_closed
    return info
