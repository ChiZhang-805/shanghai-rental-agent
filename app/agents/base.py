from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.city_guard import CityGuard
from app.services.openai_service import OpenAIService


@dataclass
class AgentContext:
    session: Session | None = None


class BaseAgent:
    name = "base"

    def __init__(
        self,
        *,
        city_guard: CityGuard | None = None,
        openai_service: OpenAIService | None = None,
    ) -> None:
        self.city_guard = city_guard or CityGuard()
        self.openai_service = openai_service or OpenAIService()

