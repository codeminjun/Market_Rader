"""
중요도 점수 판단 모듈
AI 기반 콘텐츠 중요도 평가
"""
from typing import Optional

from src.collectors.base import ContentItem, Priority
from src.analyzer.groq_client import groq_client
from src.utils.logger import logger
from config.settings import get_news_sources


class ImportanceScorer:
    """콘텐츠 중요도 평가기"""

    SYSTEM_PROMPT = """당신은 금융 뉴스 편집자입니다.
뉴스와 콘텐츠의 투자 관련 중요도를 평가합니다.
객관적이고 일관된 기준으로 평가합니다."""

    # 중요 키워드 (설정에서 로드)
    HIGH_IMPORTANCE_KEYWORDS = [
        "금리", "FOMC", "연준", "Fed", "기준금리",
        "실적발표", "어닝", "IPO", "상장",
        "인수", "합병", "M&A",
        "파산", "부도", "긴급",
        "급등", "급락", "폭락", "폭등",
    ]

    MEDIUM_IMPORTANCE_KEYWORDS = [
        "전망", "분석", "목표가", "투자의견",
        "매수", "매도", "상향", "하향",
        "실적", "배당", "자사주",
    ]

    def __init__(self):
        self.client = groq_client
        self._load_keywords_from_config()

    def _load_keywords_from_config(self):
        """설정에서 키워드 로드"""
        try:
            config = get_news_sources()
            keywords = config.get("important_keywords", {})

            if "high" in keywords:
                self.HIGH_IMPORTANCE_KEYWORDS.extend(keywords["high"])
            if "medium" in keywords:
                self.MEDIUM_IMPORTANCE_KEYWORDS.extend(keywords["medium"])

        except Exception as e:
            logger.debug(f"Could not load keywords from config: {e}")

    def score_item(self, item: ContentItem) -> float:
        """
        단일 항목 중요도 점수 계산

        Args:
            item: 콘텐츠 항목

        Returns:
            중요도 점수 (0.0 ~ 1.0)
        """
        score = 0.5  # 기본 점수

        # 키워드 기반 점수 조정
        text = f"{item.title} {item.description or ''}"
        text_lower = text.lower()

        for keyword in self.HIGH_IMPORTANCE_KEYWORDS:
            if keyword.lower() in text_lower:
                score += 0.15
                break  # 하나만 매칭되어도 점수 부여

        for keyword in self.MEDIUM_IMPORTANCE_KEYWORDS:
            if keyword.lower() in text_lower:
                score += 0.08
                break

        # 우선순위 기반 조정
        if item.priority == Priority.HIGH:
            score += 0.1
        elif item.priority == Priority.LOW:
            score -= 0.1

        # 점수 범위 제한
        score = max(0.0, min(1.0, score))

        return round(score, 2)

    def score_batch(self, items: list[ContentItem]) -> list[ContentItem]:
        """
        배치 중요도 점수 계산

        Args:
            items: 콘텐츠 항목 리스트

        Returns:
            점수가 업데이트된 항목 리스트
        """
        for item in items:
            item.importance_score = self.score_item(item)

            # 점수에 따라 우선순위 업데이트
            if item.importance_score >= 0.7:
                item.priority = Priority.HIGH
            elif item.importance_score >= 0.5:
                item.priority = Priority.MEDIUM
            else:
                item.priority = Priority.LOW

        return items

    def ai_score_item(self, item: ContentItem) -> Optional[dict]:
        """
        AI 기반 상세 중요도 평가

        Returns:
            {
                "score": 0.0-1.0,
                "reason": "평가 이유",
                "category": "긴급/중요/일반/참고"
            }
        """
        prompt = f"""다음 금융 뉴스/콘텐츠의 투자자 관점 중요도를 평가해주세요:

제목: {item.title}
출처: {item.source}
내용: {item.description[:500] if item.description else '없음'}

다음 JSON 형식으로 응답해주세요:
{{
    "score": 0.0에서 1.0 사이의 중요도 점수 (숫자만),
    "reason": "이 점수를 부여한 이유 (1문장)",
    "category": "긴급/중요/일반/참고 중 하나"
}}

평가 기준:
- 0.8 이상: 긴급 - 즉각적인 시장 영향 예상
- 0.6-0.8: 중요 - 투자 결정에 영향을 줄 수 있음
- 0.4-0.6: 일반 - 참고할 만한 정보
- 0.4 미만: 참고 - 배경 지식 수준"""

        result = self.client.generate_json(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=300,
        )

        return result

    def filter_by_importance(
        self,
        items: list[ContentItem],
        min_score: float = 0.4,
    ) -> list[ContentItem]:
        """
        중요도 기준 필터링

        Args:
            items: 콘텐츠 항목 리스트
            min_score: 최소 중요도 점수

        Returns:
            필터링된 항목 리스트
        """
        # 점수 계산
        scored_items = self.score_batch(items)

        # 필터링 및 정렬
        filtered = [item for item in scored_items if item.importance_score >= min_score]
        filtered.sort(key=lambda x: x.importance_score, reverse=True)

        logger.info(f"Filtered {len(filtered)}/{len(items)} items by importance (min: {min_score})")

        return filtered


# 전역 인스턴스
importance_scorer = ImportanceScorer()
