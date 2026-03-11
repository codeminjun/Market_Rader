"""
통합 AI 뉴스 평가기
Gemini 1회 호출로 중요도 + 감성 + 긴급뉴스를 동시 평가
기존 키워드 기반 평가를 대체하지 않고, AI 결과와 블렌딩
"""
from typing import Optional

from src.collectors.base import ContentItem
from src.analyzer.gemini_client import gemini_client
from src.utils.logger import logger


SYSTEM_PROMPT = """당신은 대한민국 증시 전문 뉴스 편집장입니다.
뉴스의 실제 맥락을 정확히 파악하여 투자자에게 가치 있는 정보를 판별합니다.

핵심 원칙:
- 제목의 키워드가 아닌 실제 맥락으로 판단하세요
- "폭락 이후 반등" → 긍정 (회복세)
- "실업률 상승" → 부정 (경기 약화)
- "급등" 키워드가 있어도 이미 끝난 과거 뉴스면 중요도 낮음
- 증시에 직접 영향 없는 정치/사회 뉴스는 중요도 낮게

JSON으로만 응답하세요."""


def evaluate_batch(
    items: list[ContentItem],
    max_items: int = 20,
) -> Optional[list[dict]]:
    """
    뉴스 배치를 AI로 종합 평가 (Gemini 1회 호출)

    각 뉴스에 대해 다음을 동시 평가:
    - importance: 투자자 관점 중요도 (0.0~1.0)
    - sentiment: 한국 증시 관점 감성 (positive/negative/neutral)
    - is_breaking: 시장 급변 긴급 뉴스 여부
    - breaking_keyword: 긴급 키워드 (급등/급락/폭락/속보 등, 없으면 null)

    Args:
        items: 뉴스 항목 리스트 (키워드 사전필터 통과한 것)
        max_items: 최대 평가 항목 수

    Returns:
        [{"index": 0, "importance": 0.8, "sentiment": "positive",
          "is_breaking": false, "breaking_keyword": null}, ...]
        또는 실패 시 None
    """
    if not items:
        return None

    eval_items = items[:max_items]

    # 뉴스 목록 텍스트 생성 (제목 + 설명 포함)
    news_lines = []
    for i, item in enumerate(eval_items):
        title = item.title[:80]
        desc = (item.description or "")[:150].replace("\n", " ").strip()
        source = (item.source or "").split("(")[0].strip()[:15]

        line = f"[{i}] [{source}] {title}"
        if desc:
            line += f" | {desc}"
        news_lines.append(line)

    news_text = "\n".join(news_lines)

    prompt = f"""아래 한국 증시 관련 뉴스 {len(eval_items)}건을 평가하세요.
각 뉴스의 **실제 맥락**을 파악하여 투자자 관점에서 평가합니다.

=== 뉴스 목록 ===
{news_text}

아래 JSON 형식으로 응답하세요:
{{
    "evaluations": [
        {{
            "index": 0,
            "importance": 0.0에서 1.0 (투자 의사결정 영향도),
            "sentiment": "positive 또는 negative 또는 neutral (한국 증시 관점)",
            "is_breaking": true/false (시장 급변 긴급 뉴스인지),
            "breaking_keyword": "급등/급락/폭락/속보/충격/전쟁 중 하나 또는 null"
        }}
    ]
}}

=== 평가 기준 ===
importance:
- 0.85+: 긴급 - 즉각적 시장 영향 (서킷브레이커, 대형 M&A, 중앙은행 결정)
- 0.70~0.84: 중요 - 투자 결정 영향 (주요 기업 실적, 섹터 변동, 정책 변화)
- 0.50~0.69: 보통 - 참고 가치 (일반 업황, 리포트 요약)
- 0.50 미만: 낮음 - 배경 지식 수준

sentiment (맥락 기반 판단 필수):
- "전일 폭락에서 반등" → positive (회복세)
- "급락 후 저가매수 유입" → positive (수급 개선)
- "사상최고 기록 후 차익실현" → negative (하방 압력)
- "실업률 상승" → negative, "금리 인하" → positive
- 증시 영향 불분명 → neutral

is_breaking (진짜 긴급뉴스만):
- 서킷브레이커, 급등/급락(당일 실시간), 전쟁, 대형 사건만 true
- 이미 반영된 과거 뉴스, 분석 기사, 전망 → false
- 맥락상 긍정인데 제목에 "폭락"이 포함된 경우 → false

=== 필수 규칙 ===
1. 모든 {len(eval_items)}건에 대해 빠짐없이 평가하세요
2. index는 뉴스 번호와 정확히 일치해야 합니다
3. 키워드가 아닌 문맥으로 판단하세요
4. 배당/커버드콜 관련 뉴스는 importance를 0.65 이상으로 평가하세요"""

    try:
        result = gemini_client.generate_json(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            max_tokens=1500,
        )

        if not result or "evaluations" not in result:
            logger.warning("AI news evaluation returned invalid format")
            return None

        evaluations = result["evaluations"]

        # 기본 검증: index 범위 체크
        valid_evals = []
        for ev in evaluations:
            idx = ev.get("index")
            if idx is not None and 0 <= idx < len(eval_items):
                # 값 정규화
                ev["importance"] = max(0.0, min(1.0, float(ev.get("importance", 0.5))))
                ev["sentiment"] = ev.get("sentiment", "neutral")
                if ev["sentiment"] not in ("positive", "negative", "neutral"):
                    ev["sentiment"] = "neutral"
                ev["is_breaking"] = bool(ev.get("is_breaking", False))
                valid_evals.append(ev)

        logger.info(
            f"AI news evaluation: {len(valid_evals)}/{len(eval_items)} items evaluated, "
            f"{sum(1 for e in valid_evals if e['is_breaking'])} breaking, "
            f"{sum(1 for e in valid_evals if e['sentiment'] == 'positive')} positive, "
            f"{sum(1 for e in valid_evals if e['sentiment'] == 'negative')} negative"
        )

        return valid_evals

    except Exception as e:
        logger.error(f"AI news evaluation failed: {e}")
        return None


def apply_evaluation(
    items: list[ContentItem],
    evaluations: list[dict],
    ai_weight: float = 0.6,
) -> None:
    """
    AI 평가 결과를 뉴스 항목에 적용

    - importance: 키워드 점수(40%) + AI 점수(60%) 블렌딩
    - sentiment: AI 결과를 extra_data에 저장
    - breaking: AI 결과를 extra_data에 저장

    Args:
        items: 뉴스 항목 리스트
        evaluations: AI 평가 결과 리스트
        ai_weight: AI 점수 가중치 (0.0~1.0, 기본 0.6)
    """
    keyword_weight = 1.0 - ai_weight

    # index → evaluation 매핑
    eval_map = {ev["index"]: ev for ev in evaluations}

    for i, item in enumerate(items):
        ev = eval_map.get(i)
        if not ev:
            continue

        # 1. 중요도 블렌딩 (키워드 기반 + AI 기반)
        keyword_score = item.importance_score
        ai_score = ev["importance"]
        blended = keyword_score * keyword_weight + ai_score * ai_weight
        item.importance_score = round(max(0.0, min(1.0, blended)), 2)

        # 2. 감성 분류 저장
        item.extra_data["ai_sentiment"] = ev["sentiment"]

        # 3. 긴급뉴스 판단 저장
        if ev["is_breaking"]:
            item.extra_data["ai_breaking"] = True
            item.extra_data["is_breaking"] = True
            if ev.get("breaking_keyword"):
                item.extra_data["breaking_keyword"] = ev["breaking_keyword"]

    # 블렌딩 후 재정렬 (importance 기준)
    items.sort(key=lambda x: x.importance_score, reverse=True)
