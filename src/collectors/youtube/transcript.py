"""
유튜브 자막 추출
youtube-transcript-api를 사용한 자막 수집
"""
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi

from src.utils.logger import logger


class YouTubeTranscriptExtractor:
    """유튜브 자막 추출기"""

    # 선호 언어 순서
    PREFERRED_LANGUAGES = ["ko", "en", "en-US", "en-GB"]

    def __init__(self):
        pass

    def get_transcript(
        self,
        video_id: str,
        max_length: int = 10000,
    ) -> Optional[str]:
        """
        비디오 자막 추출

        Args:
            video_id: 유튜브 비디오 ID
            max_length: 최대 텍스트 길이

        Returns:
            자막 텍스트 또는 None
        """
        # 선호 언어 순서대로 시도
        for lang in self.PREFERRED_LANGUAGES:
            try:
                transcript_data = YouTubeTranscriptApi.get_transcript(
                    video_id,
                    languages=[lang]
                )
                full_text = self._combine_transcript(transcript_data)

                if len(full_text) > max_length:
                    full_text = full_text[:max_length] + "..."

                logger.debug(f"Extracted transcript for {video_id}: {len(full_text)} chars")
                return full_text

            except Exception:
                continue

        # 기본 언어로 시도
        try:
            transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
            full_text = self._combine_transcript(transcript_data)

            if len(full_text) > max_length:
                full_text = full_text[:max_length] + "..."

            return full_text

        except Exception as e:
            logger.debug(f"No transcript available for {video_id}: {e}")
            return None

    def _combine_transcript(self, transcript_data: list) -> str:
        """자막 데이터를 텍스트로 결합"""
        texts = []
        for item in transcript_data:
            text = item.get("text", "").strip()
            if text:
                texts.append(text)

        return " ".join(texts)

    def get_transcript_with_timestamps(
        self,
        video_id: str,
    ) -> Optional[list[dict]]:
        """
        타임스탬프와 함께 자막 추출

        Returns:
            [{"start": float, "duration": float, "text": str}, ...]
        """
        for lang in self.PREFERRED_LANGUAGES:
            try:
                return YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
            except Exception:
                continue

        try:
            return YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as e:
            logger.debug(f"No transcript with timestamps for {video_id}: {e}")
            return None


# 전역 인스턴스
transcript_extractor = YouTubeTranscriptExtractor()


def extract_video_id(url: str) -> Optional[str]:
    """URL에서 비디오 ID 추출"""
    import re

    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None
