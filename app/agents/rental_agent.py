from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.policy_agent import PolicyAgent


class RentalAgent(BaseAgent):
    name = "rental_agent"

    def __init__(self, *, policy_agent: PolicyAgent | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.policy_agent = policy_agent or PolicyAgent(
            city_guard=self.city_guard, openai_service=self.openai_service
        )

    def handle(self, message: str, *, session: Session | None = None) -> dict:
        self.city_guard.assert_request_allowed(message)
        if any(keyword in message for keyword in ["备案", "核验", "合同", "押金", "群租"]):
            policy = self.policy_agent.answer(message, session=session)
            return policy.model_dump()
        return {
            "answer": "租赁流程建议按上海房源核验、委托确认、合同条款核对、租赁备案材料准备和交接验收推进。",
            "needs_human": False,
        }

