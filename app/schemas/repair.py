from pydantic import BaseModel, Field


class RepairTriageRequest(BaseModel):
    description: str
    image_path: str | None = None


class RepairTriageResponse(BaseModel):
    issue_type: str
    severity: str
    summary: str
    immediate_actions: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list)
    ticket_title: str
    ticket_description: str
    needs_human: bool
    risk_flags: list[str] = Field(default_factory=list)
    ticket_id: int | None = None

