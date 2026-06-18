from fastapi import APIRouter

from app.schemas.geo import GeocodeRequest, GeocodeResponse
from app.services.amap_service import AmapService

router = APIRouter(prefix="/api/geo", tags=["geo"])


@router.post("/geocode", response_model=GeocodeResponse)
async def geocode(request: GeocodeRequest) -> GeocodeResponse:
    return await AmapService().geocode(request.address, city=request.city)

