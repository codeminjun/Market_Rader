"""장 마감 시황 + AI 리뷰 테스트 (실제 데이터 기반)"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from src.collectors.market import market_data_collector
from src.collectors.news import NaverFinanceNewsCollector
from src.collectors.reports import NaverResearchCollector
from src.discord.embeds.market_close_embed import create_market_close_embed
from src.discord.embeds.briefing_embed import create_closing_review_embed
from src.discord.embeds.news_embed import create_news_list_embeds
from src.analyzer.market_briefing import market_briefing_generator
from src.analyzer.briefing_validator import briefing_validator
from src.analyzer.importance_scorer import importance_scorer
from src.discord import discord_sender
from datetime import datetime

if __name__ == "__main__":
    print("=" * 60)
    print("장 마감 시황 + AI 리뷰 테스트 (실제 데이터 기반)")
    print("=" * 60)

    now = datetime.now()
    embeds = []

    # 1. 실제 뉴스 수집
    print("\n[1/6] 실제 뉴스 수집 중...")
    news_collector = NaverFinanceNewsCollector(categories=["stock", "economy"])
    news_items = news_collector.collect()
    print(f"  수집된 뉴스: {len(news_items)}건")
    for item in news_items[:3]:
        print(f"    - [{item.source}] {item.title[:40]}...")

    # 2. 실제 리포트 수집
    print("\n[2/6] 실제 리포트 수집 중...")
    report_collector = NaverResearchCollector(categories=["invest", "company"])
    report_items = report_collector.collect()
    print(f"  수집된 리포트: {len(report_items)}건")
    for item in report_items[:3]:
        stock = item.extra_data.get("stock_name", "")
        print(f"    - [{item.source}] {stock or item.title[:30]}...")

    # 3. 시장 데이터 수집
    print("\n[3/6] 시장 데이터 수집 중...")
    market_data = market_data_collector.collect()

    if market_data.kospi:
        sign = '+' if market_data.kospi.change >= 0 else ''
        print(f"  코스피: {market_data.kospi.value:,.2f} ({sign}{market_data.kospi.change_percent:.2f}%)")
    if market_data.kosdaq:
        sign = '+' if market_data.kosdaq.change >= 0 else ''
        print(f"  코스닥: {market_data.kosdaq.value:,.2f} ({sign}{market_data.kosdaq.change_percent:.2f}%)")
    if market_data.usd_krw:
        print(f"  USD/KRW: {market_data.usd_krw.value:,.2f}")

    # 시장 데이터 Embed
    if market_data.kospi or market_data.usd_krw:
        market_embed = create_market_close_embed(market_data, now)
        embeds.append(market_embed)
        print("  ✓ 시장 데이터 Embed 생성 완료")

    # 4. AI 장 마감 리뷰 생성 (실제 데이터 기반)
    print("\n[4/6] AI 장 마감 리뷰 생성 중 (실제 뉴스/리포트 분석)...")

    # 시장 데이터를 dict로 변환
    market_dict = None
    if market_data:
        market_dict = {
            "kospi": {"value": market_data.kospi.value, "change": market_data.kospi.change, "change_percent": market_data.kospi.change_percent} if market_data.kospi else None,
            "kosdaq": {"value": market_data.kosdaq.value, "change": market_data.kosdaq.change, "change_percent": market_data.kosdaq.change_percent} if market_data.kosdaq else None,
            "usd_krw": {"value": market_data.usd_krw.value} if market_data.usd_krw else None,
        }

    # 실제 뉴스와 리포트로 브리핑 생성
    briefing = market_briefing_generator.generate_closing_review(
        news_items=news_items[:10],  # 실제 뉴스 10건
        report_items=report_items[:5],  # 실제 리포트 5건
        market_data=market_dict,
    )

    if briefing:
        print(f"\n  === AI 분석 결과 ===")
        print(f"  인사: {briefing.greeting}")
        print(f"  요약: {briefing.summary}")
        print(f"  분위기: {briefing.mood}")
        print(f"  출처: {', '.join(briefing.sources[:3])}")

        # 5. 브리핑 검증
        print("\n[5/6] 브리핑 검증 중...")
        briefing_text = briefing_validator.get_briefing_text(briefing)
        validation = briefing_validator.validate_briefing(
            briefing_text=briefing_text,
            market_data=market_dict,
            news_items=news_items[:10],
            report_items=report_items[:5],
        )

        print(f"  검증 점수: {validation.score}")
        print(f"  검증 통과: {'✓' if validation.is_valid else '✗'}")

        if validation.errors:
            print(f"  오류:")
            for error in validation.errors:
                print(f"    - {error}")

        if validation.warnings:
            print(f"  경고:")
            for warning in validation.warnings[:3]:
                print(f"    - {warning}")

        if validation.is_valid:
            review_embed = create_closing_review_embed(briefing, now)
            embeds.append(review_embed)
            print("\n  ✓ AI 리뷰 Embed 생성 완료 (검증 통과)")
        else:
            print("\n  ✗ AI 리뷰 검증 실패 - 전송하지 않음")
    else:
        print("  ✗ AI 리뷰 생성 실패")

    # 6. 한국 뉴스 목록 (중요도 순 10개)
    print("\n[6/6] 한국 뉴스 목록 생성 중...")
    if news_items:
        # 중요도 점수 계산 및 정렬
        scored_news = importance_scorer.filter_by_importance(news_items, min_score=0.3)
        top_news = scored_news[:10]  # 상위 10개

        print(f"  상위 10개 뉴스 (중요도순):")
        for i, item in enumerate(top_news, 1):
            priority_mark = ""
            if item.extra_data.get("is_priority_journalist_article"):
                priority_mark = " [우선기자]"
            elif item.extra_data.get("is_priority_keyword_match"):
                priority_mark = " [우선키워드]"
            print(f"    {i}. [{item.importance_score:.2f}] {item.title[:40]}...{priority_mark}")

        # 뉴스 목록 Embed 생성
        news_embeds = create_news_list_embeds(
            items=top_news,
            title=f"🇰🇷 장마감 주요 뉴스 ({len(top_news)}건)",
            items_per_embed=5,
            color="e74c3c",  # 빨강
        )
        embeds.extend(news_embeds)
        print(f"  ✓ 뉴스 목록 Embed {len(news_embeds)}개 생성 완료")
    else:
        print("  ✗ 뉴스 없음")

    # 7. Discord 전송
    print("\n" + "=" * 60)
    print("Discord로 전송하시겠습니까? (y/n): ", end="")
    choice = input().strip().lower()

    if choice == 'y' and embeds:
        print("전송 중...")
        success = discord_sender.send_multiple_embeds(embeds)
        if success:
            print("✅ 전송 완료!")
        else:
            print("❌ 전송 실패")
    else:
        print("전송 취소됨")

    print("=" * 60)
