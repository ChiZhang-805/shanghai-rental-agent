from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.schemas.policy import PolicyAnswer
from app.services.policy_service import PolicyChunkRecord, PolicyService


class PolicyAgent(BaseAgent):
    name = "policy_agent"

    def __init__(self, *, policy_service: PolicyService | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.policy_service = policy_service or PolicyService(city_guard=self.city_guard)

    def answer(
        self,
        question: str,
        *,
        session: Session | None = None,
        chunks: list[PolicyChunkRecord] | None = None,
    ) -> PolicyAnswer:
        return self.policy_service.answer(question, session=session, chunks=chunks)

