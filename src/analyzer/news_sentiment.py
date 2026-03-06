"""
키워드 기반 뉴스 감성 분류기 + AI 정제
1차: 키워드로 긍정/부정 후보 추출 (빠름, API 불필요)
2차: AI가 재분류 + 중요도 순 정렬 (Gemini 1회 호출)
"""
import re
from typing import Optional

from src.collectors.base import ContentItem
from src.utils.logger import logger


# ── 부정 맥락에서의 긍정 키워드 (반전 패턴) ──
NEGATIVE_CONTEXT_PATTERNS = [
    r"(?:실업률|부채|적자|손실|부도율|물가|인플레|인플레이션|금리|이자|관세|CPI)\s*(?:가|이|도|는|은)?\s*(?:상승|증가|확대|급증|급등|폭등|치솟|높아|올라|껑충)",
    r"(?:고용|일자리|수출|매출|이익|영업이익|순이익|GDP|성장률|수요)\s*(?:가|이|도|는|은)?\s*(?:감소|급감|하락|축소|둔화|부진|위축|줄어|빠져)",
]

_NEGATIVE_CONTEXT_COMPILED = [re.compile(p, re.IGNORECASE) for p in NEGATIVE_CONTEXT_PATTERNS]


# ── 긍정 키워드 ──
POSITIVE_KEYWORDS = [
    # 시장/주가
    "상승", "호재", "신고가", "강세", "반등", "돌파", "급등", "랠리",
    "사상최고", "최고치", "회복", "반등세", "상승세", "상승랠리",
    "저점반등", "바닥확인", "매수세", "순매수",
    # 실적
    "실적개선", "호실적", "최대실적", "흑자", "흑자전환", "어닝서프라이즈",
    "실적호조", "매출증가", "영업이익증가", "순이익증가",
    # 투자/성장
    "수주", "계약", "승인", "증가", "개선", "성장", "확대", "수혜",
    "신규투자", "증설", "수요증가", "낙관", "투자확대",
    "대규모투자", "설비증설", "공장증설",
    # 리포트/목표가
    "목표가상향", "상향", "매수", "비중확대", "투자의견상향",
    # 정책/경제
    "부양책", "감세", "규제완화", "금리인하", "양적완화",
    "경기부양", "재정확대", "무역합의", "협상타결",
    # 산업
    "수출호조", "수출증가", "수출최대", "호황",
    "특허취득", "FDA승인", "임상성공", "기술이전",
    # 배당/주주환원
    "배당확대", "자사주매입", "주주환원", "배당증가",
]

# ── 부정 키워드 ──
NEGATIVE_KEYWORDS = [
    # 시장/주가
    "하락", "악재", "급락", "약세", "폭락", "하락세", "급전직하",
    "투매", "패닉", "매도세", "순매도", "하한가", "서킷브레이커",
    "사이드카", "폭풍", "붕괴", "추락",
    # 실적
    "실적부진", "실적악화", "적자", "적자전환", "적자확대",
    "어닝쇼크", "실적쇼크", "매출감소", "영업손실",
    # 경제 위기
    "파산", "부도", "워크아웃", "구조조정", "디폴트",
    "위기", "불안", "침체", "경기침체", "리세션", "스태그플레이션",
    "경착륙", "디플레이션",
    # 규제/제재
    "리콜", "제재", "규제", "과징금", "벌금", "소송", "기소",
    "수사", "압수수색", "횡령", "배임", "분식",
    "수입규제", "수출규제", "관세부과", "무역전쟁",
    # 리포트/목표가
    "목표가하향", "하향", "매도", "비중축소", "투자의견하향",
    # 감소/둔화
    "감소", "축소", "둔화", "부진", "위축", "하회", "감산",
    "수요감소", "비관", "경고", "우려",
    "급감", "급감소", "대폭감소", "수출감소",
    # 지정학
    "전쟁", "폭격", "침공", "공습", "미사일", "제재",
    "긴장", "갈등", "분쟁", "충돌", "교전",
    # 자연재해
    "지진", "태풍", "홍수", "가뭄", "산불",
    # 고용
    "해고", "정리해고", "감원", "구조조정", "일자리감소",
    # 기타
    "손실", "피해", "차질", "지연", "취소", "철회", "파기",
    "금지", "중단", "봉쇄", "차단", "격추",
    "충격", "쇼크", "피란", "대피", "발묶",
]


# 사전 컴파일된 패턴
_POSITIVE_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in POSITIVE_KEYWORDS),
    re.IGNORECASE,
)
_NEGATIVE_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in NEGATIVE_KEYWORDS),
    re.IGNORECASE,
)


def _score_sentiment(text: str) -> tuple[int, int]:
    """텍스트의 긍정/부정 키워드 매칭 수 반환 (반전 패턴 보정 포함)"""
    pos_count = len(_POSITIVE_PATTERN.findall(text))
    neg_count = len(_NEGATIVE_PATTERN.findall(text))

    # 반전 패턴 체크: "실업률 상승" 등 → 긍정에서 빼고 부정에 추가
    for pattern in _NEGATIVE_CONTEXT_COMPILED:
        reversal_matches = len(pattern.findall(text))
        if reversal_matches > 0:
            pos_count = max(0, pos_count - reversal_matches)
            neg_count += reversal_matches

    return pos_count, neg_count


def _keyword_classify(
    items: list[ContentItem],
) -> tuple[list[ContentItem], list[ContentItem], list[ContentItem]]:
    """1차: 키워드 기반 분류 → (긍정, 부정, 중립) 반환"""
    positive = []
    negative = []
    neutral = []

    for item in items:
        text = f"{item.title} {item.description or ''}"
        pos_count, neg_count = _score_sentiment(text)

        if pos_count > neg_count:
            item.extra_data["keyword_sentiment"] = "positive"
            item.extra_data["sentiment_score"] = pos_count - neg_count
            positive.append(item)
        elif neg_count > pos_count:
            item.extra_data["keyword_sentiment"] = "negative"
            item.extra_data["sentiment_score"] = neg_count - pos_count
            negative.append(item)
        else:
            item.extra_data["keyword_sentiment"] = "neutral"
            item.extra_data["sentiment_score"] = 0
            neutral.append(item)

    return positive, negative, neutral


def _ai_refine(
    candidates: list[ContentItem],
    max_positive: int = 5,
    max_negative: int = 5,
) -> Optional[tuple[list[ContentItem], list[ContentItem]]]:
    """
    2차: AI가 후보군을 재분류하고 중요도 순 정렬.
    Gemini 1회 호출.

    Returns:
        (positive_top, negative_top) 또는 실패 시 None
    """
    from src.analyzer.gemini_client import gemini_client

    if not candidates:
        return None

    # 후보 뉴스 목록 텍스트 생성
    news_list = []
    for i, item in enumerate(candidates):
        kw_sent = item.extra_data.get("keyword_sentiment", "neutral")
        news_list.append(f"[{i}] ({kw_sent}) {item.title}")

    news_text = "\n".join(news_list)

    prompt = f"""아래는 오늘의 한국 주요 뉴스 목록입니다. 각 뉴스에는 키워드 기반 1차 분류 결과(positive/negative/neutral)가 있습니다.

당신의 역할:
1. 각 뉴스를 **대한민국 증시/경제 관점**에서 긍정(positive) 또는 부정(negative)으로 재분류하세요.
2. 1차 분류가 틀린 경우 반드시 교정하세요. (예: "실업률 상승"은 부정, "일자리 감소"는 부정)
3. 증시에 직접 영향이 큰 뉴스일수록 높은 순위를 부여하세요.
4. 정치/사회 뉴스 중 증시와 무관한 것은 제외(exclude)하세요.

=== 뉴스 목록 ===
{news_text}

아래 JSON 형식으로만 응답하세요:
{{
    "positive": [{{"index": 0, "reason": "간단한 이유"}}],
    "negative": [{{"index": 1, "reason": "간단한 이유"}}]
}}

규칙:
- positive, negative 각각 최대 {max_positive}개 (중요도 순)
- index는 뉴스 번호 [0], [1] 등에서 숫자만
- 증시 무관 뉴스는 어디에도 포함하지 마세요"""

    system_prompt = "대한민국 증시 전문 애널리스트. 뉴스의 시장 영향을 정확히 판단합니다. JSON으로만 응답하세요."

    try:
        result = gemini_client.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=1024,
        )

        if not result:
            return None

        # 인덱스 → ContentItem 매핑
        idx_map = {i: item for i, item in enumerate(candidates)}

        positive_refined = []
        for entry in result.get("positive", []):
            idx = entry.get("index")
            if idx is not None and idx in idx_map:
                item = idx_map[idx]
                item.extra_data["sentiment"] = "positive"
                item.extra_data["ai_reason"] = entry.get("reason", "")
                positive_refined.append(item)

        negative_refined = []
        for entry in result.get("negative", []):
            idx = entry.get("index")
            if idx is not None and idx in idx_map:
                item = idx_map[idx]
                item.extra_data["sentiment"] = "negative"
                item.extra_data["ai_reason"] = entry.get("reason", "")
                negative_refined.append(item)

        logger.info(
            f"AI sentiment refinement: {len(positive_refined)} positive, "
            f"{len(negative_refined)} negative (from {len(candidates)} candidates)"
        )
        return positive_refined[:max_positive], negative_refined[:max_negative]

    except Exception as e:
        logger.warning(f"AI sentiment refinement failed: {e}")
        return None


def classify_sentiment(
    items: list[ContentItem],
    max_positive: int = 5,
    max_negative: int = 5,
    use_ai: bool = True,
) -> tuple[list[ContentItem], list[ContentItem]]:
    """
    뉴스를 긍정/부정으로 분류하여 각 상위 N건씩 반환.

    1차: 키워드 기반 분류 (빠름)
    2차: AI 정제 (선택, Gemini 1회 호출)

    Args:
        items: 분류할 뉴스 항목 리스트
        max_positive: 긍정 뉴스 최대 수
        max_negative: 부정 뉴스 최대 수
        use_ai: AI 정제 사용 여부

    Returns:
        (positive_top, negative_top) 튜플
    """
    # 1차: 키워드 분류
    positive_kw, negative_kw, neutral_kw = _keyword_classify(items)
    logger.info(
        f"Keyword classification: {len(positive_kw)} positive, "
        f"{len(negative_kw)} negative, {len(neutral_kw)} neutral"
    )

    # 2차: AI 정제
    if use_ai:
        # AI에게 전체 후보 전달 (키워드 분류 결과 포함)
        # 중립도 포함해야 AI가 재분류 가능
        candidates = positive_kw + negative_kw + neutral_kw
        # 너무 많으면 상위만 (중요도순)
        candidates.sort(key=lambda x: x.importance_score, reverse=True)
        candidates = candidates[:25]  # 최대 25건만 AI에 전달

        ai_result = _ai_refine(candidates, max_positive, max_negative)
        if ai_result:
            return ai_result
        logger.info("AI refinement failed, falling back to keyword-only")

    # AI 실패 또는 미사용 시: 키워드 기반 결과 사용
    for item in positive_kw:
        item.extra_data["sentiment"] = "positive"
    for item in negative_kw:
        item.extra_data["sentiment"] = "negative"

    positive_kw.sort(
        key=lambda x: (x.extra_data.get("sentiment_score", 0), x.importance_score),
        reverse=True,
    )
    negative_kw.sort(
        key=lambda x: (x.extra_data.get("sentiment_score", 0), x.importance_score),
        reverse=True,
    )

    return positive_kw[:max_positive], negative_kw[:max_negative]
