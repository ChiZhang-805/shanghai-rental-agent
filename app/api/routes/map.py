import json
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.agents.rental_recommendation_agent import RentalRecommendationAgent
from app.api.deps import get_db
from app.config import get_settings
from app.schemas.rental import RentalRecommendationRequest, RentalRecommendationResponse

router = APIRouter(tags=["map"])


@router.post("/api/map/rental-recommendations", response_model=RentalRecommendationResponse)
async def map_rental_recommendations(
    request: RentalRecommendationRequest,
    session: Session = Depends(get_db),
) -> RentalRecommendationResponse:
    return await RentalRecommendationAgent().recommend(request, session=session)


@router.get("/map", response_class=HTMLResponse)
def map_page() -> HTMLResponse:
    settings = get_settings()
    html = Path("app/templates/map.html").read_text(encoding="utf-8")
    html = html.replace("{{ amap_js_api_key_json }}", json.dumps(settings.amap_js_api_key))
    html = html.replace("{{ amap_js_security_code_json }}", json.dumps(settings.amap_js_security_code))
    return HTMLResponse(html)
