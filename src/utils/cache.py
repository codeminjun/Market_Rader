"""
캐시 관리 모듈
이미 전송한 항목 추적 (중복 방지)
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config.settings import settings
from src.utils.logger import logger


class SentItemsCache:
    """전송된 항목 캐시 관리"""

    def __init__(self, cache_file: Optional[Path] = None):
        self.cache_file = cache_file or settings.SENT_ITEMS_FILE
        self.cache: dict = self._load_cache()

    def _load_cache(self) -> dict:
        """캐시 파일 로드"""
        if not self.cache_file.exists():
            # data 디렉토리 생성
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            return {"news": [], "reports": [], "youtube": [], "last_updated": None}

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cache: {e}")
            return {"news": [], "reports": [], "youtube": [], "last_updated": None}

    def _save_cache(self) -> None:
        """캐시 파일 저장"""
        self.cache["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"Failed to save cache: {e}")

    def is_sent(self, item_id: str, category: str = "news") -> bool:
        """항목이 이미 전송되었는지 확인"""
        if category not in self.cache:
            self.cache[category] = []
        return item_id in self.cache[category]

    def mark_as_sent(self, item_id: str, category: str = "news") -> None:
        """항목을 전송됨으로 표시"""
        if category not in self.cache:
            self.cache[category] = []
        if item_id not in self.cache[category]:
            self.cache[category].append(item_id)
            self._save_cache()

    def mark_multiple_as_sent(self, item_ids: list[str], category: str = "news") -> None:
        """여러 항목을 전송됨으로 표시"""
        if category not in self.cache:
            self.cache[category] = []

        for item_id in item_ids:
            if item_id not in self.cache[category]:
                self.cache[category].append(item_id)

        self._save_cache()

    def cleanup_old_entries(self, days: int = 7) -> None:
        """오래된 캐시 항목 정리 (최근 N일 항목만 유지)"""
        # 각 카테고리당 최근 1000개 항목만 유지
        max_items = 1000

        for category in ["news", "reports", "youtube"]:
            if category in self.cache and len(self.cache[category]) > max_items:
                self.cache[category] = self.cache[category][-max_items:]

        self._save_cache()
        logger.info("Cache cleanup completed")

    def get_sent_count(self, category: str = "news") -> int:
        """전송된 항목 수 반환"""
        if category not in self.cache:
            return 0
        return len(self.cache[category])


# 전역 캐시 인스턴스
cache = SentItemsCache()
