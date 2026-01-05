"""
Groq API 클라이언트
Llama 모델을 사용한 AI 분석
"""
from typing import Optional
from groq import Groq

from config.settings import settings
from src.utils.logger import logger


class GroqClient:
    """Groq API 클라이언트"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self._client: Optional[Groq] = None

    @property
    def client(self) -> Groq:
        """Groq 클라이언트 (lazy initialization)"""
        if self._client is None:
            if not self.api_key:
                raise ValueError("GROQ_API_KEY is not configured")
            self._client = Groq(api_key=self.api_key)
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
            temperature: 생성 온도 (0~1)

        Returns:
            생성된 텍스트 또는 None
        """
        try:
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            if response.choices:
                return response.choices[0].message.content

            return None

        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return None

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> Optional[dict]:
        """
        JSON 형식으로 생성

        Returns:
            파싱된 JSON 또는 None
        """
        import json

        # JSON 형식 요청 추가
        json_instruction = "\n\nRespond ONLY with valid JSON, no other text."
        full_prompt = prompt + json_instruction

        result = self.generate(
            prompt=full_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=0.3,  # JSON은 낮은 temperature
        )

        if not result:
            return None

        try:
            # JSON 추출 (마크다운 코드 블록 처리)
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.startswith("```"):
                result = result[3:]
            if result.endswith("```"):
                result = result[:-3]

            return json.loads(result.strip())

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {result}")
            return None


# 전역 클라이언트 인스턴스
groq_client = GroqClient()
