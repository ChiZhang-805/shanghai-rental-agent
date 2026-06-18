from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.schemas.commute import CommuteMode, CommuteRouteSummary
from app.schemas.rental import AnchorInput
from app.services.commute_service import CommuteService
from app.services.rental_scoring_service import RentalScoringService


class CommuteAgent(BaseAgent):
    name = "commute_agent"

    def __init__(
        self,
        *,
        commute_service: CommuteService | None = None,
        scoring_service: RentalScoringService | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.commute_service = commute_service or CommuteService(city_guard=self.city_guard)
        self.scoring_service = scoring_service or RentalScoringService()

    async def analyze(
        self,
        *,
        candidates: list[dict[str, Any]],
        anchors: list[AnchorInput],
        modes: list[CommuteMode],
        max_commute_min: int,
        session: Session | None = None,
    ) -> dict[str, dict[str, Any]]:
        routes_by_candidate = await self.commute_service.batch_estimate(
            candidates,
            anchors,
            modes,
            session=session,
        )
        anchor_weights = {anchor.label: anchor.weight for anchor in anchors}
        result: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            candidate_id = str(candidate["id"])
            routes: list[CommuteRouteSummary] = routes_by_candidate.get(candidate_id, [])
            commute_score = self.scoring_service.commute_score_for_routes(
                routes, max_commute_min, anchor_weights
            )
            result[candidate_id] = {"routes": routes, "commute_score": commute_score}
        return result

