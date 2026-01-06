"""
스케줄별 테스트 스크립트
오전 7시 / 오후 12시 스케줄을 강제로 테스트
"""
import sys
from pathlib import Path

# 프로젝트 루트 설정
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from unittest.mock import patch
from datetime import datetime


def test_morning():
    """오전 7시 스케줄 테스트 (전체 콘텐츠)"""
    print("=" * 60)
    print("🌅 오전 7시 스케줄 테스트 (전체 콘텐츠)")
    print("=" * 60)

    # 오전 7시로 시간 모킹
    mock_time = datetime(2025, 1, 6, 7, 0, 0)

    with patch('src.main.datetime') as mock_datetime:
        mock_datetime.now.return_value = mock_time
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        from src.main import get_schedule_type
        schedule_type, header = get_schedule_type()
        print(f"Schedule Type: {schedule_type}")
        print(f"Header: {header}")
        print()

        # 실제 수집 및 전송 테스트
        run_full_test(mock_datetime)


def test_noon():
    """오후 12시 스케줄 테스트 (뉴스 위주)"""
    print("=" * 60)
    print("🌞 오후 12시 스케줄 테스트 (한국 뉴스 15개)")
    print("=" * 60)

    # 오후 12시로 시간 모킹
    mock_time = datetime(2025, 1, 6, 12, 0, 0)

    with patch('src.main.datetime') as mock_datetime:
        mock_datetime.now.return_value = mock_time
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        from src.main import get_schedule_type
        schedule_type, header = get_schedule_type()
        print(f"Schedule Type: {schedule_type}")
        print(f"Header: {header}")
        print()

        # 실제 수집 및 전송 테스트
        run_full_test(mock_datetime)


def run_full_test(mock_datetime):
    """전체 파이프라인 테스트 (Discord 전송 제외)"""
    from src.main import collect_news, collect_reports, collect_youtube, analyze_content, get_schedule_type
    from src.utils.constants import NewsSettings

    print("📡 수집 중...")
    news = collect_news()
    reports = collect_reports()
    videos = collect_youtube()

    print(f"\n📊 수집 결과:")
    print(f"  - 한국 뉴스: {len(news.get('korean', []))}개")
    print(f"  - 해외 뉴스: {len(news.get('international', []))}개")
    print(f"  - 리포트: {len(reports)}개")
    print(f"  - 한국 유튜브: {len(videos.get('korean', []))}개")
    print(f"  - 해외 유튜브: {len(videos.get('international', []))}개")

    print("\n🔍 분석 중...")
    analyzed = analyze_content(news, reports, videos)

    schedule_type, _ = get_schedule_type()
    is_noon = schedule_type == "noon"

    print(f"\n📋 전송 예정 콘텐츠 ({schedule_type} 스케줄):")

    if is_noon:
        # 점심: 한국 뉴스만 15개
        korean_news = analyzed.get("korean_news", [])[:NewsSettings.NOON_MAX_KOREAN_NEWS]
        print(f"  - 한국 뉴스: {len(korean_news)}개 (최대 15개)")
        print(f"  - 해외 뉴스: 0개 (점심 스케줄 제외)")
        print(f"  - 리포트: 0개 (점심 스케줄 제외)")
        print(f"  - 유튜브: 0개 (점심 스케줄 제외)")

        print(f"\n📰 한국 뉴스 목록 (중요도 순):")
        for i, item in enumerate(korean_news, 1):
            score = f"[{item.importance_score:.2f}]"
            covered = "💰" if item.extra_data.get("is_covered_call") else ""
            print(f"  {i:2}. {score} {covered}{item.title[:50]}...")
    else:
        # 아침: 전체 콘텐츠
        korean_news = analyzed.get("korean_news", [])[:NewsSettings.MAX_KOREAN_NEWS]
        intl_news = analyzed.get("international_news", [])[:NewsSettings.MAX_INTL_NEWS]
        reports_list = analyzed.get("reports", [])[:NewsSettings.MAX_REPORTS]
        korean_videos = analyzed.get("korean_videos", [])[:NewsSettings.MAX_YOUTUBE_KOREAN]
        intl_videos = analyzed.get("international_videos", [])[:NewsSettings.MAX_YOUTUBE_INTL]

        print(f"  - 한국 뉴스: {len(korean_news)}개")
        print(f"  - 해외 뉴스: {len(intl_news)}개")
        print(f"  - 리포트: {len(reports_list)}개")
        print(f"  - 한국 유튜브: {len(korean_videos)}개")
        print(f"  - 해외 유튜브: {len(intl_videos)}개")

        print(f"\n📰 한국 뉴스 (상위 5개):")
        for i, item in enumerate(korean_news[:5], 1):
            score = f"[{item.importance_score:.2f}]"
            print(f"  {i}. {score} {item.title[:50]}...")

        if reports_list:
            print(f"\n📊 리포트 (상위 3개):")
            for i, item in enumerate(reports_list[:3], 1):
                print(f"  {i}. {item.title[:50]}...")


def test_dry_run():
    """Dry Run - Discord 전송 없이 분석 결과만 확인"""
    print("=" * 60)
    print("🧪 Dry Run 테스트 (현재 시간 기준)")
    print("=" * 60)

    from src.main import get_schedule_type
    schedule_type, header = get_schedule_type()
    print(f"현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Schedule Type: {schedule_type}")
    print(f"Header: {header}")
    print()

    run_full_test(None)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법:")
        print("  python test_schedule.py morning  - 오전 7시 스케줄 테스트")
        print("  python test_schedule.py noon     - 오후 12시 스케줄 테스트")
        print("  python test_schedule.py dry      - 현재 시간 기준 테스트")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "morning":
        test_morning()
    elif mode == "noon":
        test_noon()
    elif mode == "dry":
        test_dry_run()
    else:
        print(f"알 수 없는 모드: {mode}")
        print("morning, noon, dry 중 하나를 선택하세요.")
