"""
유튜브 자막 추출
youtube-transcript-api를 사용한 자막 수집
"""
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

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
        try:
            # 자막 목록 조회
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # 선호 언어로 자막 찾기
            transcript = self._find_best_transcript(transcript_list)

            if not transcript:
                logger.debug(f"No suitable transcript found for {video_id}")
                return None

            # 자막 데이터 가져오기
            transcript_data = transcript.fetch()

            # 텍스트로 변환
            full_text = self._combine_transcript(transcript_data)

            # 길이 제한
            if len(full_text) > max_length:
                full_text = full_text[:max_length] + "..."

            logger.debug(f"Extracted transcript for {video_id}: {len(full_text)} chars")
            return full_text

        except TranscriptsDisabled:
            logger.debug(f"Transcripts disabled for video {video_id}")
            return None
        except NoTranscriptFound:
            logger.debug(f"No transcript found for video {video_id}")
            return None
        except VideoUnavailable:
            logger.debug(f"Video unavailable: {video_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get transcript for {video_id}: {e}")
            return None

    def _find_best_transcript(self, transcript_list):
        """최적의 자막 찾기"""
        # 수동 생성 자막 우선
        try:
            for lang in self.PREFERRED_LANGUAGES:
                try:
                    return transcript_list.find_transcript([lang])
                except NoTranscriptFound:
                    continue
        except Exception:
            pass

        # 자동 생성 자막
        try:
            for lang in self.PREFERRED_LANGUAGES:
                try:
                    generated = transcript_list.find_generated_transcript([lang])
                    return generated
                except NoTranscriptFound:
                    continue
        except Exception:
            pass

        # 아무 자막이나 가져오기
        try:
            for transcript in transcript_list:
                return transcript
        except Exception:
            pass

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
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = self._find_best_transcript(transcript_list)

            if not transcript:
                return None

            return transcript.fetch()

        except Exception as e:
            logger.error(f"Failed to get transcript with timestamps for {video_id}: {e}")
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
