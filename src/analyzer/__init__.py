"""
AI 분석 모듈
Groq API를 사용한 요약 및 중요도 평가
"""
from src.analyzer.groq_client import GroqClient, groq_client
from src.analyzer.news_summarizer import (
    NewsSummarizer,
    ReportSummarizer,
    news_summarizer,
    report_summarizer,
)
from src.analyzer.video_summarizer import VideoSummarizer, video_summarizer
from src.analyzer.importance_scorer import ImportanceScorer, importance_scorer
from src.analyzer.morning_brief_summarizer import MorningBriefSummarizer, morning_brief_summarizer
from src.analyzer.market_signal import MarketSignalAnalyzer, market_signal_analyzer, Signal
from src.analyzer.report_analyzer import ReportAnalyzer, report_analyzer
from src.analyzer.market_briefing import (
    MarketBriefingGenerator,
    market_briefing_generator,
    MarketBriefing,
)

__all__ = [
    # Groq Client
    "GroqClient",
    "groq_client",
    # News Summarizer
    "NewsSummarizer",
    "ReportSummarizer",
    "news_summarizer",
    "report_summarizer",
    # Video Summarizer
    "VideoSummarizer",
    "video_summarizer",
    # Importance Scorer
    "ImportanceScorer",
    "importance_scorer",
    # Morning Brief Summarizer
    "MorningBriefSummarizer",
    "morning_brief_summarizer",
    # Market Signal Analyzer
    "MarketSignalAnalyzer",
    "market_signal_analyzer",
    "Signal",
    # Report Analyzer (PDF 기반)
    "ReportAnalyzer",
    "report_analyzer",
    # Market Briefing (가상 비서)
    "MarketBriefingGenerator",
    "market_briefing_generator",
    "MarketBriefing",
]
