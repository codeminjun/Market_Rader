"""
오전 시그널 캐시
점심 브리핑에서 오전 예측 vs 실제 비교용
"""
import json
from datetime import datetime
from pathlib import Path

from src.utils.logger import logger

CACHE_FILE = Path("data/morning_signal.json")


def save_morning_signal(signal_data: dict) -> None:
    """오전 시그널 결과를 캐시에 저장"""
    try:
        cache = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "overall_signal": signal_data.get("overall_signal"),
            "signal_strength": signal_data.get("signal_strength"),
            "market_sentiment": signal_data.get("market_sentiment"),
            "saved_at": datetime.now().isoformat(),
        }
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        logger.info(f"Morning signal cached: {cache['overall_signal']}")
    except Exception as e:
        logger.warning(f"Failed to save morning signal cache: {e}")


def load_morning_signal() -> dict | None:
    """오늘의 오전 시그널 로드"""
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        today = datetime.now().strftime("%Y-%m-%d")
        if cache.get("date") != today:
            logger.info("Morning signal cache is from a different day, ignoring")
            return None
        logger.info(f"Loaded morning signal: {cache.get('overall_signal')}")
        return cache
    except Exception as e:
        logger.warning(f"Failed to load morning signal cache: {e}")
        return None


def evaluate_prediction_accuracy(
    morning_signal: dict,
    kospi_change_percent: float,
) -> dict:
    """
    오전 예측 vs 실제 비교

    Returns:
        {
            "result": "적중/불일치/부분적중",
            "emoji": "✅/❌/⚠️",
            "comment": "설명 텍스트",
        }
    """
    predicted = morning_signal.get("overall_signal", "neutral")
    strength = morning_signal.get("signal_strength", 0.5)

    # 예측 방향
    if predicted in ("strong_bullish", "bullish"):
        predicted_dir = "up"
    elif predicted in ("strong_bearish", "bearish"):
        predicted_dir = "down"
    else:
        predicted_dir = "flat"

    # 실제 방향
    if kospi_change_percent > 0.5:
        actual_dir = "up"
    elif kospi_change_percent < -0.5:
        actual_dir = "down"
    else:
        actual_dir = "flat"

    # 판정
    if predicted_dir == actual_dir:
        return {
            "result": "적중",
            "emoji": "✅",
            "comment": f"오전 예측({_signal_kr(predicted)} {int(strength*100)}%)이 적중했어요",
        }
    elif (predicted_dir == "up" and actual_dir == "down") or (predicted_dir == "down" and actual_dir == "up"):
        return {
            "result": "불일치",
            "emoji": "❌",
            "comment": f"오전 예측({_signal_kr(predicted)} {int(strength*100)}%)과 실제 방향이 달라요",
        }
    else:
        return {
            "result": "부분적중",
            "emoji": "⚠️",
            "comment": f"오전 예측({_signal_kr(predicted)} {int(strength*100)}%) 대비 실제는 혼조세예요",
        }


def _signal_kr(signal: str) -> str:
    """시그널 한글 변환"""
    return {
        "strong_bullish": "강한 상승",
        "bullish": "상승",
        "neutral": "중립",
        "bearish": "하락",
        "strong_bearish": "강한 하락",
    }.get(signal, "중립")
