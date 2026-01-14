"""
중요도 점수 판단 모듈
AI 기반 콘텐츠 중요도 평가
"""
import re
from functools import lru_cache
from typing import Optional

from src.collectors.base import ContentItem, Priority
from src.analyzer.groq_client import groq_client
from src.utils.logger import logger
from src.utils.constants import ImportanceThresholds
from config.settings import get_news_sources, get_journalist_priority


class ImportanceScorer:
    """콘텐츠 중요도 평가기"""

    SYSTEM_PROMPT = """당신은 금융 뉴스 편집자입니다.
뉴스와 콘텐츠의 투자 관련 중요도를 평가합니다.
객관적이고 일관된 기준으로 평가합니다."""

    # 언론사별 가중치 (사용자 선호도 반영)
    SOURCE_WEIGHTS = {
        "한국경제": 0.10,      # 선호 언론사: +10%
        "연합인포맥스": 0.05,  # 중립
        "매일경제": -0.05,     # 상대적 낮은 우선순위: -5%
    }

    # 커버드콜/배당 키워드 (최최우선 가중치: +0.30)
    COVERED_CALL_KEYWORDS = [
        # 커버드콜
        "커버드콜", "covered call", "콜옵션", "프리미엄",
        # 배당 관련
        "배당", "dividend", "배당주", "배당금", "배당수익", "배당성장",
        "고배당", "월배당", "분기배당", "연배당", "배당락",
        "배당귀족", "배당킹", "배당챔피언", "배당ETF", "인컴",
        # 대표 배당 ETF
        "SCHD", "JEPI", "JEPQ", "QYLD", "XYLD", "DIVO",
        "TIGER 미국배당", "KODEX 배당", "ARIRANG 고배당",
        # 리츠/인컴
        "리츠", "REITs", "부동산투자", "인컴펀드",
    ]

    # 산업뉴스 키워드 (최우선 가중치: +0.20)
    INDUSTRY_KEYWORDS = [
        # 반도체/IT
        "반도체", "파운드리", "HBM", "메모리", "D램", "낸드", "AP", "GPU", "NPU",
        "삼성전자", "SK하이닉스", "인텔", "엔비디아", "TSMC", "AMD", "퀄컴",
        # 2차전지/배터리
        "2차전지", "배터리", "리튬", "양극재", "음극재", "전해질", "분리막",
        "LG에너지솔루션", "삼성SDI", "SK온", "CATL", "파나소닉",
        "전기차", "EV", "전고체",
        # AI/소프트웨어
        "AI", "인공지능", "LLM", "생성형", "챗GPT", "클라우드", "데이터센터",
        # 바이오/헬스케어
        "바이오", "신약", "임상", "FDA", "셀트리온", "삼성바이오", "SK바이오",
        # 자동차
        "현대차", "기아", "테슬라", "자율주행", "전기차", "수소차",
        # 조선/해운
        "조선", "HD한국조선", "삼성중공업", "한화오션", "LNG선", "컨테이너선",
        # 철강/화학
        "포스코", "철강", "화학", "석유화학", "정유", "LG화학",
        # 방산/항공
        "방산", "한화에어로", "KAI", "LIG넥스원", "무기", "수출",
        # 금융
        "은행", "증권", "보험", "KB", "신한", "하나", "우리",
    ]

    # 중요 키워드 (설정에서 로드)
    HIGH_IMPORTANCE_KEYWORDS = [
        # 금리/통화정책
        "금리", "FOMC", "연준", "Fed", "기준금리", "금리인하", "금리인상",
        # 기업 이벤트
        "실적발표", "어닝", "IPO", "상장", "인수", "합병", "M&A",
        # 시장 급변
        "파산", "부도", "긴급", "급등", "급락", "폭락", "폭등", "사상최고",
        # 주요 지수
        "코스피", "코스닥", "나스닥", "S&P500", "다우", "니케이",
        # 시사/정책
        "트럼프", "관세", "무역전쟁", "환율", "달러",
    ]

    MEDIUM_IMPORTANCE_KEYWORDS = [
        # 투자 분석
        "전망", "분석", "목표가", "투자의견", "리포트",
        "매수", "매도", "상향", "하향", "추천",
        # 기업 재무
        "실적", "배당", "자사주", "영업이익", "순이익",
        # 시장 동향
        "상승", "하락", "반등", "조정", "횡보",
        "ETF", "펀드", "채권", "국채",
        # 경제 지표
        "고용", "물가", "CPI", "GDP", "PMI",
    ]

    def __init__(self):
        self.client = groq_client
        self._load_keywords_from_config()
        self._load_journalist_priority()
        self._load_analyst_priority()
        self._load_keyword_priority()
        self._load_report_source_priority()
        # 사전 컴파일된 정규표현식 패턴 생성 (성능 최적화)
        self._compiled_patterns = {}
        self._compile_keyword_patterns()
        self._compile_journalist_patterns()
        self._compile_analyst_patterns()
        self._compile_priority_keyword_patterns()

    def _compile_keyword_patterns(self):
        """키워드 리스트를 정규표현식 패턴으로 사전 컴파일 (성능 최적화)"""
        keyword_lists = {
            "covered_call": self.COVERED_CALL_KEYWORDS,
            "industry": self.INDUSTRY_KEYWORDS,
            "high": self.HIGH_IMPORTANCE_KEYWORDS,
            "medium": self.MEDIUM_IMPORTANCE_KEYWORDS,
        }

        for name, keywords in keyword_lists.items():
            # 대소문자 무시 정규표현식 패턴 생성
            escaped_keywords = [re.escape(kw.lower()) for kw in keywords]
            pattern = re.compile("|".join(escaped_keywords), re.IGNORECASE)
            self._compiled_patterns[name] = pattern

    def _check_keywords(self, text_lower: str, keywords: list, pattern_name: str = None) -> bool:
        """키워드 리스트에서 매칭 여부 확인 (사전 컴파일된 패턴 사용)"""
        if pattern_name and pattern_name in self._compiled_patterns:
            return bool(self._compiled_patterns[pattern_name].search(text_lower))
        return any(keyword.lower() in text_lower for keyword in keywords)

    def _load_keywords_from_config(self):
        """설정에서 키워드 로드"""
        try:
            config = get_news_sources()
            keywords = config.get("important_keywords", {})

            if "covered_call" in keywords:
                self.COVERED_CALL_KEYWORDS.extend(keywords["covered_call"])
            if "industry" in keywords:
                self.INDUSTRY_KEYWORDS.extend(keywords["industry"])
            if "high" in keywords:
                self.HIGH_IMPORTANCE_KEYWORDS.extend(keywords["high"])
            if "medium" in keywords:
                self.MEDIUM_IMPORTANCE_KEYWORDS.extend(keywords["medium"])

        except Exception as e:
            logger.debug(f"Could not load keywords from config: {e}")

    def _load_journalist_priority(self):
        """우선 기자 설정 로드"""
        self._journalist_priority = []
        self._journalist_settings = {
            "require_affiliation_match": False,
            "store_journalist_info": True,
            "flag_priority_articles": True,
        }

        try:
            config = get_journalist_priority()
            journalists = config.get("priority_journalists", [])

            for j in journalists:
                self._journalist_priority.append({
                    "name": j.get("name", ""),
                    "affiliation": j.get("affiliation", ""),
                    "weight": float(j.get("weight", 0.0)),
                    "rank": int(j.get("rank", 99)),
                    "note": j.get("note", ""),
                })

            # 설정 로드
            settings_cfg = config.get("settings", {})
            self._journalist_settings.update(settings_cfg)

            logger.info(f"Loaded {len(self._journalist_priority)} priority journalists")

        except Exception as e:
            logger.debug(f"Could not load journalist priority config: {e}")

    def _compile_journalist_patterns(self):
        """기자명 매칭용 정규표현식 패턴 사전 컴파일"""
        self._journalist_patterns = []

        for j in self._journalist_priority:
            name = j["name"]
            if not name:
                continue

            # 기자명 패턴: "기자명 + (기자|특파원|대표|편집장|)" 형태 매칭
            # 예: "안재광 기자", "김현석 특파원", "안근모"
            pattern = re.compile(
                rf'{re.escape(name)}\s*(?:기자|특파원|대표|편집장|에디터|)',
                re.IGNORECASE
            )
            self._journalist_patterns.append({
                "pattern": pattern,
                "journalist": j,
            })

    def _check_journalist_priority(self, text: str, item: ContentItem) -> float:
        """
        텍스트에서 우선 기자 매칭 확인 및 가중치 반환

        Args:
            text: 검색할 텍스트 (제목 + 내용)
            item: 콘텐츠 항목 (extra_data 업데이트용)

        Returns:
            매칭된 기자의 가중치 (매칭 없으면 0.0)
        """
        if not self._journalist_priority:
            return 0.0

        best_match = None
        best_weight = 0.0

        # 1. extra_data["journalist"]에서 직접 매칭 확인 (가장 정확)
        extracted_journalist = item.extra_data.get("journalist", "")
        if extracted_journalist:
            for j in self._journalist_priority:
                if j["name"] == extracted_journalist:
                    best_weight = j["weight"]
                    best_match = j
                    break

        # 2. 본문 텍스트에서 패턴 매칭 (fallback)
        if not best_match and self._journalist_patterns:
            for jp in self._journalist_patterns:
                pattern = jp["pattern"]
                journalist = jp["journalist"]

                if pattern.search(text):
                    # 소속 확인 필요 시
                    if self._journalist_settings.get("require_affiliation_match", False):
                        affiliation = journalist["affiliation"]
                        if affiliation and affiliation not in text:
                            continue

                    # 더 높은 가중치를 가진 기자로 업데이트
                    if journalist["weight"] > best_weight:
                        best_weight = journalist["weight"]
                        best_match = journalist

        # 매칭된 기자 정보 저장
        if best_match and self._journalist_settings.get("store_journalist_info", True):
            item.extra_data["priority_journalist"] = {
                "name": best_match["name"],
                "affiliation": best_match["affiliation"],
                "rank": best_match.get("rank", 99),
                "note": best_match.get("note", ""),
            }
            if self._journalist_settings.get("flag_priority_articles", True):
                item.extra_data["is_priority_journalist_article"] = True

        return best_weight

    def _load_analyst_priority(self):
        """우선 애널리스트 설정 로드"""
        self._analyst_priority = []

        try:
            config = get_journalist_priority()
            analysts = config.get("priority_analysts", [])

            for a in analysts:
                self._analyst_priority.append({
                    "name": a.get("name", ""),
                    "affiliation": a.get("affiliation", ""),
                    "weight": float(a.get("weight", 0.0)),
                })

            logger.info(f"Loaded {len(self._analyst_priority)} priority analysts")

        except Exception as e:
            logger.debug(f"Could not load analyst priority config: {e}")

    def _compile_analyst_patterns(self):
        """애널리스트명 매칭용 정규표현식 패턴 사전 컴파일"""
        self._analyst_patterns = []

        for a in self._analyst_priority:
            name = a["name"]
            if not name:
                continue

            # 애널리스트명 패턴: "이름 + (애널리스트|연구원|)" 형태 매칭
            # 예: "허혜민 애널리스트", "엄경아 연구원", "박은정"
            pattern = re.compile(
                rf'{re.escape(name)}\s*(?:애널리스트|연구원|)',
                re.IGNORECASE
            )
            self._analyst_patterns.append({
                "pattern": pattern,
                "analyst": a,
            })

    def _check_analyst_priority(self, text: str, item: ContentItem) -> float:
        """
        텍스트에서 우선 애널리스트 매칭 확인 및 가중치 반환

        Args:
            text: 검색할 텍스트 (제목 + 내용)
            item: 콘텐츠 항목 (extra_data 업데이트용)

        Returns:
            매칭된 애널리스트의 가중치 (매칭 없으면 0.0)
        """
        if not self._analyst_patterns:
            return 0.0

        best_match = None
        best_weight = 0.0

        for ap in self._analyst_patterns:
            pattern = ap["pattern"]
            analyst = ap["analyst"]

            if pattern.search(text):
                # 소속 확인 필요 시
                if self._journalist_settings.get("require_affiliation_match", False):
                    affiliation = analyst["affiliation"]
                    if affiliation and affiliation not in text:
                        continue

                # 더 높은 가중치를 가진 애널리스트로 업데이트
                if analyst["weight"] > best_weight:
                    best_weight = analyst["weight"]
                    best_match = analyst

        # 매칭된 애널리스트 정보 저장
        if best_match and self._journalist_settings.get("store_analyst_info", True):
            item.extra_data["priority_analyst"] = {
                "name": best_match["name"],
                "affiliation": best_match["affiliation"],
            }
            if self._journalist_settings.get("flag_priority_articles", True):
                item.extra_data["is_priority_analyst_article"] = True

        return best_weight

    def _load_keyword_priority(self):
        """우선 키워드 설정 로드"""
        self._keyword_priority = []

        try:
            config = get_journalist_priority()
            keywords = config.get("priority_keywords", [])

            for k in keywords:
                self._keyword_priority.append({
                    "keyword": k.get("keyword", ""),
                    "weight": float(k.get("weight", 0.0)),
                })

            # 설정에서 키워드 부스트 적용 여부 로드
            settings = config.get("settings", {})
            self._apply_keyword_boost = settings.get("apply_keyword_boost", True)

            logger.info(f"Loaded {len(self._keyword_priority)} priority keywords")

        except Exception as e:
            logger.debug(f"Could not load keyword priority config: {e}")
            self._apply_keyword_boost = True

    def _compile_priority_keyword_patterns(self):
        """우선 키워드 매칭용 정규표현식 패턴 사전 컴파일"""
        self._priority_keyword_patterns = []

        for k in self._keyword_priority:
            keyword = k["keyword"]
            if not keyword:
                continue

            # 키워드 패턴 (대소문자 무시)
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            self._priority_keyword_patterns.append({
                "pattern": pattern,
                "keyword_data": k,
            })

    def _check_keyword_priority(self, text: str, item: ContentItem) -> float:
        """
        텍스트에서 우선 키워드 매칭 확인 및 가중치 반환

        Args:
            text: 검색할 텍스트 (제목 + 내용)
            item: 콘텐츠 항목 (extra_data 업데이트용)

        Returns:
            매칭된 키워드들의 총 가중치 (최대 0.4로 제한)
        """
        if not self._apply_keyword_boost or not self._priority_keyword_patterns:
            return 0.0

        total_weight = 0.0
        matched_keywords = []

        for kp in self._priority_keyword_patterns:
            pattern = kp["pattern"]
            keyword_data = kp["keyword_data"]

            if pattern.search(text):
                total_weight += keyword_data["weight"]
                matched_keywords.append(keyword_data["keyword"])

        # 매칭된 키워드 정보 저장
        if matched_keywords:
            item.extra_data["priority_keywords"] = matched_keywords
            item.extra_data["is_priority_keyword_match"] = True

        # 키워드 가중치 최대값 제한 (너무 높은 점수 방지)
        return min(total_weight, 0.4)

    def _load_report_source_priority(self):
        """우선 리포트 소스 설정 로드"""
        self._report_source_priority = []

        try:
            config = get_journalist_priority()
            sources = config.get("priority_report_sources", [])

            for s in sources:
                self._report_source_priority.append({
                    "name": s.get("name", ""),
                    "report_type": s.get("report_type", ""),
                    "weight": float(s.get("weight", 0.0)),
                })

            # 설정에서 소스 부스트 적용 여부 로드
            settings = config.get("settings", {})
            self._apply_source_boost = settings.get("apply_source_boost", True)

            logger.info(f"Loaded {len(self._report_source_priority)} priority report sources")

        except Exception as e:
            logger.debug(f"Could not load report source priority config: {e}")
            self._apply_source_boost = True

    def _check_report_source_priority(self, item: ContentItem) -> float:
        """
        리포트 소스 우선순위 확인 및 가중치 반환

        Args:
            item: 콘텐츠 항목

        Returns:
            매칭된 소스의 가중치 (매칭 없으면 0.0)
        """
        if not self._apply_source_boost or not self._report_source_priority:
            return 0.0

        # 아이템 소스 정보
        item_source = item.source or ""
        item_broker = item.extra_data.get("broker", "")
        item_title = item.title or ""

        best_weight = 0.0
        best_source = None

        for source_config in self._report_source_priority:
            source_name = source_config["name"]
            report_type = source_config["report_type"]
            weight = source_config["weight"]

            # 소스명 매칭 (소스 또는 브로커에서)
            if source_name in item_source or source_name in item_broker:
                # 리포트 타입 매칭 (있는 경우)
                if report_type:
                    if report_type.lower() in item_title.lower():
                        if weight > best_weight:
                            best_weight = weight
                            best_source = source_config
                else:
                    # 타입 지정 없으면 소스만 매칭
                    if weight > best_weight:
                        best_weight = weight
                        best_source = source_config

        # 매칭된 소스 정보 저장
        if best_source:
            item.extra_data["priority_report_source"] = {
                "name": best_source["name"],
                "report_type": best_source["report_type"],
            }
            item.extra_data["is_priority_source"] = True

        return best_weight

    def score_item(self, item: ContentItem) -> float:
        """
        단일 항목 중요도 점수 계산

        Args:
            item: 콘텐츠 항목

        Returns:
            중요도 점수 (0.0 ~ 1.0)
        """
        score = 0.5  # 기본 점수

        # 키워드 기반 점수 조정
        text = f"{item.title} {item.description or ''}"
        text_lower = text.lower()

        # 커버드콜/배당 뉴스 체크 (최최우선 가중치) - 사전 컴파일된 패턴 사용
        if self._check_keywords(text_lower, self.COVERED_CALL_KEYWORDS, "covered_call"):
            score += ImportanceThresholds.COVERED_CALL_WEIGHT
            item.extra_data["is_covered_call"] = True

        # 산업 키워드 (최우선 가중치)
        if self._check_keywords(text_lower, self.INDUSTRY_KEYWORDS, "industry"):
            score += ImportanceThresholds.INDUSTRY_WEIGHT

        # 중요 키워드
        if self._check_keywords(text_lower, self.HIGH_IMPORTANCE_KEYWORDS, "high"):
            score += ImportanceThresholds.HIGH_KEYWORD_WEIGHT

        # 일반 키워드
        if self._check_keywords(text_lower, self.MEDIUM_IMPORTANCE_KEYWORDS, "medium"):
            score += ImportanceThresholds.MEDIUM_KEYWORD_WEIGHT

        # 우선순위 기반 조정
        if item.priority == Priority.HIGH:
            score += ImportanceThresholds.HIGH_PRIORITY_WEIGHT
        elif item.priority == Priority.LOW:
            score += ImportanceThresholds.LOW_PRIORITY_WEIGHT

        # 언론사 가중치 적용 (사용자 선호도 반영)
        source_weight = self.SOURCE_WEIGHTS.get(item.source, 0.0)
        score += source_weight

        # 우선 기자 가중치 적용 (최우선시)
        journalist_weight = self._check_journalist_priority(text, item)
        score += journalist_weight

        # 우선 애널리스트 가중치 적용
        analyst_weight = self._check_analyst_priority(text, item)
        score += analyst_weight

        # 우선 키워드 가중치 적용 (퀄테스트, 캐파, 증설, 설비투자, HBM, AI반도체 등)
        keyword_weight = self._check_keyword_priority(text, item)
        score += keyword_weight

        # 우선 리포트 소스 가중치 적용 (SK증권 Morning Brief, 네이버 시황정보 등)
        source_weight = self._check_report_source_priority(item)
        score += source_weight

        # 점수 범위 제한
        score = max(0.0, min(1.0, score))

        return round(score, 2)

    def score_batch(self, items: list[ContentItem]) -> list[ContentItem]:
        """
        배치 중요도 점수 계산

        Args:
            items: 콘텐츠 항목 리스트

        Returns:
            점수가 업데이트된 항목 리스트
        """
        for item in items:
            item.importance_score = self.score_item(item)

            # 점수에 따라 우선순위 업데이트
            if item.importance_score >= ImportanceThresholds.HIGH_PRIORITY:
                item.priority = Priority.HIGH
            elif item.importance_score >= ImportanceThresholds.MEDIUM_PRIORITY:
                item.priority = Priority.MEDIUM
            else:
                item.priority = Priority.LOW

        return items

    def ai_score_item(self, item: ContentItem) -> Optional[dict]:
        """
        AI 기반 상세 중요도 평가

        Returns:
            {
                "score": 0.0-1.0,
                "reason": "평가 이유",
                "category": "긴급/중요/일반/참고"
            }
        """
        prompt = f"""다음 금융 뉴스/콘텐츠의 투자자 관점 중요도를 평가해주세요:

제목: {item.title}
출처: {item.source}
내용: {item.description[:500] if item.description else '없음'}

다음 JSON 형식으로 응답해주세요:
{{
    "score": 0.0에서 1.0 사이의 중요도 점수 (숫자만),
    "reason": "이 점수를 부여한 이유 (1문장)",
    "category": "긴급/중요/일반/참고 중 하나"
}}

평가 기준:
- 0.8 이상: 긴급 - 즉각적인 시장 영향 예상
- 0.6-0.8: 중요 - 투자 결정에 영향을 줄 수 있음
- 0.4-0.6: 일반 - 참고할 만한 정보
- 0.4 미만: 참고 - 배경 지식 수준"""

        result = self.client.generate_json(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=300,
        )

        return result

    def filter_by_importance(
        self,
        items: list[ContentItem],
        min_score: float = ImportanceThresholds.MIN_SCORE,
    ) -> list[ContentItem]:
        """
        중요도 기준 필터링

        Args:
            items: 콘텐츠 항목 리스트
            min_score: 최소 중요도 점수

        Returns:
            필터링된 항목 리스트
        """
        # 점수 계산
        scored_items = self.score_batch(items)

        # 필터링 및 정렬
        filtered = [item for item in scored_items if item.importance_score >= min_score]
        filtered.sort(key=lambda x: x.importance_score, reverse=True)

        logger.info(f"Filtered {len(filtered)}/{len(items)} items by importance (min: {min_score})")

        return filtered


# 전역 인스턴스
importance_scorer = ImportanceScorer()
