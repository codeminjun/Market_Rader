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

    # Groq API
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = "llama-3.1-70b-versatile"

    # NewsAPI (Optional)
    NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")

    # Naver API (Optional)
    NAVER_CLIENT_ID: str = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET: str = os.getenv("NAVER_CLIENT_SECRET", "")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # News Settings
    MAX_NEWS_COUNT: int = 20
    MAX_REPORTS_COUNT: int = 10
    MAX_YOUTUBE_COUNT: int = 10

    # Cache file path
    SENT_ITEMS_FILE: Path = DATA_DIR / "sent_items.json"

    @classmethod
    def validate(cls) -> list[str]:
        """필수 설정 검증"""
        errors = []
        if not cls.DISCORD_WEBHOOK_URL:
            errors.append("DISCORD_WEBHOOK_URL is required")
        if not cls.GROQ_API_KEY:
            errors.append("GROQ_API_KEY is required")
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


# 설정 인스턴스
settings = Settings()
