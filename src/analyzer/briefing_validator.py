"""
브리핑 검증 모듈
AI가 생성한 브리핑 내용이 실제 수집된 데이터와 일치하는지 검증
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from src.collectors.base import ContentItem
from src.utils.logger import logger


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool                          # 전체 검증 통과 여부
    score: float                            # 검증 점수 (0.0 ~ 1.0)
    errors: list[str] = field(default_factory=list)      # 심각한 오류 (차단 사유)
    warnings: list[str] = field(default_factory=list)    # 경고 (정보용)
    details: dict = field(default_factory=dict)          # 상세 검증 결과


class BriefingValidator:
    """브리핑 검증기 (키워드/출처 검증 - 수치는 AI가 생성하지 않으므로 검증 불필요)"""

    # 검증 임계값
    MIN_KEYWORD_MATCH = 0.5       # 최소 키워드 매칭률 (50%)
    MIN_PASS_SCORE = 0.7          # 최소 통과 점수

    # 회사/종목명 추출 패턴
    COMPANY_PATTERN = re.compile(
        r"(삼성전자|SK하이닉스|현대차|기아|LG에너지솔루션|삼성바이오|셀트리온|"
        r"NAVER|네이버|카카오|삼성SDI|포스코|현대모비스|LG화학|신한지주|KB금융|"
        r"하나금융|우리금융|삼성물산|SK이노베이션|LG전자|한국전력|"
        r"엔비디아|NVIDIA|테슬라|Tesla|애플|Apple|마이크로소프트|Microsoft|"
        r"아마존|Amazon|구글|Google|메타|Meta|AMD|인텔|Intel|TSMC)",
        re.IGNORECASE
    )

    def validate_briefing(
        self,
        briefing_text: str,
        news_items: Optional[list[ContentItem]] = None,
        report_items: Optional[list[ContentItem]] = None,
    ) -> ValidationResult:
        """
        브리핑 내용 종합 검증 (키워드/출처만 검증)

        Args:
            briefing_text: 검증할 브리핑 텍스트 (summary + key_points 등 합친 것)
            news_items: 실제 수집된 뉴스 항목
            report_items: 실제 수집된 리포트 항목

        Returns:
            ValidationResult 객체
        """
        errors = []
        warnings = []
        details = {}
        checks_passed = 0
        total_checks = 0

        # 1. 키워드/회사명 검증 (뉴스에 실제로 있는지)
        if news_items or report_items:
            keyword_result = self._validate_keywords(
                briefing_text, news_items or [], report_items or []
            )
            details["keywords"] = keyword_result

            if keyword_result.get("errors"):
                errors.extend(keyword_result["errors"])
            if keyword_result.get("warnings"):
                warnings.extend(keyword_result["warnings"])

            checks_passed += keyword_result.get("passed", 0)
            total_checks += keyword_result.get("total", 0)

        # 2. 출처 언급 검증
        source_result = self._validate_sources(briefing_text, news_items or [])
        details["sources"] = source_result

        if source_result.get("warnings"):
            warnings.extend(source_result["warnings"])

        # 점수 계산
        score = checks_passed / total_checks if total_checks > 0 else 1.0
        is_valid = len(errors) == 0 and score >= self.MIN_PASS_SCORE

        result = ValidationResult(
            is_valid=is_valid,
            score=round(score, 2),
            errors=errors,
            warnings=warnings,
            details=details,
        )

        # 로깅
        if is_valid:
            logger.info(f"Briefing validation PASSED (score: {score:.2f})")
        else:
            logger.warning(f"Briefing validation FAILED (score: {score:.2f}, errors: {errors})")

        return result

    def _validate_keywords(
        self,
        text: str,
        news_items: list[ContentItem],
        report_items: list[ContentItem],
    ) -> dict:
        """
        브리핑에 언급된 회사/키워드가 실제 뉴스/리포트에 있는지 검증

        Returns:
            {
                "passed": int,
                "total": int,
                "errors": list,
                "warnings": list,
                "mentioned_companies": list,
                "verified_companies": list,
                "unverified_companies": list
            }
        """
        result = {
            "passed": 0,
            "total": 0,
            "errors": [],
            "warnings": [],
            "mentioned_companies": [],
            "verified_companies": [],
            "unverified_companies": [],
        }

        # 브리핑에서 회사명 추출
        mentioned = set(self.COMPANY_PATTERN.findall(text))
        mentioned = {m.upper() if m.isupper() else m for m in mentioned}  # 정규화
        result["mentioned_companies"] = list(mentioned)

        if not mentioned:
            return result

        # 뉴스/리포트에서 회사명 추출
        source_text = ""
        for item in news_items:
            source_text += f" {item.title} {item.description or ''}"
        for item in report_items:
            source_text += f" {item.title} {item.extra_data.get('stock_name', '')}"

        source_companies = set(self.COMPANY_PATTERN.findall(source_text))
        source_companies = {c.upper() if c.isupper() else c for c in source_companies}

        # 검증
        for company in mentioned:
            result["total"] += 1
            # 대소문자 무시 비교
            company_lower = company.lower()
            found = any(c.lower() == company_lower for c in source_companies)

            if found:
                result["passed"] += 1
                result["verified_companies"].append(company)
            else:
                result["unverified_companies"].append(company)
                result["warnings"].append(
                    f"'{company}' - 수집된 뉴스/리포트에서 확인되지 않음"
                )

        # 검증률이 너무 낮으면 에러
        if result["total"] > 0:
            match_rate = result["passed"] / result["total"]
            if match_rate < self.MIN_KEYWORD_MATCH:
                result["errors"].append(
                    f"키워드 검증률 낮음: {result['passed']}/{result['total']} ({match_rate:.0%})"
                )

        return result

    def _validate_sources(self, text: str, news_items: list[ContentItem]) -> dict:
        """
        출처가 적절히 언급되었는지 검증

        Returns:
            {
                "has_sources": bool,
                "source_count": int,
                "warnings": list
            }
        """
        result = {
            "has_sources": False,
            "source_count": 0,
            "warnings": [],
        }

        # 출처 패턴 확인 (괄호 안에 출처)
        source_pattern = re.compile(r"\(([^)]*(?:경제|신문|일보|뉴스|증권|MBC|KBS|SBS|연합)[^)]*)\)")
        found_sources = source_pattern.findall(text)

        result["source_count"] = len(found_sources)
        result["has_sources"] = len(found_sources) > 0

        if not result["has_sources"]:
            result["warnings"].append("브리핑에 출처 언급이 없음 - 출처 명시 권장")

        return result

    def get_briefing_text(self, briefing) -> str:
        """MarketBriefing 객체에서 검증용 텍스트 추출"""
        parts = []

        if hasattr(briefing, "greeting") and briefing.greeting:
            parts.append(briefing.greeting)
        if hasattr(briefing, "summary") and briefing.summary:
            parts.append(briefing.summary)
        if hasattr(briefing, "key_points") and briefing.key_points:
            parts.extend(briefing.key_points)
        if hasattr(briefing, "action_items") and briefing.action_items:
            parts.extend(briefing.action_items)
        if hasattr(briefing, "closing") and briefing.closing:
            parts.append(briefing.closing)

        return " ".join(parts)


# 전역 인스턴스
briefing_validator = BriefingValidator()
