"""
로깅 설정 모듈
"""
import logging
import sys
from datetime import datetime

from config.settings import settings


def setup_logger(name: str = "market_rader") -> logging.Logger:
    """로거 설정 및 반환"""
    logger = logging.getLogger(name)

    # 이미 핸들러가 설정되어 있으면 반환
    if logger.handlers:
        return logger

    # 로그 레벨 설정
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # 포맷 설정
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger


# 기본 로거 인스턴스
logger = setup_logger()


def log_execution_time(func):
    """함수 실행 시간 로깅 데코레이터"""
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        result = func(*args, **kwargs)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.debug(f"{func.__name__} executed in {duration:.2f}s")
        return result
    return wrapper
