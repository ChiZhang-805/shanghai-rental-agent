from fastapi import APIRouter, Depends

from app.api.key_overrides import request_settings_overrides
from app.config import temporary_settings_override
from app.schemas.geo import GeocodeRequest, GeocodeResponse
from app.services.amap_service import AmapService

router = APIRouter(prefix="/api/geo", tags=["geo"])


@router.post("/geocode", response_model=GeocodeResponse)
async def geocode(
    request: GeocodeRequest,
    key_overrides: dict[str, str] = Depends(request_settings_overrides),
) -> GeocodeResponse:
    with temporary_settings_override(key_overrides):
        return await AmapService().geocode(request.address, city=request.city)
