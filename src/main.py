"""
Market Rader - 주식 뉴스 디스코드 봇
메인 실행 파일
"""
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings, get_news_sources, get_youtube_channels
from src.utils.logger import logger
from src.utils.cache import cache

# Collectors
from src.collectors.base import ContentItem, ContentType, Priority
from src.collectors.news import (
    NaverFinanceNewsCollector,
    RSSNewsCollector,
    create_rss_collectors,
)
from src.collectors.reports import NaverResearchCollector, SeekingAlphaCollector
from src.collectors.youtube import YouTubeChannelMonitor, transcript_extractor

# Analyzers
from src.analyzer import (
    news_summarizer,
    report_summarizer,
    video_summarizer,
    importance_scorer,
)

# Discord
from src.discord import (
    discord_sender,
    create_news_header_embed,
    create_news_list_embed,
    create_reports_header_embed,
    create_reports_list_embed,
    create_youtube_header_embed,
    create_youtube_item_embed,
    create_youtube_list_embed,
)


def validate_settings() -> bool:
    """설정 검증"""
    errors = settings.validate()
    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        return False
    return True


def collect_news() -> list[ContentItem]:
    """뉴스 수집"""
    logger.info("=== Collecting News ===")
    all_news = []

    # 1. 네이버 금융 뉴스
    try:
        naver_collector = NaverFinanceNewsCollector(categories=["stock", "economy"])
        naver_news = naver_collector.collect()
        all_news.extend(naver_news)
        logger.info(f"Naver Finance: {len(naver_news)} items")
    except Exception as e:
        logger.error(f"Naver news collection failed: {e}")

    # 2. RSS 뉴스
    try:
        news_config = get_news_sources()
        korean_sources = news_config.get("news", {}).get("korean", [])
        intl_sources = news_config.get("news", {}).get("international", [])

        for source in korean_sources + intl_sources:
            if source.get("type") == "rss" and source.get("enabled", True):
                try:
                    collector = RSSNewsCollector(
                        name=source["name"],
                        url=source["url"],
                    )
                    items = collector.collect()
                    all_news.extend(items)
                except Exception as e:
                    logger.warning(f"RSS collection failed for {source.get('name')}: {e}")

    except Exception as e:
        logger.error(f"RSS news collection failed: {e}")

    # 중복 제거 (ID 기준)
    seen_ids = set()
    unique_news = []
    for item in all_news:
        if item.id not in seen_ids and not cache.is_sent(item.id, "news"):
            seen_ids.add(item.id)
            unique_news.append(item)

    logger.info(f"Total unique news: {len(unique_news)}")
    return unique_news


def collect_reports() -> list[ContentItem]:
    """애널리스트 리포트 수집"""
    logger.info("=== Collecting Reports ===")
    all_reports = []

    # 1. 네이버 증권 리서치
    try:
        naver_research = NaverResearchCollector(categories=["invest", "company", "market"])
        reports = naver_research.collect()
        all_reports.extend(reports)
        logger.info(f"Naver Research: {len(reports)} items")
    except Exception as e:
        logger.error(f"Naver research collection failed: {e}")

    # 2. Seeking Alpha
    try:
        sa_collector = SeekingAlphaCollector()
        sa_reports = sa_collector.collect()
        all_reports.extend(sa_reports)
        logger.info(f"Seeking Alpha: {len(sa_reports)} items")
    except Exception as e:
        logger.warning(f"Seeking Alpha collection failed: {e}")

    # 중복 제거
    seen_ids = set()
    unique_reports = []
    for item in all_reports:
        if item.id not in seen_ids and not cache.is_sent(item.id, "reports"):
            seen_ids.add(item.id)
            unique_reports.append(item)

    logger.info(f"Total unique reports: {len(unique_reports)}")
    return unique_reports


def collect_youtube() -> list[ContentItem]:
    """유튜브 영상 수집"""
    logger.info("=== Collecting YouTube Videos ===")

    try:
        youtube_monitor = YouTubeChannelMonitor()
        videos = youtube_monitor.collect()

        # 중복 제거 (이미 전송된 영상 제외)
        unique_videos = [
            v for v in videos
            if not cache.is_sent(v.id, "youtube")
        ]

        logger.info(f"Total new videos: {len(unique_videos)}")
        return unique_videos

    except Exception as e:
        logger.error(f"YouTube collection failed: {e}")
        return []


def analyze_content(
    news: list[ContentItem],
    reports: list[ContentItem],
    videos: list[ContentItem],
) -> dict:
    """콘텐츠 분석 및 요약"""
    logger.info("=== Analyzing Content ===")

    result = {
        "news": news,
        "news_summary": None,
        "reports": reports,
        "reports_summary": None,
        "videos": videos,
        "video_summaries": {},
    }

    # 1. 뉴스 중요도 평가 및 필터링
    if news:
        scored_news = importance_scorer.filter_by_importance(news, min_score=0.3)
        result["news"] = scored_news[:settings.MAX_NEWS_COUNT]

        # AI 요약
        try:
            result["news_summary"] = news_summarizer.summarize_news_batch(
                result["news"][:15]
            )
        except Exception as e:
            logger.warning(f"News summarization failed: {e}")

    # 2. 리포트 중요도 평가
    if reports:
        scored_reports = importance_scorer.score_batch(reports)
        scored_reports.sort(key=lambda x: x.importance_score, reverse=True)
        result["reports"] = scored_reports[:settings.MAX_REPORTS_COUNT]

        # AI 요약
        try:
            result["reports_summary"] = report_summarizer.summarize_reports(
                result["reports"][:10]
            )
        except Exception as e:
            logger.warning(f"Report summarization failed: {e}")

    # 3. 유튜브 중요도 평가 및 요약
    if videos:
        scored_videos = importance_scorer.score_batch(videos)
        scored_videos.sort(key=lambda x: (x.priority.value, -x.importance_score))
        result["videos"] = scored_videos[:settings.MAX_YOUTUBE_COUNT]

        # 높은 우선순위 영상만 자막 요약
        for video in result["videos"]:
            if video.priority == Priority.HIGH:
                try:
                    summary = video_summarizer.summarize_video(video)
                    if summary:
                        result["video_summaries"][video.id] = summary
                except Exception as e:
                    logger.warning(f"Video summarization failed for {video.title[:30]}: {e}")

    return result


def send_to_discord(analyzed: dict) -> bool:
    """Discord로 전송"""
    logger.info("=== Sending to Discord ===")

    embeds = []
    now = datetime.now()

    # 1. 뉴스 섹션
    news = analyzed.get("news", [])
    if news:
        # 헤더 Embed
        header_embed = create_news_header_embed(
            date=now,
            news_count=len(news),
            summary=analyzed.get("news_summary"),
        )
        embeds.append(header_embed)

        # 뉴스 목록 Embed
        news_list_embed = create_news_list_embed(
            items=news,
            title="🇰🇷 국내 뉴스" if any("네이버" in n.source or "한국" in n.source for n in news) else "📰 주요 뉴스",
            max_items=15,
        )
        embeds.append(news_list_embed)

    # 2. 리포트 섹션
    reports = analyzed.get("reports", [])
    if reports:
        reports_header = create_reports_header_embed(
            report_count=len(reports),
            summary=analyzed.get("reports_summary"),
        )
        embeds.append(reports_header)

        reports_list = create_reports_list_embed(
            items=reports,
            max_items=10,
        )
        embeds.append(reports_list)

    # 3. 유튜브 섹션
    videos = analyzed.get("videos", [])
    video_summaries = analyzed.get("video_summaries", {})

    if videos:
        youtube_header = create_youtube_header_embed(len(videos))
        embeds.append(youtube_header)

        # 높은 우선순위 영상은 개별 Embed
        high_priority_videos = [v for v in videos if v.priority == Priority.HIGH]
        other_videos = [v for v in videos if v.priority != Priority.HIGH]

        for video in high_priority_videos[:3]:
            summary = video_summaries.get(video.id)
            video_embed = create_youtube_item_embed(video, summary=summary)
            embeds.append(video_embed)

        # 나머지는 목록으로
        if other_videos:
            other_list = create_youtube_list_embed(
                items=other_videos,
                title="📺 기타 새 영상",
                max_items=7,
            )
            embeds.append(other_list)

    # Discord로 전송
    if not embeds:
        logger.info("No content to send")
        return True

    success = discord_sender.send_multiple_embeds(
        embeds=embeds,
        username="Market Rader 📈",
    )

    if success:
        # 캐시에 전송된 항목 기록
        cache.mark_multiple_as_sent([n.id for n in news], "news")
        cache.mark_multiple_as_sent([r.id for r in reports], "reports")
        cache.mark_multiple_as_sent([v.id for v in videos], "youtube")
        logger.info(f"Successfully sent {len(embeds)} embeds to Discord")
    else:
        logger.error("Failed to send to Discord")

    return success


def main():
    """메인 실행 함수"""
    logger.info("=" * 50)
    logger.info("Market Rader Starting...")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    # 설정 검증
    if not validate_settings():
        logger.error("Configuration validation failed. Exiting.")
        sys.exit(1)

    try:
        # 1. 콘텐츠 수집
        news = collect_news()
        reports = collect_reports()
        videos = collect_youtube()

        # 수집된 콘텐츠가 없으면 종료
        if not news and not reports and not videos:
            logger.info("No new content collected. Exiting.")
            return

        # 2. 분석 및 요약
        analyzed = analyze_content(news, reports, videos)

        # 3. Discord 전송
        success = send_to_discord(analyzed)

        # 4. 캐시 정리
        cache.cleanup_old_entries(days=7)

        if success:
            logger.info("Market Rader completed successfully!")
        else:
            logger.warning("Market Rader completed with some errors")

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
