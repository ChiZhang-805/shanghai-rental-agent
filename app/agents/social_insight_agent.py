from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.schemas.social_insight import SocialInsightRequest, SocialInsightResponse
from app.services.social_insight_service import SocialInsightService


class SocialInsightAgent(BaseAgent):
    name = "social_insight_agent"

    def __init__(
        self,
        *,
        social_insight_service: SocialInsightService | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.social_insight_service = social_insight_service or SocialInsightService(self.openai_service)

    def extract(
        self,
        request: SocialInsightRequest,
        *,
        session: Session | None = None,
    ) -> SocialInsightResponse:
        if request.user_context:
            self.city_guard.assert_request_allowed(request.user_context)
        return self.social_insight_service.extract(request, session=session)
