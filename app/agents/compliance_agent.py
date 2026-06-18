from typing import Any

from app.agents.base import BaseAgent
from app.schemas.compliance import ComplianceResult
from app.services.compliance_service import ComplianceService


class ComplianceAgent(BaseAgent):
    name = "compliance_agent"

    def __init__(self, *, compliance_service: ComplianceService | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.compliance_service = compliance_service or ComplianceService(self.city_guard)

    def check(self, text: str, *, listing: dict[str, Any] | None = None) -> ComplianceResult:
        rule_result = self.compliance_service.evaluate(text, listing=listing)
        if rule_result.violations or not self.openai_service.is_configured:
            return rule_result

        prompt = (
            "你是上海房地产公司合规审查 Agent。请只输出 JSON，字段必须符合 schema。"
            "业务只服务上海，不得承诺学区、入学、落户、贷款审批、涨价、收益，"
            "不得协助伪造材料。待审查文本：\n"
            f"{text}"
        )
        data = self.openai_service.generate_json(
            prompt=prompt,
            schema_model=ComplianceResult,
            schema_name="compliance_result",
            fallback=rule_result.model_dump(),
        )
        return ComplianceResult.model_validate(data)

