"""
Google Gemini API 클라이언트
Gemini 2.5 Flash 모델을 사용한 AI 분석
"""
import json
import re
import time
from typing import Optional

from google import genai
from google.genai import types

from config.settings import settings
from src.utils.logger import logger

# Rate limit 상수
MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 15  # 기본 재시도 대기 (초)
MIN_REQUEST_INTERVAL = 13  # 요청 간 최소 간격 (초) - 분당 5회 한도 대비


class GeminiClient:
    """Gemini API 클라이언트 (Rate limit 자동 재시도 포함)"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self._client: Optional[genai.Client] = None
        self._last_request_time: float = 0

    @property
    def client(self) -> genai.Client:
        """Gemini 클라이언트 (lazy initialization)"""
        if self._client is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not configured")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _throttle(self) -> None:
        """분당 요청 한도를 초과하지 않도록 요청 간격 조절"""
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            wait = MIN_REQUEST_INTERVAL - elapsed
            logger.debug(f"Rate limit throttle: waiting {wait:.1f}s")
            time.sleep(wait)

    @staticmethod
    def _parse_retry_delay(error: Exception) -> Optional[float]:
        """429 에러에서 권장 재시도 대기 시간 추출"""
        error_str = str(error)
        # "retryDelay": "32s" 또는 "Please retry in 32.156942909s" 패턴
        match = re.search(r'retry.*?(\d+\.?\d*)\s*s', error_str, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None

    @staticmethod
    def _is_rate_limit_error(error: Exception) -> bool:
        """429 Rate limit 에러 여부 확인"""
        error_str = str(error)
        return "429" in error_str or "RESOURCE_EXHAUSTED" in error_str

    def _call_with_retry(self, config: types.GenerateContentConfig, prompt: str):
        """API 호출 + rate limit 자동 재시도"""
        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            try:
                self._last_request_time = time.time()
                return self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
            except Exception as e:
                if not self._is_rate_limit_error(e):
                    raise

                if attempt >= MAX_RETRIES:
                    logger.error(f"Gemini API rate limit: {MAX_RETRIES}회 재시도 모두 실패")
                    raise

                delay = self._parse_retry_delay(e) or DEFAULT_RETRY_DELAY * (attempt + 1)
                logger.warning(f"Gemini API rate limit (429). {delay:.0f}초 후 재시도 ({attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> Optional[str]:
        """
        텍스트 생성

        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트
            max_tokens: 최대 토큰 수
            temperature: 생성 온도 (0~2)

        Returns:
            생성된 텍스트 또는 None
        """
        try:
            config = types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )

            if system_prompt:
                config.system_instruction = system_prompt

            response = self._call_with_retry(config, prompt)

            if response.text:
                return response.text

            return None

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> Optional[dict]:
        """
        JSON 형식으로 생성 (Gemini 네이티브 JSON 모드)

        Returns:
            파싱된 JSON 또는 None
        """
        try:
            config = types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.3,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )

            if system_prompt:
                config.system_instruction = system_prompt

            response = self._call_with_retry(config, prompt)

            if not response.text:
                return None

            return json.loads(response.text)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {response.text}")
            return None
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None


# 전역 클라이언트 인스턴스
gemini_client = GeminiClient()
