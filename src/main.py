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
from src.collectors.base import ContentItem, ContentType
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
    create_news_list_embeds,
    create_reports_header_embed,
    create_reports_list_embed,
    create_youtube_header_embed,
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


def collect_news() -> dict:
    """뉴스 수집 (국내/해외 분리)"""
    logger.info("=== Collecting News ===")
    korean_news = []
    international_news = []

    # 1. 네이버 금융 뉴스 (국내)
    try:
        naver_collector = NaverFinanceNewsCollector(categories=["stock", "economy"])
        naver_news = naver_collector.collect()
        for item in naver_news:
            item.extra_data["region"] = "korean"
        korean_news.extend(naver_news)
        logger.info(f"Naver Finance: {len(naver_news)} items")
    except Exception as e:
        logger.error(f"Naver news collection failed: {e}")

    # 2. RSS 뉴스
    try:
        news_config = get_news_sources()
        korean_sources = news_config.get("news", {}).get("korean", [])
        intl_sources = news_config.get("news", {}).get("international", [])

        # 국내 RSS
        for source in korean_sources:
            if source.get("type") == "rss" and source.get("enabled", True):
                try:
                    collector = RSSNewsCollector(name=source["name"], url=source["url"])
                    items = collector.collect()
                    for item in items:
                        item.extra_data["region"] = "korean"
                    korean_news.extend(items)
                except Exception as e:
                    logger.warning(f"RSS collection failed for {source.get('name')}: {e}")

        # 해외 RSS
        for source in intl_sources:
            if source.get("type") == "rss" and source.get("enabled", True):
                try:
                    collector = RSSNewsCollector(name=source["name"], url=source["url"])
                    items = collector.collect()
                    for item in items:
                        item.extra_data["region"] = "international"
                    international_news.extend(items)
                except Exception as e:
                    logger.warning(f"RSS collection failed for {source.get('name')}: {e}")

    except Exception as e:
        logger.error(f"RSS news collection failed: {e}")

    # 중복 제거 (ID 기준)
    def dedupe(news_list):
        seen_ids = set()
        unique = []
        for item in news_list:
            if item.id not in seen_ids and not cache.is_sent(item.id, "news"):
                seen_ids.add(item.id)
                unique.append(item)
        return unique

    korean_news = dedupe(korean_news)
    international_news = dedupe(international_news)

    logger.info(f"Korean news: {len(korean_news)}, International: {len(international_news)}")
    return {"korean": korean_news, "international": international_news}


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


def collect_youtube() -> dict:
    """유튜브 영상 수집 (한국/해외 분리)"""
    logger.info("=== Collecting YouTube Videos ===")

    try:
        youtube_monitor = YouTubeChannelMonitor()
        videos = youtube_monitor.collect()

        # 중복 제거 (이미 전송된 영상 제외)
        korean_videos = [
            v for v in videos.get("korean", [])
            if not cache.is_sent(v.id, "youtube")
        ]
        intl_videos = [
            v for v in videos.get("international", [])
            if not cache.is_sent(v.id, "youtube")
        ]

        logger.info(f"Total new videos - Korean: {len(korean_videos)}, Intl: {len(intl_videos)}")
        return {"korean": korean_videos, "international": intl_videos}

    except Exception as e:
        logger.error(f"YouTube collection failed: {e}")
        return {"korean": [], "international": []}


def analyze_content(
    news: dict,
    reports: list[ContentItem],
    videos: dict,
) -> dict:
    """콘텐츠 분석 및 요약"""
    logger.info("=== Analyzing Content ===")

    korean_news = news.get("korean", [])
    intl_news = news.get("international", [])
    korean_videos = videos.get("korean", [])
    intl_videos = videos.get("international", [])

    result = {
        "korean_news": korean_news,
        "international_news": intl_news,
        "news_summary": None,
        "reports": reports,
        "reports_summary": None,
        "korean_videos": korean_videos,
        "international_videos": intl_videos,
        "video_summaries": {},
    }

    # 1. 국내 뉴스 중요도 평가
    if korean_news:
        scored = importance_scorer.filter_by_importance(korean_news, min_score=0.3)
        result["korean_news"] = scored[:settings.MAX_NEWS_COUNT]

    # 2. 해외 뉴스 중요도 평가
    if intl_news:
        scored = importance_scorer.filter_by_importance(intl_news, min_score=0.3)
        result["international_news"] = scored[:settings.MAX_NEWS_COUNT]

    # 3. AI 요약 (국내 + 해외 합쳐서)
    all_news = result["korean_news"] + result["international_news"]
    if all_news:
        try:
            result["news_summary"] = news_summarizer.summarize_news_batch(all_news[:15])
        except Exception as e:
            logger.warning(f"News summarization failed: {e}")

    # 4. 리포트 중요도 평가 - 중요도 높은 순
    if reports:
        scored_reports = importance_scorer.score_batch(reports)
        scored_reports.sort(key=lambda x: x.importance_score, reverse=True)
        result["reports"] = scored_reports[:settings.MAX_REPORTS_COUNT]
        logger.info(f"Reports top scores: {[f'{r.title[:20]}({r.importance_score})' for r in result['reports'][:5]]}")

        # AI 요약
        try:
            result["reports_summary"] = report_summarizer.summarize_reports(
                result["reports"][:10]
            )
        except Exception as e:
            logger.warning(f"Report summarization failed: {e}")

    # 5. 유튜브 중요도 평가 및 요약 (한국) - 중요도 높은 순
    if korean_videos:
        scored = importance_scorer.score_batch(korean_videos)
        scored.sort(key=lambda x: x.importance_score, reverse=True)
        result["korean_videos"] = scored[:5]  # 한국 5개
        logger.info(f"Korean YouTube top scores: {[f'{v.title[:20]}({v.importance_score})' for v in result['korean_videos']]}")

        for video in result["korean_videos"]:
            try:
                summary = video_summarizer.summarize_video(video)
                if summary:
                    result["video_summaries"][video.id] = summary
            except Exception as e:
                logger.warning(f"Video summarization failed for {video.title[:30]}: {e}")

    # 6. 유튜브 중요도 평가 및 요약 (해외) - 중요도 높은 순
    if intl_videos:
        scored = importance_scorer.score_batch(intl_videos)
        scored.sort(key=lambda x: x.importance_score, reverse=True)
        result["international_videos"] = scored[:5]  # 해외 5개
        logger.info(f"Intl YouTube top scores: {[f'{v.title[:20]}({v.importance_score})' for v in result['international_videos']]}")

        for video in result["international_videos"]:
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

    korean_news = analyzed.get("korean_news", [])[:10]
    intl_news = analyzed.get("international_news", [])[:10]
    all_news = korean_news + intl_news

    # 1. 헤더 (AI 요약)
    if all_news:
        header_embed = create_news_header_embed(
            date=now,
            news_count=len(all_news),
            summary=analyzed.get("news_summary"),
        )
        embeds.append(header_embed)

    # 2. 국내 뉴스 (10건)
    if korean_news:
        korean_embeds = create_news_list_embeds(
            items=korean_news,
            title=f"🇰🇷 국내 뉴스 ({len(korean_news)}건)",
            items_per_embed=5,
            color="e74c3c",
        )
        embeds.extend(korean_embeds)

    # 3. 해외 뉴스 (10건)
    if intl_news:
        intl_embeds = create_news_list_embeds(
            items=intl_news,
            title=f"🇺🇸 해외 뉴스 ({len(intl_news)}건)",
            items_per_embed=5,
            color="3498db",
        )
        embeds.extend(intl_embeds)

    # 4. 리포트 (10건)
    reports = analyzed.get("reports", [])[:10]
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

    # 5. 한국 유튜브 (5건)
    korean_videos = analyzed.get("korean_videos", [])[:5]
    video_summaries = analyzed.get("video_summaries", {})

    if korean_videos:
        korean_yt_list = create_youtube_list_embed(
            items=korean_videos,
            title=f"🇰🇷 한국 유튜브 ({len(korean_videos)}건)",
            max_items=5,
            video_summaries=video_summaries,
        )
        embeds.append(korean_yt_list)

    # 6. 해외 유튜브 (5건)
    intl_videos = analyzed.get("international_videos", [])[:5]

    if intl_videos:
        intl_yt_list = create_youtube_list_embed(
            items=intl_videos,
            title=f"🇺🇸 해외 유튜브 ({len(intl_videos)}건)",
            max_items=5,
            video_summaries=video_summaries,
        )
        embeds.append(intl_yt_list)

    all_videos = korean_videos + intl_videos

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
        cache.mark_multiple_as_sent([n.id for n in all_news], "news")
        cache.mark_multiple_as_sent([r.id for r in reports], "reports")
        cache.mark_multiple_as_sent([v.id for v in all_videos], "youtube")
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
        news = collect_news()  # {"korean": [...], "international": [...]}
        reports = collect_reports()
        videos = collect_youtube()

        # 수집된 콘텐츠가 없으면 종료
        all_news = news.get("korean", []) + news.get("international", [])
        if not all_news and not reports and not videos:
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
