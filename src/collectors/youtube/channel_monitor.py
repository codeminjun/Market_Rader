"""
유튜브 채널 모니터링
RSS 피드를 통한 새 영상 감지
"""
from datetime import datetime, timedelta
from typing import Optional
import feedparser
from dateutil import parser as date_parser

from src.collectors.base import BaseCollector, ContentItem, ContentType, Priority
from src.utils.logger import logger
from config.settings import get_youtube_channels


class YouTubeChannelMonitor(BaseCollector):
    """유튜브 채널 모니터링 (RSS 기반)"""

    RSS_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    def __init__(self, channels: Optional[list[dict]] = None):
        super().__init__("YouTube", ContentType.YOUTUBE)
        self.channels = channels or self._load_channels()

    def _load_channels(self) -> dict:
        """설정에서 채널 목록 로드 (지역별 분리)"""
        config = get_youtube_channels()
        channels = {"korean": [], "international": []}

        for region in ["korean", "international"]:
            if region in config:
                for channel in config[region]:
                    if channel.get("enabled", True):
                        channel["region"] = region
                        channels[region].append(channel)

        return channels

    def collect(self) -> dict:
        """모든 채널에서 새 영상 수집 (지역별 분리)"""
        korean_videos = []
        intl_videos = []

        # 한국 채널
        for channel in self.channels.get("korean", []):
            channel_items = self._collect_channel(channel)
            for item in channel_items:
                item.extra_data["region"] = "korean"
            korean_videos.extend(channel_items)

        # 해외 채널
        for channel in self.channels.get("international", []):
            channel_items = self._collect_channel(channel)
            for item in channel_items:
                item.extra_data["region"] = "international"
            intl_videos.extend(channel_items)

        # 최신순 정렬
        korean_videos.sort(key=lambda x: x.published_at or datetime.min, reverse=True)
        intl_videos.sort(key=lambda x: x.published_at or datetime.min, reverse=True)

        total = len(korean_videos) + len(intl_videos)
        logger.info(f"Collected {total} videos (Korean: {len(korean_videos)}, Intl: {len(intl_videos)})")

        return {"korean": korean_videos, "international": intl_videos}

    def _collect_channel(self, channel: dict) -> list[ContentItem]:
        """개별 채널 수집"""
        items = []
        channel_name = channel.get("name", "Unknown")
        channel_id = channel.get("channel_id", "")

        if not channel_id:
            logger.warning(f"No channel_id for {channel_name}")
            return items

        try:
            rss_url = self.RSS_URL_TEMPLATE.format(channel_id=channel_id)
            feed = feedparser.parse(rss_url)

            if feed.bozo and feed.bozo_exception:
                logger.warning(f"RSS parse warning for {channel_name}: {feed.bozo_exception}")

            # 삼프로TV는 10일 간격으로 최신 4개 스택
            is_sampro = "삼프로" in channel_name
            if is_sampro:
                cutoff_time = datetime.now() - timedelta(days=10)
                max_videos = 4
            else:
                cutoff_time = datetime.now() - timedelta(hours=48)
                max_videos = 10

            collected_count = 0
            for entry in feed.entries[:15]:
                if collected_count >= max_videos:
                    break

                item = self._parse_video_entry(entry, channel)
                if item:
                    # 최근 영상만 포함
                    if item.published_at and item.published_at.replace(tzinfo=None) > cutoff_time:
                        items.append(item)
                        collected_count += 1
                    elif not item.published_at:
                        items.append(item)
                        collected_count += 1

            logger.debug(f"Collected {len(items)} videos from {channel_name}")

        except Exception as e:
            logger.error(f"Failed to collect from {channel_name}: {e}")

        return items

    def _parse_video_entry(self, entry, channel: dict) -> Optional[ContentItem]:
        """영상 엔트리 파싱"""
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            video_id = entry.get("yt_videoid", "")

            if not title or not link:
                return None

            # 발행일 파싱
            published_at = None
            if "published" in entry:
                try:
                    published_at = date_parser.parse(entry.published)
                except (ValueError, TypeError):
                    pass

            # 썸네일
            thumbnail_url = None
            if "media_thumbnail" in entry and entry.media_thumbnail:
                thumbnail_url = entry.media_thumbnail[0].get("url")

            # 설명
            description = ""
            if "media_group" in entry:
                media_group = entry.media_group
                if "media_description" in media_group:
                    description = media_group.media_description[:500]

            # 우선순위 매핑
            priority_map = {
                "high": Priority.HIGH,
                "medium": Priority.MEDIUM,
                "low": Priority.LOW,
            }
            priority = priority_map.get(channel.get("priority", "medium"), Priority.MEDIUM)

            # 채널 정보
            channel_name = channel.get("name", "Unknown")
            channel_id = channel.get("channel_id", "")

            return ContentItem(
                id=self.generate_id(link),
                title=title,
                url=link,
                source=channel_name,
                content_type=ContentType.YOUTUBE,
                published_at=published_at,
                description=description,
                priority=priority,
                thumbnail_url=thumbnail_url,
                extra_data={
                    "video_id": video_id,
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "channel_priority": channel.get("priority", "medium"),
                },
            )

        except Exception as e:
            logger.debug(f"Failed to parse video entry: {e}")
            return None


def get_video_url(video_id: str) -> str:
    """비디오 ID로 URL 생성"""
    return f"https://www.youtube.com/watch?v={video_id}"
