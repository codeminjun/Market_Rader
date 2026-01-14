"""아침 전략 브리핑 테스트 (실제 데이터 기반) - 전체 항목 포함"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from src.collectors.news import NaverFinanceNewsCollector, RSSNewsCollector
from src.collectors.reports import NaverResearchCollector, MorningBriefCollector
from src.collectors.youtube import YouTubeChannelMonitor
from src.discord.embeds.briefing_embed import create_morning_strategy_embed
from src.discord.embeds.news_embed import create_news_list_embeds
from src.discord.embeds.morning_brief_embed import create_morning_brief_embed
from src.discord.embeds.report_embed import (
    create_reports_with_analysis_embeds,
    create_reports_header_embed,
    create_reports_list_embed,
)
from src.discord.embeds.youtube_embed import create_youtube_list_embed
from src.analyzer.market_briefing import market_briefing_generator
from src.analyzer.briefing_validator import briefing_validator
from src.analyzer.importance_scorer import importance_scorer
from src.analyzer import morning_brief_summarizer, video_summarizer, report_analyzer
from src.discord import discord_sender
from config.settings import get_news_sources
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

if __name__ == "__main__":
    print("=" * 60)
    print("아침 전략 브리핑 테스트 (전체 항목 포함)")
    print("=" * 60)

    now = datetime.now()
    embeds = []

    # 1. 한국 뉴스 수집
    print("\n[1/7] 한국 뉴스 수집 중...")
    news_collector = NaverFinanceNewsCollector(categories=["stock", "economy"], extract_journalist=True)
    korean_news = news_collector.collect()
    for item in korean_news:
        item.extra_data["region"] = "korean"
    print(f"  수집된 한국 뉴스: {len(korean_news)}건")

    # 기자명 추출 현황
    journalists_found = sum(1 for n in korean_news if n.extra_data.get("journalist"))
    print(f"  기자명 추출: {journalists_found}건")

    # 2. 해외 뉴스 수집 (RSS)
    print("\n[2/7] 해외 뉴스 수집 중...")
    international_news = []
    news_config = get_news_sources()
    intl_sources = news_config.get("news", {}).get("international", [])

    for source in intl_sources[:5]:  # 상위 5개 소스만
        if source.get("type") == "rss" and source.get("enabled", True):
            try:
                collector = RSSNewsCollector(
                    name=source["name"],
                    url=source["url"],
                )
                items = collector.collect()
                for item in items:
                    item.extra_data["region"] = "international"
                international_news.extend(items)
                print(f"    - {source['name']}: {len(items)}건")
            except Exception as e:
                print(f"    - {source['name']}: 실패 ({e})")

    print(f"  수집된 해외 뉴스: {len(international_news)}건")

    # 3. 리포트 수집 (PDF 추출 포함)
    print("\n[3/7] 리포트 수집 중 (PDF 추출 포함)...")
    report_collector = NaverResearchCollector(
        categories=["invest", "company", "market"],
        extract_pdf=True,
        max_pdf_extract=8,  # 더 많은 리포트 분석을 위해 증가
    )
    report_items = report_collector.collect()
    print(f"  수집된 리포트: {len(report_items)}건")

    # PDF 추출된 리포트 수
    pdf_extracted = sum(1 for r in report_items if r.extra_data.get("pdf_text"))
    print(f"  PDF 추출: {pdf_extracted}건")

    # 4. Morning Brief 수집
    print("\n[4/7] Morning Brief 수집 중...")
    try:
        brief_collector = MorningBriefCollector(max_briefs=3)
        morning_briefs = brief_collector.collect()
        print(f"  수집된 Morning Brief: {len(morning_briefs)}건")
        for brief in morning_briefs[:3]:
            print(f"    - [{brief.source}] {brief.title[:40]}...")
    except Exception as e:
        print(f"  Morning Brief 수집 실패: {e}")
        morning_briefs = []

    # 5. 유튜브 수집
    print("\n[5/7] 유튜브 영상 수집 중...")
    try:
        youtube_monitor = YouTubeChannelMonitor()
        videos = youtube_monitor.collect()
        korean_videos = videos.get("korean", [])[:5]
        intl_videos = videos.get("international", [])[:5]
        print(f"  한국 유튜브: {len(korean_videos)}건")
        print(f"  해외 유튜브: {len(intl_videos)}건")
    except Exception as e:
        print(f"  유튜브 수집 실패: {e}")
        korean_videos = []
        intl_videos = []

    # 6. 중요도 점수 계산
    print("\n[6/7] 중요도 점수 계산 중...")

    # 한국 뉴스
    scored_korean = importance_scorer.filter_by_importance(korean_news, min_score=0.3)
    top_korean = scored_korean[:15]

    # 해외 뉴스
    scored_intl = importance_scorer.filter_by_importance(international_news, min_score=0.3)
    top_intl = scored_intl[:10]

    # 리포트
    scored_reports = importance_scorer.score_batch(report_items)
    scored_reports.sort(key=lambda x: x.importance_score, reverse=True)
    top_reports = scored_reports[:10]

    # 우선 항목 확인
    priority_journalist_count = sum(1 for n in top_korean if n.extra_data.get("is_priority_journalist_article"))
    priority_keyword_count = sum(1 for n in top_korean if n.extra_data.get("is_priority_keyword_match"))
    print(f"  한국 뉴스 우선 기자: {priority_journalist_count}건")
    print(f"  한국 뉴스 우선 키워드: {priority_keyword_count}건")

    print(f"\n  상위 5개 한국 뉴스:")
    for i, item in enumerate(top_korean[:5], 1):
        journalist = item.extra_data.get("journalist", "")
        j_str = f" (기자:{journalist})" if journalist else ""
        print(f"    {i}. [{item.importance_score:.2f}] {item.title[:35]}...{j_str}")

    print(f"\n  상위 5개 해외 뉴스:")
    for i, item in enumerate(top_intl[:5], 1):
        print(f"    {i}. [{item.importance_score:.2f}] {item.title[:45]}...")

    # 7. Embed 생성
    print("\n[7/7] Embed 생성 중...")

    all_news = top_korean[:10] + top_intl[:5]

    # 7-1. Morning Brief Embed (개별 분석 포함)
    if morning_briefs:
        # 개별 Morning Brief AI 분석
        print("  Morning Brief 개별 분석 중...")
        morning_briefs = morning_brief_summarizer.analyze_all_briefs(morning_briefs)
        analyzed_count = sum(1 for b in morning_briefs if b.extra_data.get("ai_analysis"))
        print(f"    개별 분석 완료: {analyzed_count}건")

        # 종합 요약
        combined_summary = morning_brief_summarizer.summarize_multiple_briefs(morning_briefs)
        brief_embeds = create_morning_brief_embed(morning_briefs, combined_summary, show_individual_analysis=True)
        embeds.extend(brief_embeds)
        print(f"  Morning Brief Embed: {len(brief_embeds)}개")

    # 7-2. AI 아침 전략 브리핑
    print("  AI 아침 전략 브리핑 생성 중...")
    briefing = market_briefing_generator.generate_morning_strategy(
        news_items=all_news,
        morning_briefs=morning_briefs,
        report_items=top_reports[:5],
    )

    if briefing:
        print(f"    인사: {briefing.greeting[:50]}...")
        print(f"    요약: {briefing.summary[:60]}...")
        print(f"    분위기: {briefing.mood}")

        # 브리핑 검증
        briefing_text = briefing_validator.get_briefing_text(briefing)
        validation = briefing_validator.validate_briefing(
            briefing_text=briefing_text,
            market_data=None,
            news_items=all_news,
            report_items=top_reports[:5],
        )

        print(f"    검증 점수: {validation.score}")
        print(f"    검증 통과: {'O' if validation.is_valid else 'X'}")

        if validation.is_valid:
            strategy_embed = create_morning_strategy_embed(briefing, now)
            embeds.append(strategy_embed)
            print("  AI 아침 브리핑 Embed: 1개 (검증 통과)")
        else:
            print("  AI 브리핑 검증 실패 - 전송하지 않음")
            for error in validation.errors:
                print(f"    오류: {error}")
    else:
        print("  AI 브리핑 생성 실패")

    # 7-3. 한국 뉴스 목록
    if top_korean:
        news_embeds = create_news_list_embeds(
            items=top_korean,
            title=f"🇰🇷 국내 뉴스 ({len(top_korean)}건)",
            items_per_embed=5,
            color="e74c3c",
        )
        embeds.extend(news_embeds)
        print(f"  한국 뉴스 Embed: {len(news_embeds)}개")

    # 7-4. 해외 뉴스 목록
    if top_intl:
        intl_embeds = create_news_list_embeds(
            items=top_intl,
            title=f"🇺🇸 해외 뉴스 ({len(top_intl)}건)",
            items_per_embed=5,
            color="3498db",
        )
        embeds.extend(intl_embeds)
        print(f"  해외 뉴스 Embed: {len(intl_embeds)}개")

    # 7-5. 리포트 목록
    if top_reports:
        # PDF 추출된 리포트 AI 분석
        pdf_reports = [r for r in top_reports if r.extra_data.get("pdf_text")]
        if pdf_reports:
            try:
                report_analyzer.analyze_batch(pdf_reports, max_items=5)  # 더 많은 리포트 분석
                analyzed_count = sum(1 for r in pdf_reports if r.extra_data.get("ai_analysis"))
                print(f"  리포트 AI 분석: {analyzed_count}건")
            except Exception as e:
                print(f"  리포트 AI 분석 실패: {e}")

        # AI 분석된 리포트가 있으면 상세 Embed
        analyzed_reports = [r for r in top_reports if r.extra_data.get("ai_analysis")]
        if analyzed_reports:
            report_embeds = create_reports_with_analysis_embeds(
                items=top_reports,
                max_detailed=3,
                max_list=7,
            )
            embeds.extend(report_embeds)
            print(f"  리포트 Embed (AI 분석 포함): {len(report_embeds)}개")
        else:
            # 기존 방식
            reports_header = create_reports_header_embed(
                report_count=len(top_reports),
                summary=None,
            )
            embeds.append(reports_header)
            reports_list = create_reports_list_embed(
                items=top_reports,
                max_items=10,
            )
            embeds.append(reports_list)
            print(f"  리포트 Embed: 2개")

    # 7-6. 유튜브 영상
    video_summaries = {}

    # 유튜브 요약 (병렬)
    all_videos = korean_videos + intl_videos
    if all_videos:
        print("  유튜브 요약 생성 중...")
        for video in all_videos[:5]:  # 상위 5개만
            try:
                summary = video_summarizer.summarize_video(video)
                if summary:
                    video_summaries[video.id] = summary
            except Exception as e:
                pass

    if korean_videos:
        korean_yt_embed = create_youtube_list_embed(
            items=korean_videos,
            title=f"🇰🇷 한국 유튜브 ({len(korean_videos)}건)",
            max_items=5,
            video_summaries=video_summaries,
        )
        embeds.append(korean_yt_embed)
        print(f"  한국 유튜브 Embed: 1개")

    if intl_videos:
        intl_yt_embed = create_youtube_list_embed(
            items=intl_videos,
            title=f"🇺🇸 해외 유튜브 ({len(intl_videos)}건)",
            max_items=5,
            video_summaries=video_summaries,
        )
        embeds.append(intl_yt_embed)
        print(f"  해외 유튜브 Embed: 1개")

    # 8. Discord 전송
    print("\n" + "=" * 60)
    print(f"총 {len(embeds)}개 Embed 생성됨")
    print("Discord로 전송하시겠습니까? (y/n): ", end="")
    choice = input().strip().lower()

    if choice == 'y' and embeds:
        print("전송 중...")
        success = discord_sender.send_multiple_embeds(embeds)
        if success:
            print("전송 완료!")
        else:
            print("전송 실패")
    else:
        print("전송 취소됨")

    print("=" * 60)
