"""
Market Rader - 주식 뉴스 디스코드 봇
메인 실행 파일
"""
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    InvestingNewsCollector,
)
from src.collectors.reports import NaverResearchCollector, SeekingAlphaCollector, MorningBriefCollector
from src.collectors.youtube import YouTubeChannelMonitor, transcript_extractor
from src.collectors.market import market_data_collector

# Analyzers
from src.analyzer import (
    news_summarizer,
    report_summarizer,
    video_summarizer,
    importance_scorer,
    morning_brief_summarizer,
    market_signal_analyzer,
    report_analyzer,
    market_briefing_generator,
)
from src.analyzer.briefing_validator import briefing_validator

# Discord
from src.discord import (
    discord_sender,
    create_news_header_embed,
    create_news_list_embeds,
    create_market_signal_embed,
    create_breaking_news_embed,
    create_reports_header_embed,
    create_reports_list_embed,
    create_youtube_header_embed,
    create_youtube_list_embed,
    create_morning_brief_embed,
    create_market_close_embed,
    create_closing_review_embed,
    create_morning_strategy_embed,
)
from src.discord.embeds.report_embed import create_reports_with_analysis_embeds


def validate_settings() -> bool:
    """설정 검증"""
    errors = settings.validate()
    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        return False
    return True


def collect_news() -> dict:
    """뉴스 수집 (국내/해외 분리, 병렬 처리)"""
    from src.utils.constants import get_priority_from_string

    logger.info("=== Collecting News (Parallel) ===")
    korean_news = []
    international_news = []

    # 수집 태스크 정의
    def collect_naver():
        """네이버 금융 뉴스"""
        collector = NaverFinanceNewsCollector(categories=["stock", "economy"])
        items = collector.collect()
        for item in items:
            item.extra_data["region"] = "korean"
        return ("korean", items, "Naver Finance")

    def collect_investing():
        """인베스팅닷컴 인기 뉴스 (현재 차단됨 - 비활성화)"""
        # 인베스팅닷컴이 봇 차단 중이므로 빈 리스트 반환
        # TODO: 다른 인기 뉴스 소스로 대체 필요
        return ("korean", [], "Investing.com (disabled)")

    def collect_rss(source: dict, region: str):
        """RSS 뉴스 수집"""
        priority = get_priority_from_string(source.get("priority", "medium"))
        collector = RSSNewsCollector(
            name=source["name"],
            url=source["url"],
            priority=priority,
        )
        items = collector.collect()
        for item in items:
            item.extra_data["region"] = region
        return (region, items, source["name"])

    # RSS 소스 로드
    news_config = get_news_sources()
    korean_sources = news_config.get("news", {}).get("korean", [])
    intl_sources = news_config.get("news", {}).get("international", [])

    # 모든 수집 태스크 병렬 실행
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = []

        # 기본 수집기
        futures.append(executor.submit(collect_naver))
        futures.append(executor.submit(collect_investing))

        # RSS 수집기들
        for source in korean_sources:
            if source.get("type") == "rss" and source.get("enabled", True):
                futures.append(executor.submit(collect_rss, source, "korean"))

        for source in intl_sources:
            if source.get("type") == "rss" and source.get("enabled", True):
                futures.append(executor.submit(collect_rss, source, "international"))

        # 결과 수집
        for future in as_completed(futures):
            try:
                region, items, source_name = future.result()
                if region == "korean":
                    korean_news.extend(items)
                else:
                    international_news.extend(items)
                logger.info(f"{source_name}: {len(items)} items")
            except Exception as e:
                logger.error(f"News collection failed: {e}")

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


def collect_reports(extract_pdf: bool = False) -> list[ContentItem]:
    """애널리스트 리포트 수집 (병렬 처리)

    Args:
        extract_pdf: PDF 텍스트 추출 여부 (오전 스케줄에서만 True)
    """
    logger.info("=== Collecting Reports (Parallel) ===")
    all_reports = []

    def collect_naver_research():
        """네이버 증권 리서치"""
        collector = NaverResearchCollector(
            categories=["invest", "company", "market"],
            extract_pdf=extract_pdf,
            max_pdf_extract=5,  # 상위 5개만 PDF 추출
        )
        return collector.collect()

    def collect_seeking_alpha():
        """Seeking Alpha"""
        collector = SeekingAlphaCollector()
        return collector.collect()

    # 병렬 수집
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(collect_naver_research): "Naver Research",
            executor.submit(collect_seeking_alpha): "Seeking Alpha",
        }

        for future in as_completed(futures):
            source_name = futures[future]
            try:
                reports = future.result()
                all_reports.extend(reports)
                logger.info(f"{source_name}: {len(reports)} items")
            except Exception as e:
                logger.error(f"{source_name} collection failed: {e}")

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


def collect_morning_briefs() -> list[ContentItem]:
    """Morning Brief 수집 (오전 스케줄 전용)"""
    logger.info("=== Collecting Morning Briefs ===")

    try:
        collector = MorningBriefCollector(max_briefs=3)
        briefs = collector.collect()

        # 중복 제거
        unique_briefs = [
            b for b in briefs
            if not cache.is_sent(b.id, "morning_brief")
        ]

        logger.info(f"Collected {len(unique_briefs)} Morning Briefs")
        return unique_briefs

    except Exception as e:
        logger.error(f"Morning Brief collection failed: {e}")
        return []


def analyze_content(
    news: dict,
    reports: list[ContentItem],
    videos: dict,
    morning_briefs: list[ContentItem] = None,
) -> dict:
    """콘텐츠 분석 및 요약"""
    logger.info("=== Analyzing Content ===")

    korean_news = news.get("korean", [])
    intl_news = news.get("international", [])
    korean_videos = videos.get("korean", [])
    intl_videos = videos.get("international", [])
    morning_briefs = morning_briefs or []

    result = {
        "korean_news": korean_news,
        "international_news": intl_news,
        "news_summary": None,
        "market_signal": None,
        "breaking_news": [],
        "sector_news": {},
        "reports": reports,
        "reports_summary": None,
        "korean_videos": korean_videos,
        "international_videos": intl_videos,
        "video_summaries": {},
        "morning_briefs": morning_briefs,
        "morning_brief_summary": None,
    }

    # 0. Morning Brief 요약 (있는 경우)
    if morning_briefs:
        try:
            result["morning_brief_summary"] = morning_brief_summarizer.summarize_multiple_briefs(
                morning_briefs
            )
            logger.info(f"Morning Brief summary generated from {len(morning_briefs)} briefs")
        except Exception as e:
            logger.warning(f"Morning Brief summarization failed: {e}")

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

        # 3-1. 시장 시그널 분석 (AI)
        try:
            result["market_signal"] = market_signal_analyzer.analyze_news_batch(all_news[:15])
            if result["market_signal"]:
                logger.info(f"Market signal: {result['market_signal'].get('overall_signal')}")
        except Exception as e:
            logger.warning(f"Market signal analysis failed: {e}")

        # 3-2. 긴급 뉴스 감지
        try:
            result["breaking_news"] = market_signal_analyzer.detect_breaking_news(all_news)
        except Exception as e:
            logger.warning(f"Breaking news detection failed: {e}")

        # 3-3. 섹터별 분류
        try:
            result["sector_news"] = market_signal_analyzer.categorize_by_sector(all_news)
        except Exception as e:
            logger.warning(f"Sector categorization failed: {e}")

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

        # 4-1. 개별 리포트 AI 분석 (PDF 추출된 것만)
        pdf_reports = [r for r in result["reports"] if r.extra_data.get("pdf_text")]
        if pdf_reports:
            try:
                report_analyzer.analyze_batch(pdf_reports, max_items=5)
                analyzed_count = sum(1 for r in pdf_reports if r.extra_data.get("ai_analysis"))
                logger.info(f"Analyzed {analyzed_count} reports with AI")
            except Exception as e:
                logger.warning(f"Report analysis failed: {e}")

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


def get_schedule_type() -> tuple[str, str]:
    """
    현재 실행 시간에 따른 스케줄 타입 반환

    Returns:
        (schedule_type, header_title)
    """
    from src.utils.constants import ScheduleSettings
    from src.utils.market_holiday import check_market_holidays

    now = datetime.now()
    weekday = now.weekday()  # 0=월요일, 6=일요일
    hour = now.hour

    # 주말 스케줄
    if weekday == 5:  # 토요일
        return ("saturday", ScheduleSettings.SATURDAY_TITLE)
    elif weekday == 6:  # 일요일
        return ("sunday", ScheduleSettings.SUNDAY_TITLE)

    # 평일 휴장일 체크
    holiday_info = check_market_holidays(now)
    if holiday_info.is_holiday:
        return ("holiday", ScheduleSettings.HOLIDAY_TITLE)

    # 평일 스케줄
    if ScheduleSettings.MORNING_START_HOUR <= hour <= ScheduleSettings.MORNING_END_HOUR:
        return ("morning", ScheduleSettings.MORNING_TITLE)
    elif ScheduleSettings.NOON_START_HOUR <= hour <= ScheduleSettings.NOON_END_HOUR:
        return ("noon", ScheduleSettings.NOON_TITLE)
    elif ScheduleSettings.AFTERNOON_START_HOUR <= hour <= ScheduleSettings.AFTERNOON_END_HOUR:
        return ("afternoon", ScheduleSettings.AFTERNOON_TITLE)
    return ("manual", ScheduleSettings.MANUAL_TITLE)


def send_weekend_to_discord(analyzed: dict, schedule_type: str) -> bool:
    """주말 전용 Discord 전송 (토요일: 리뷰, 일요일: 전망)"""
    from src.analyzer.weekly_summarizer import weekly_summarizer, weekly_preview
    from src.discord import create_weekly_review_embed, create_weekly_preview_embed

    logger.info(f"=== Sending Weekend Content ({schedule_type}) ===")

    now = datetime.now()
    embeds = []

    # 뉴스와 리포트 수집
    all_news = analyzed.get("korean_news", []) + analyzed.get("international_news", [])
    reports = analyzed.get("reports", [])

    if schedule_type == "saturday":
        # 토요일: 주간 리뷰
        logger.info("Generating weekly review...")
        review_data = weekly_summarizer.generate_weekly_review(
            news_items=all_news[:25],
            report_items=reports[:10],
        )
        embeds = create_weekly_review_embed(now, review_data)

    elif schedule_type == "sunday":
        # 일요일: 주간 전망
        logger.info("Generating weekly preview...")
        preview_data = weekly_preview.generate_weekly_preview(
            recent_news=all_news[:20],
            recent_reports=reports[:10],
        )
        embeds = create_weekly_preview_embed(now, preview_data)

    if not embeds:
        logger.warning("No weekend embeds generated")
        return False

    success = discord_sender.send_multiple_embeds(
        embeds=embeds,
        username="Market Rader 📈",
    )

    if success:
        logger.info(f"Successfully sent {len(embeds)} weekend embeds to Discord")
    else:
        logger.error("Failed to send weekend content to Discord")

    return success


def send_to_discord(analyzed: dict) -> bool:
    """Discord로 전송"""
    from src.utils.constants import NewsSettings, EmbedColors

    logger.info("=== Sending to Discord ===")

    embeds = []
    now = datetime.now()
    schedule_type, header_title = get_schedule_type()

    # 주말 스케줄 처리
    if schedule_type in ("saturday", "sunday"):
        return send_weekend_to_discord(analyzed, schedule_type)

    # 스케줄 타입에 따른 콘텐츠 설정
    is_brief_schedule = schedule_type in ("noon", "afternoon")  # 간략 스케줄 (뉴스만)

    if schedule_type == "noon":
        # 오후 12시: 한국 뉴스 위주 (최대 15개, 중요도 순)
        korean_news = analyzed.get("korean_news", [])[:NewsSettings.NOON_MAX_KOREAN_NEWS]
        intl_news = []  # 해외 뉴스 제외
        logger.info(f"Noon schedule: Korean news only ({len(korean_news)} items)")
    elif schedule_type == "afternoon":
        # 오후 5시: 한국 뉴스 위주 (최대 15개, 중요도 순) - 낮과 동일
        korean_news = analyzed.get("korean_news", [])[:NewsSettings.AFTERNOON_MAX_KOREAN_NEWS]
        intl_news = []  # 해외 뉴스 제외
        logger.info(f"Afternoon schedule: Korean news only ({len(korean_news)} items)")
    else:
        # 오전 7시/수동: 전체 콘텐츠
        korean_news = analyzed.get("korean_news", [])[:NewsSettings.MAX_KOREAN_NEWS]
        intl_news = analyzed.get("international_news", [])[:NewsSettings.MAX_INTL_NEWS]

    all_news = korean_news + intl_news

    # 0. Morning Brief (오전 스케줄에서만)
    morning_briefs = analyzed.get("morning_briefs", [])
    if schedule_type == "morning" and morning_briefs:
        # Morning Brief 종합 요약 생성
        combined_summary = analyzed.get("morning_brief_summary")
        brief_embeds = create_morning_brief_embed(morning_briefs, combined_summary)
        embeds.extend(brief_embeds)
        logger.info(f"Added {len(brief_embeds)} Morning Brief embeds")

    # 0-1. AI 아침 전략 브리핑 (오전 스케줄에서만)
    reports = analyzed.get("reports", [])
    if schedule_type == "morning" and all_news:
        try:
            morning_briefing = market_briefing_generator.generate_morning_strategy(
                news_items=all_news[:10],
                morning_briefs=morning_briefs,
                report_items=reports[:5],
            )
            if morning_briefing:
                # 브리핑 검증
                briefing_text = briefing_validator.get_briefing_text(morning_briefing)
                validation = briefing_validator.validate_briefing(
                    briefing_text=briefing_text,
                    market_data=None,  # 아침엔 시장 데이터 없음
                    news_items=all_news[:10],
                    report_items=reports[:5],
                )

                if validation.is_valid:
                    strategy_embed = create_morning_strategy_embed(morning_briefing, now)
                    embeds.append(strategy_embed)
                    logger.info(f"Added AI morning strategy briefing (validation score: {validation.score})")
                else:
                    # 검증 실패 시 로그 남기고 전송하지 않음
                    logger.warning(f"Morning strategy validation FAILED: {validation.errors}")
                    logger.warning(f"Validation warnings: {validation.warnings}")
        except Exception as e:
            logger.warning(f"Failed to generate morning strategy: {e}")

    # 0-2. 장 마감 시황 및 AI 리뷰 (오후 5시 스케줄에서만)
    if schedule_type == "afternoon":
        # 시장 데이터 수집
        market_data = None
        try:
            market_data = market_data_collector.collect()
            if market_data.kospi or market_data.usd_krw:
                market_close_embed = create_market_close_embed(market_data, now)
                embeds.append(market_close_embed)
                logger.info("Added market close summary embed")
        except Exception as e:
            logger.warning(f"Failed to collect market data: {e}")

        # AI 장 마감 리뷰 생성
        if all_news:
            try:
                # 시장 데이터를 dict로 변환
                market_dict = None
                if market_data:
                    market_dict = {
                        "kospi": {"value": market_data.kospi.value, "change": market_data.kospi.change, "change_percent": market_data.kospi.change_percent} if market_data.kospi else None,
                        "kosdaq": {"value": market_data.kosdaq.value, "change": market_data.kosdaq.change, "change_percent": market_data.kosdaq.change_percent} if market_data.kosdaq else None,
                        "usd_krw": {"value": market_data.usd_krw.value} if market_data.usd_krw else None,
                    }

                closing_briefing = market_briefing_generator.generate_closing_review(
                    news_items=all_news[:10],
                    report_items=reports[:5] if reports else None,
                    market_data=market_dict,
                )
                if closing_briefing:
                    # 브리핑 검증
                    briefing_text = briefing_validator.get_briefing_text(closing_briefing)
                    validation = briefing_validator.validate_briefing(
                        briefing_text=briefing_text,
                        market_data=market_dict,
                        news_items=all_news[:10],
                        report_items=reports[:5] if reports else None,
                    )

                    if validation.is_valid:
                        review_embed = create_closing_review_embed(closing_briefing, now)
                        embeds.append(review_embed)
                        logger.info(f"Added AI closing review briefing (validation score: {validation.score})")
                    else:
                        # 검증 실패 시 로그 남기고 전송하지 않음
                        logger.warning(f"Closing review validation FAILED: {validation.errors}")
                        logger.warning(f"Validation warnings: {validation.warnings}")
            except Exception as e:
                logger.warning(f"Failed to generate closing review: {e}")

    # 0-3. 긴급 뉴스 (있는 경우 최상단)
    breaking_news = analyzed.get("breaking_news", [])
    if breaking_news:
        breaking_embed = create_breaking_news_embed(breaking_news)
        if breaking_embed:
            embeds.append(breaking_embed)
            logger.info(f"Added breaking news embed ({len(breaking_news)} items)")

    # 1. 시장 시그널 헤더 (AI 분석 결과가 있으면) 또는 일반 헤더
    market_signal = analyzed.get("market_signal")
    if all_news:
        if market_signal:
            # 시장 시그널 Embed 사용
            signal_embed = create_market_signal_embed(
                date=now,
                signal_data=market_signal,
                news_count=len(all_news),
                title_override=header_title,
            )
            embeds.append(signal_embed)
        else:
            # 기존 헤더 Embed
            header_embed = create_news_header_embed(
                date=now,
                news_count=len(all_news),
                summary=analyzed.get("news_summary"),
                title_override=header_title,
            )
            embeds.append(header_embed)

    # 2. 국내 뉴스
    if korean_news:
        korean_embeds = create_news_list_embeds(
            items=korean_news,
            title=f"🇰🇷 국내 뉴스 ({len(korean_news)}건)",
            items_per_embed=5,
            color=EmbedColors.NEWS_KOREAN,
        )
        embeds.extend(korean_embeds)

    # 3. 해외 뉴스 (간략 스케줄에서는 건너뜀)
    if intl_news and not is_brief_schedule:
        intl_embeds = create_news_list_embeds(
            items=intl_news,
            title=f"🇺🇸 해외 뉴스 ({len(intl_news)}건)",
            items_per_embed=5,
            color=EmbedColors.NEWS_INTL,
        )
        embeds.extend(intl_embeds)

    # 간략 스케줄(점심/오후)에서는 리포트와 유튜브 제외
    reports = []
    korean_videos = []
    intl_videos = []
    video_summaries = {}

    if not is_brief_schedule:
        # 4. 리포트 (AI 분석 포함 시 상세 Embed 사용)
        reports = analyzed.get("reports", [])[:NewsSettings.MAX_REPORTS]
        if reports:
            # AI 분석된 리포트가 있는지 확인
            analyzed_reports = [r for r in reports if r.extra_data.get("ai_analysis")]

            if analyzed_reports:
                # AI 분석 포함 상세 Embed 사용
                report_embeds = create_reports_with_analysis_embeds(
                    items=reports,
                    max_detailed=3,  # 상세 분석 3개
                    max_list=7,  # 나머지 목록 7개
                )
                embeds.extend(report_embeds)
                logger.info(f"Added {len(report_embeds)} report embeds (with {len(analyzed_reports)} analyzed)")
            else:
                # 기존 방식 (AI 분석 없을 때)
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

        # 5. 한국 유튜브
        korean_videos = analyzed.get("korean_videos", [])[:NewsSettings.MAX_YOUTUBE_KOREAN]
        video_summaries = analyzed.get("video_summaries", {})

        if korean_videos:
            korean_yt_list = create_youtube_list_embed(
                items=korean_videos,
                title=f"🇰🇷 한국 유튜브 ({len(korean_videos)}건)",
                max_items=5,
                video_summaries=video_summaries,
            )
            embeds.append(korean_yt_list)

        # 6. 해외 유튜브
        intl_videos = analyzed.get("international_videos", [])[:NewsSettings.MAX_YOUTUBE_INTL]

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
        if morning_briefs:
            cache.mark_multiple_as_sent([b.id for b in morning_briefs], "morning_brief")
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
        # 현재 스케줄 타입 확인
        schedule_type, _ = get_schedule_type()

        # 휴장일 처리: 안내 Embed만 전송하고 종료
        if schedule_type == "holiday":
            from src.utils.market_holiday import check_market_holidays
            from src.discord.embeds.holiday_embed import create_holiday_embed

            now = datetime.now()
            holiday_info = check_market_holidays(now)
            logger.info(f"Market holiday detected: {holiday_info.summary}")

            embed = create_holiday_embed(holiday_info, now)
            success = discord_sender.send_multiple_embeds(
                embeds=[embed],
                username="Market Rader 📈",
            )
            if success:
                logger.info("Holiday notice sent to Discord")
            else:
                logger.error("Failed to send holiday notice")
            return

        is_morning = schedule_type == "morning"

        # 1. 콘텐츠 수집 (병렬 실행)
        logger.info("=== Starting Parallel Collection ===")
        news = {"korean": [], "international": []}
        reports = []
        videos = {"korean": [], "international": []}
        morning_briefs = []

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(collect_news): "news",
                # 오전 스케줄에서만 PDF 추출 (AI 분석용)
                executor.submit(collect_reports, extract_pdf=is_morning): "reports",
                executor.submit(collect_youtube): "youtube",
            }

            # 오전 스케줄에만 Morning Brief 수집
            if is_morning:
                futures[executor.submit(collect_morning_briefs)] = "morning_briefs"

            for future in as_completed(futures):
                task_name = futures[future]
                try:
                    result = future.result()
                    if task_name == "news":
                        news = result
                    elif task_name == "reports":
                        reports = result
                    elif task_name == "youtube":
                        videos = result
                    elif task_name == "morning_briefs":
                        morning_briefs = result
                    logger.info(f"Completed: {task_name}")
                except Exception as e:
                    logger.error(f"Failed to collect {task_name}: {e}")

        # 수집된 콘텐츠가 없으면 종료
        all_news = news.get("korean", []) + news.get("international", [])
        if not all_news and not reports and not videos and not morning_briefs:
            logger.info("No new content collected. Exiting.")
            return

        # 2. 분석 및 요약
        analyzed = analyze_content(news, reports, videos, morning_briefs)

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
