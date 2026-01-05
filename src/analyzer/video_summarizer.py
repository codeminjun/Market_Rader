"""
유튜브 영상 요약 모듈
자막 기반 AI 요약
"""
from typing import Optional

from src.collectors.base import ContentItem
from src.collectors.youtube.transcript import transcript_extractor, extract_video_id
from src.analyzer.groq_client import groq_client
from src.utils.logger import logger


class VideoSummarizer:
    """유튜브 영상 요약기"""

    SYSTEM_PROMPT = """당신은 금융/경제 콘텐츠 전문가입니다.
유튜브 영상의 자막을 분석하여 핵심 내용을 요약합니다.
응답은 항상 한국어로 작성합니다."""

    def __init__(self):
        self.client = groq_client
        self.transcript_extractor = transcript_extractor

    def summarize_video(
        self,
        item: ContentItem,
        max_transcript_length: int = 8000,
    ) -> Optional[dict]:
        """
        영상 요약

        Args:
            item: 유튜브 영상 항목
            max_transcript_length: 최대 자막 길이

        Returns:
            {
                "summary": "영상 요약",
                "key_points": ["핵심 포인트 1", ...],
                "investment_relevance": "투자 관련성"
            }
        """
        # 비디오 ID 추출
        video_id = item.extra_data.get("video_id")
        if not video_id:
            video_id = extract_video_id(item.url)

        if not video_id:
            logger.warning(f"Could not extract video ID from {item.url}")
            return None

        # 자막 추출
        transcript = self.transcript_extractor.get_transcript(
            video_id,
            max_length=max_transcript_length,
        )

        if not transcript:
            logger.debug(f"No transcript available for video: {item.title}")
            # 자막이 없으면 제목/설명 기반으로 간단 요약
            return self._summarize_from_metadata(item)

        # AI 요약
        return self._summarize_transcript(item, transcript)

    def _summarize_transcript(
        self,
        item: ContentItem,
        transcript: str,
    ) -> Optional[dict]:
        """자막 기반 요약"""
        prompt = f"""다음은 금융/경제 유튜브 영상의 정보와 자막입니다:

채널: {item.source}
제목: {item.title}
설명: {item.description or '없음'}

자막 내용:
{transcript[:6000]}

위 영상의 내용을 분석하여 다음 JSON 형식으로 응답해주세요:
{{
    "summary": "영상의 핵심 내용을 3-4문장으로 요약",
    "key_points": ["핵심 포인트 1", "핵심 포인트 2", "핵심 포인트 3"],
    "investment_relevance": "이 영상이 투자에 어떤 시사점을 주는지 1-2문장으로 설명"
}}"""

        result = self.client.generate_json(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=800,
        )

        if result:
            logger.info(f"Video summary generated for: {item.title[:50]}")

        return result

    def _summarize_from_metadata(
        self,
        item: ContentItem,
    ) -> Optional[dict]:
        """메타데이터 기반 간단 요약 (자막 없을 때)"""
        if not item.title:
            return None

        prompt = f"""다음 금융/경제 유튜브 영상의 제목과 설명을 보고 간단히 분석해주세요:

채널: {item.source}
제목: {item.title}
설명: {item.description or '없음'}

다음 JSON 형식으로 응답해주세요:
{{
    "summary": "제목과 설명을 바탕으로 예상되는 영상 내용 1-2문장",
    "key_points": ["예상 핵심 주제"],
    "investment_relevance": "투자자에게 어떤 정보를 제공할 것으로 예상되는지"
}}"""

        result = self.client.generate_json(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=500,
        )

        return result

    def quick_summary(
        self,
        item: ContentItem,
    ) -> Optional[str]:
        """
        빠른 요약 (제목/설명 기반, 자막 없이)

        Returns:
            간단한 요약 문자열
        """
        prompt = f"""다음 금융/경제 유튜브 영상을 한 문장으로 요약해주세요:

채널: {item.source}
제목: {item.title}
설명: {item.description[:300] if item.description else '없음'}

한 문장 요약:"""

        result = self.client.generate(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=150,
            temperature=0.5,
        )

        return result


# 전역 인스턴스
video_summarizer = VideoSummarizer()
