from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.listing_agent import ListingAgent
from app.api.deps import get_db
from app.schemas.listings import ListingSearchRequest, ListingSearchResponse

router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.post("/search", response_model=ListingSearchResponse)
def search_listings(
    request: ListingSearchRequest, session: Session = Depends(get_db)
) -> ListingSearchResponse:
    return ListingAgent().search(request, session=session)

