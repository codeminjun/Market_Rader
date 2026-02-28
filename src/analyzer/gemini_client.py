"""
Google Gemini API 클라이언트
Gemini 2.5 Flash 모델을 사용한 AI 분석
"""
import json
from typing import Optional

from google import genai
from google.genai import types

from config.settings import settings
from src.utils.logger import logger


class GeminiClient:
    """Gemini API 클라이언트"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        """Gemini 클라이언트 (lazy initialization)"""
        if self._client is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not configured")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

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

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )

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

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )

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
