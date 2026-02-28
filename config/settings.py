"""
설정 관리 모듈
환경 변수 및 YAML 설정 파일 로드
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import yaml

# 프로젝트 루트 경로
ROOT_DIR = Path(__file__).parent.parent
CONFIG_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"

# .env 파일 로드
load_dotenv(ROOT_DIR / ".env")


class Settings:
    """애플리케이션 설정"""

    # Discord
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # Gemini API
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # NewsAPI (Optional)
    NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")

    # Naver API (Optional)
    NAVER_CLIENT_ID: str = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET: str = os.getenv("NAVER_CLIENT_SECRET", "")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # News Settings
    MAX_NEWS_COUNT: int = 20  # 충분한 뉴스 확보 (점심 15개, 아침 14+6개)
    MAX_REPORTS_COUNT: int = 15
    MAX_YOUTUBE_COUNT: int = 10

    # Cache file path
    SENT_ITEMS_FILE: Path = DATA_DIR / "sent_items.json"

    # Weekly archive file path
    WEEKLY_ARCHIVE_FILE: Path = DATA_DIR / "weekly_archive.json"

    @classmethod
    def validate(cls) -> list[str]:
        """필수 설정 검증"""
        errors = []
        if not cls.DISCORD_WEBHOOK_URL:
            errors.append("DISCORD_WEBHOOK_URL is required")
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required")
        return errors


def load_yaml_config(filename: str) -> dict:
    """YAML 설정 파일 로드"""
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_news_sources() -> dict:
    """뉴스 소스 설정 로드"""
    return load_yaml_config("news_sources.yaml")


def get_youtube_channels() -> dict:
    """유튜브 채널 설정 로드"""
    return load_yaml_config("youtube_channels.yaml")


def get_top_companies() -> dict:
    """시총 상위 50위 기업 설정 로드"""
    return load_yaml_config("top_companies.yaml")


def get_journalist_priority() -> dict:
    """우선 기자 설정 로드"""
    return load_yaml_config("journalist_priority.yaml")


# 설정 인스턴스
settings = Settings()
