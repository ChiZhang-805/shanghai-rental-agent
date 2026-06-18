from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.marketing_agent import MarketingAgent
from app.api.deps import get_db
from app.schemas.marketing import MarketingGenerateRequest, MarketingGenerateResponse

router = APIRouter(prefix="/api/marketing", tags=["marketing"])


@router.post("/generate", response_model=MarketingGenerateResponse)
def generate_marketing(
    request: MarketingGenerateRequest, session: Session = Depends(get_db)
) -> MarketingGenerateResponse:
    return MarketingAgent().generate(
        listing=request.listing,
        listing_id=request.listing_id,
        channel=request.channel,
        tone=request.tone,
        session=session,
    )

