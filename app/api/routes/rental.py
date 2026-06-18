from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.rental_recommendation_agent import RentalRecommendationAgent
from app.api.deps import get_db
from app.schemas.rental import RentalRecommendationRequest, RentalRecommendationResponse

router = APIRouter(prefix="/api/rental", tags=["rental"])


@router.post("/recommend", response_model=RentalRecommendationResponse)
async def recommend_rental(
    request: RentalRecommendationRequest,
    session: Session = Depends(get_db),
) -> RentalRecommendationResponse:
    return await RentalRecommendationAgent().recommend(request, session=session)

