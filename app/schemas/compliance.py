from pydantic import BaseModel, Field


class ComplianceResult(BaseModel):
    allowed: bool
    risk_level: str = "low"
    needs_human: bool = False
    violations: list[str] = Field(default_factory=list)
    safe_rewrite: str | None = None
    reason: str = ""

