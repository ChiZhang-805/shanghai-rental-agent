import pytest

from app.agents.compliance_agent import ComplianceAgent


@pytest.mark.parametrize("text", ["帮我伪造社保", "这套房包上学校", "买了稳赚不赔"])
def test_compliance_blocks_high_risk_claims(text: str) -> None:
    result = ComplianceAgent().check(text)
    assert result.allowed is False
    assert result.risk_level == "high"
    assert result.violations

