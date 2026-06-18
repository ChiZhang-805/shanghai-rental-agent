from app.agents.repair_agent import RepairAgent
from app.config import Settings


def test_repair_agent_marks_gas_smell_emergency_and_human() -> None:
    response = RepairAgent().triage("厨房有燃气异味，灶台附近味道很重")
    assert response.severity == "emergency"
    assert response.needs_human is True
    assert "gas" in response.risk_flags


class FakeOpenAIService:
    is_configured = True
    settings = Settings()

    def analyze_image_json(self, **kwargs):
        raise AssertionError("unsafe image path should not be read")


def test_repair_agent_ignores_image_path_outside_upload_dir() -> None:
    response = RepairAgent(openai_service=FakeOpenAIService()).triage(
        "墙面有点漏水",
        image_path="/etc/passwd",
    )

    assert response.issue_type == "plumbing"
    assert "water_leak" in response.risk_flags


class BrokenRepairSession:
    def __init__(self) -> None:
        self.rolled_back = False

    def add(self, value: object) -> None:
        return None

    def commit(self) -> None:
        raise RuntimeError("database unavailable")

    def refresh(self, value: object) -> None:
        raise AssertionError("refresh should not run after failed commit")

    def rollback(self) -> None:
        self.rolled_back = True


def test_repair_agent_returns_when_persistence_fails() -> None:
    session = BrokenRepairSession()

    response = RepairAgent().triage("墙面有点漏水", session=session)  # type: ignore[arg-type]

    assert response.issue_type == "plumbing"
    assert response.ticket_id is None
    assert session.rolled_back is True
