"""
수집기 베이스 클래스 및 데이터 모델
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ContentType(Enum):
    """콘텐츠 유형"""
    NEWS = "news"
    REPORT = "report"
    YOUTUBE = "youtube"


class Priority(Enum):
    """우선순위"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ContentItem:
    """수집된 콘텐츠 항목"""
    id: str                          # 고유 ID (URL 해시 등)
    title: str                       # 제목
    url: str                         # 원본 URL
    source: str                      # 소스 이름 (네이버, Reuters 등)
    content_type: ContentType        # 콘텐츠 유형
    published_at: Optional[datetime] = None  # 발행일
    summary: Optional[str] = None    # 요약 (AI 생성)
    description: Optional[str] = None  # 원본 설명/내용
    priority: Priority = Priority.MEDIUM  # 우선순위
    importance_score: float = 0.5    # 중요도 점수 (0~1)
    thumbnail_url: Optional[str] = None  # 썸네일 이미지
    extra_data: dict = field(default_factory=dict)  # 추가 데이터

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "content_type": self.content_type.value,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "summary": self.summary,
            "description": self.description,
            "priority": self.priority.value,
            "importance_score": self.importance_score,
            "thumbnail_url": self.thumbnail_url,
            "extra_data": self.extra_data,
        }


class BaseCollector(ABC):
    """수집기 베이스 클래스"""

    def __init__(self, name: str, content_type: ContentType):
        self.name = name
        self.content_type = content_type

    @abstractmethod
    def collect(self) -> list[ContentItem]:
        """콘텐츠 수집"""
        pass

    def generate_id(self, url: str) -> str:
        """URL로부터 고유 ID 생성"""
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:16]
