import re
from typing import Any

from app.schemas.compliance import ComplianceResult
from app.services.city_guard import CityGuard


class ComplianceService:
    def __init__(self, city_guard: CityGuard | None = None) -> None:
        self.city_guard = city_guard or CityGuard()

    def evaluate(self, text: str, *, listing: dict[str, Any] | None = None) -> ComplianceResult:
        violations: list[str] = []
        needs_human = False
        risk_level = "low"

        city_result = self.city_guard.check_request(text)
        if not city_result.allowed:
            violations.append("outside_shanghai")
            risk_level = "high"

        if self._has(text, r"伪造|假社保|代办社保|伪造社保|伪造个税|假流水|包装流水|伪造居住证|伪造合同|伪造核验码"):
            violations.append("forged_materials")
            risk_level = "high"

        if self._has(text, r"包上|保证入学|确保入学|学区.*保证|承诺.*学校|落户.*保证|保证落户"):
            violations.append("school_or_settlement_promise")
            risk_level = "high"

        if self._has(text, r"稳赚|稳赚不赔|保证涨|一定涨|必涨|固定收益|保收益|包租回报|贷款.*包过|保证贷款"):
            violations.append("return_or_loan_promise")
            risk_level = "high"

        if self._has(text, r"群租|隔断房|打隔断|违规分租"):
            violations.append("group_rental_risk")
            risk_level = max(risk_level, "medium", key=self._risk_rank)

        if self._has(text, r"合同争议|税费争议|定金争议|定金不退|产权|抵押|查封|户口|法律责任|起诉"):
            violations.append("legal_or_tax_dispute")
            needs_human = True
            risk_level = "high"

        if self._has(text, r"燃气|煤气|漏电|电路|消防|着火|火灾|严重漏水|水漫|冒烟"):
            violations.append("safety_risk")
            needs_human = True
            risk_level = "high"

        if self._has(text, r"身份证号|银行卡号|完整手机号|征信报告"):
            violations.append("privacy_risk")
            needs_human = True
            risk_level = max(risk_level, "medium", key=self._risk_rank)

        if listing is not None and self._looks_like_marketing(text):
            if listing.get("city") != "上海":
                violations.append("outside_shanghai_listing")
                risk_level = "high"
            if listing.get("verification_status") != "verified":
                violations.append("unverified_listing_marketing")
                risk_level = "high"
            if listing.get("entrusted_status") != "active":
                violations.append("inactive_entrustment_marketing")
                risk_level = "high"

        blocking = {
            "outside_shanghai",
            "outside_shanghai_listing",
            "forged_materials",
            "school_or_settlement_promise",
            "return_or_loan_promise",
            "unverified_listing_marketing",
            "inactive_entrustment_marketing",
            "group_rental_risk",
        }
        allowed = not any(violation in blocking for violation in violations)
        safe_rewrite = self._safe_rewrite(text, violations)
        reason = "通过规则合规检查。" if allowed and not violations else "命中合规风险：" + ", ".join(violations)
        return ComplianceResult(
            allowed=allowed,
            risk_level=risk_level,
            needs_human=needs_human,
            violations=violations,
            safe_rewrite=safe_rewrite,
            reason=reason,
        )

    @staticmethod
    def _has(text: str, pattern: str) -> bool:
        return re.search(pattern, text, flags=re.IGNORECASE) is not None

    @staticmethod
    def _looks_like_marketing(text: str) -> bool:
        return any(keyword in text for keyword in ["文案", "朋友圈", "小红书", "公众号", "视频号", "标题", "带看话术", "发布"])

    @staticmethod
    def _risk_rank(value: str) -> int:
        return {"low": 0, "medium": 1, "high": 2}.get(value, 0)

    @staticmethod
    def _safe_rewrite(text: str, violations: list[str]) -> str | None:
        if not violations:
            return None
        rewritten = text
        replacements = {
            "包上": "周边教育资源请以主管部门当年公示为准",
            "保证入学": "入学政策请以教育主管部门审核为准",
            "稳赚": "投资收益存在不确定性",
            "稳赚不赔": "投资收益存在不确定性",
            "保证涨": "价格走势不作承诺",
            "必涨": "价格走势不作承诺",
            "贷款包过": "贷款审批以银行审核为准",
        }
        for source, target in replacements.items():
            rewritten = rewritten.replace(source, target)
        return rewritten

