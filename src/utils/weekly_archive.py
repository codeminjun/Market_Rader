"""
주간 뉴스 아카이브 모듈
매일 수집된 뉴스를 축적하고 토요일 주간 리뷰에 제공
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config.settings import settings
from src.collectors.base import ContentItem, ContentType
from src.utils.logger import logger


class WeeklyNewsArchive:
    """주간 뉴스 아카이브 - 매일 뉴스를 축적하고 주간 리뷰에 제공"""

    def __init__(self, archive_path: Optional[Path] = None):
        self.archive_path = archive_path or settings.WEEKLY_ARCHIVE_FILE

    def _load(self) -> dict:
        """아카이브 파일 로드"""
        if not self.archive_path.exists():
            return self._empty_archive()

        try:
            with open(self.archive_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load archive, creating new: {e}")
            return self._empty_archive()

    def _save(self, data: dict) -> None:
        """아카이브 파일 저장"""
        self.archive_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.archive_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _empty_archive(self) -> dict:
        """빈 아카이브 구조"""
        today = datetime.now()
        # 이번 주 월요일 계산
        week_start = today - timedelta(days=today.weekday())
        return {
            "week_start": week_start.strftime("%Y-%m-%d"),
            "items": [],
            "sector_etf_history": {},
            "market_index_history": {},
        }

    def add_items(self, items: list[ContentItem]) -> int:
        """
        뉴스/리포트 아이템들을 아카이브에 추가 (중복 URL 제거)

        Args:
            items: ContentItem 리스트

        Returns:
            새로 추가된 아이템 수
        """
        if not items:
            return 0

        data = self._load()
        existing_urls = {item["url"] for item in data["items"]}
        added_count = 0

        for item in items:
            if item.url in existing_urls:
                continue

            archive_item = {
                "title": item.title,
                "url": item.url,
                "source": item.source or "Unknown",
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "importance_score": item.importance_score,
                "description": item.description or "",
                "content_type": item.content_type.value if isinstance(item.content_type, ContentType) else str(item.content_type),
                "archived_at": datetime.now().isoformat(),
            }

            data["items"].append(archive_item)
            existing_urls.add(item.url)
            added_count += 1

        if added_count > 0:
            self._save(data)
            logger.info(f"Weekly archive: added {added_count} items (total: {len(data['items'])})")

        return added_count

    def get_top_items(self, max_count: int = 30, content_type: Optional[str] = None) -> list[dict]:
        """
        중요도 순으로 상위 아이템 반환

        Args:
            max_count: 최대 반환 개수
            content_type: 필터할 콘텐츠 타입 ("news" 또는 "report")

        Returns:
            중요도 순 정렬된 아이템 리스트
        """
        data = self._load()
        items = data["items"]

        if content_type:
            items = [item for item in items if item.get("content_type") == content_type]

        # 중요도 순 정렬
        items.sort(key=lambda x: x.get("importance_score", 0), reverse=True)
        return items[:max_count]

    def get_items_count(self) -> int:
        """현재 아카이브 아이템 수"""
        data = self._load()
        return len(data["items"])

    def add_sector_etf_data(self, sector_etf_data: dict) -> None:
        """
        섹터 ETF 시세를 날짜별로 아카이브에 저장

        Args:
            sector_etf_data: {섹터명: SectorETFData} dict
        """
        if not sector_etf_data:
            return

        data = self._load()
        history = data.setdefault("sector_etf_history", {})
        today_key = datetime.now().strftime("%Y-%m-%d")

        # 같은 날짜에 여러 번 실행되면 마지막 값으로 덮어쓰기 (장 마감 시세가 최종)
        day_data = {}
        for sector, etf in sector_etf_data.items():
            day_data[sector] = {
                "etf_name": etf.etf_name,
                "price": etf.price,
                "change": etf.change,
                "change_percent": etf.change_percent,
                "is_up": etf.is_up,
            }

        history[today_key] = day_data
        self._save(data)
        logger.info(f"Weekly archive: saved {len(day_data)} sector ETF prices for {today_key}")

    def add_market_index_data(self, market_data) -> None:
        """
        시장 지수(코스피/코스닥/환율)를 날짜별로 아카이브에 저장

        Args:
            market_data: MarketSummary 객체
        """
        if not market_data:
            return

        data = self._load()
        history = data.setdefault("market_index_history", {})
        today_key = datetime.now().strftime("%Y-%m-%d")

        day_data = {}
        if market_data.kospi:
            day_data["kospi"] = {
                "value": market_data.kospi.value,
                "change": market_data.kospi.change,
                "change_percent": market_data.kospi.change_percent,
                "is_up": market_data.kospi.is_up,
            }
        if market_data.kosdaq:
            day_data["kosdaq"] = {
                "value": market_data.kosdaq.value,
                "change": market_data.kosdaq.change,
                "change_percent": market_data.kosdaq.change_percent,
                "is_up": market_data.kosdaq.is_up,
            }
        if market_data.usd_krw:
            day_data["usd_krw"] = {
                "value": market_data.usd_krw.value,
                "change": market_data.usd_krw.change,
                "change_percent": market_data.usd_krw.change_percent,
                "is_up": market_data.usd_krw.is_up,
            }
        if market_data.jpy_krw:
            day_data["jpy_krw"] = {
                "value": market_data.jpy_krw.value,
                "change": market_data.jpy_krw.change,
                "change_percent": market_data.jpy_krw.change_percent,
                "is_up": market_data.jpy_krw.is_up,
            }
        if market_data.eur_krw:
            day_data["eur_krw"] = {
                "value": market_data.eur_krw.value,
                "change": market_data.eur_krw.change,
                "change_percent": market_data.eur_krw.change_percent,
                "is_up": market_data.eur_krw.is_up,
            }
        if market_data.wti:
            day_data["wti"] = {
                "value": market_data.wti.value,
                "change": market_data.wti.change,
                "change_percent": market_data.wti.change_percent,
                "is_up": market_data.wti.is_up,
            }
        if market_data.gold:
            day_data["gold"] = {
                "value": market_data.gold.value,
                "change": market_data.gold.change,
                "change_percent": market_data.gold.change_percent,
                "is_up": market_data.gold.is_up,
            }

        if day_data:
            history[today_key] = day_data
            self._save(data)
            logger.info(f"Weekly archive: saved market index data for {today_key}")

    def get_market_index_history(self) -> dict:
        """
        주간 시장 지수 이력 반환

        Returns:
            {"2026-02-17": {"kospi": {...}, "kosdaq": {...}, "usd_krw": {...}}, ...}
        """
        data = self._load()
        return data.get("market_index_history", {})

    def get_sector_etf_history(self) -> dict:
        """
        주간 섹터 ETF 시세 이력 반환

        Returns:
            {"2026-02-17": {"반도체": {...}, ...}, "2026-02-18": {...}, ...}
        """
        data = self._load()
        return data.get("sector_etf_history", {})

    def get_weekly_summary(self) -> dict:
        """
        주간 시작/종료 값에서 변동률 자동 계산

        Returns:
            {
                "kospi": {"start": 2500.0, "end": 2550.0, "change": 50.0, "change_pct": 2.0},
                "kosdaq": {...},
                "usd_krw": {...},
                ...
            }
        """
        history = self.get_market_index_history()
        if not history:
            return {}

        sorted_dates = sorted(history.keys())
        if not sorted_dates:
            return {}

        index_keys = ["kospi", "kosdaq", "usd_krw", "jpy_krw", "eur_krw", "wti", "gold"]
        summary = {}

        for key in index_keys:
            first_val = None
            last_val = None
            first_date = None
            last_date = None

            for date_key in sorted_dates:
                data = history.get(date_key, {}).get(key)
                if data:
                    if first_val is None:
                        first_val = data["value"]
                        first_date = date_key
                    last_val = data["value"]
                    last_date = date_key

            if first_val is not None and last_val is not None:
                change = last_val - first_val
                change_pct = (change / first_val) * 100 if first_val else 0
                summary[key] = {
                    "start": first_val,
                    "end": last_val,
                    "start_date": first_date,
                    "end_date": last_date,
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                }

        return summary

    def reset(self) -> None:
        """주간 리뷰 생성 후 아카이브 초기화 (다음 주 준비)"""
        data = self._empty_archive()
        self._save(data)
        logger.info("Weekly archive reset for next week")


# 전역 인스턴스
weekly_archive = WeeklyNewsArchive()
