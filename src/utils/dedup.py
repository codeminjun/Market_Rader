"""
뉴스 제목 유사도 기반 중복 제거
같은 이벤트를 다른 언론사에서 보도한 경우 중복 제거
"""
import re
from difflib import SequenceMatcher

from src.collectors.base import ContentItem
from src.utils.logger import logger


def normalize_title(title: str) -> str:
    """제목 정규화: 특수문자, 공백, 언론사 태그 제거"""
    # [속보], [단독], [마켓PRO] 등 대괄호 태그 제거
    title = re.sub(r"\[.*?\]", "", title)
    # 말줄임표, 특수문자 제거
    title = re.sub(r"[…·\-=+#@!?\"'()（）<>{}|~`^*&%$,.:;]", "", title)
    # 연속 공백 정리
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _extract_keywords(title: str) -> set[str]:
    """제목에서 핵심 키워드 추출 (2글자 이상 단어)"""
    normalized = normalize_title(title)
    words = normalized.split()
    # 2글자 이상 단어만 (조사, 접속사 등 짧은 단어 제외)
    return {w for w in words if len(w) >= 2}


def _keyword_overlap(a: str, b: str) -> float:
    """두 제목의 키워드 Jaccard 유사도 (0.0 ~ 1.0)"""
    kw_a = _extract_keywords(a)
    kw_b = _extract_keywords(b)
    if not kw_a or not kw_b:
        return 0.0
    intersection = kw_a & kw_b
    union = kw_a | kw_b
    return len(intersection) / len(union)


def title_similarity(a: str, b: str) -> float:
    """
    두 제목의 유사도 계산 (0.0 ~ 1.0)
    SequenceMatcher와 키워드 오버랩 중 높은 값 사용
    """
    na = normalize_title(a)
    nb = normalize_title(b)
    if not na or not nb:
        return 0.0

    seq_sim = SequenceMatcher(None, na, nb).ratio()
    kw_sim = _keyword_overlap(a, b)

    return max(seq_sim, kw_sim)


def deduplicate_by_title(
    items: list[ContentItem],
    threshold: float = 0.55,
) -> list[ContentItem]:
    """
    제목 유사도 기반 중복 제거

    같은 이벤트를 다른 언론사에서 보도한 경우,
    중요도 점수가 가장 높은 기사만 유지합니다.

    Args:
        items: 뉴스 항목 리스트 (이미 중요도 순 정렬 가정)
        threshold: 유사도 임계값 (0.55 이상이면 중복으로 판단)

    Returns:
        중복 제거된 뉴스 리스트
    """
    if len(items) <= 1:
        return items

    unique: list[ContentItem] = []
    removed_count = 0

    for item in items:
        is_duplicate = False
        for existing in unique:
            sim = title_similarity(item.title, existing.title)
            if sim >= threshold:
                is_duplicate = True
                logger.debug(
                    f"Duplicate removed (sim={sim:.2f}): "
                    f"'{item.title[:40]}' ≈ '{existing.title[:40]}'"
                )
                removed_count += 1
                break

        if not is_duplicate:
            unique.append(item)

    if removed_count > 0:
        logger.info(f"Title dedup: removed {removed_count} duplicates from {len(items)} items")

    return unique
