from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.rental_recommendation_agent import RentalRecommendationAgent
from app.api.deps import get_db
from app.api.key_overrides import request_settings_overrides
from app.config import temporary_settings_override
from app.schemas.rental import RentalRecommendationRequest, RentalRecommendationResponse

router = APIRouter(prefix="/api/rental", tags=["rental"])


@router.post("/recommend", response_model=RentalRecommendationResponse)
async def recommend_rental(
    request: RentalRecommendationRequest,
    session: Session = Depends(get_db),
    key_overrides: dict[str, str] = Depends(request_settings_overrides),
) -> RentalRecommendationResponse:
    with temporary_settings_override(key_overrides):
        return await RentalRecommendationAgent().recommend(request, session=session)
