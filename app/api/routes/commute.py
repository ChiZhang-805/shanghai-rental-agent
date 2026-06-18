from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.key_overrides import request_settings_overrides
from app.config import temporary_settings_override
from app.schemas.commute import CommuteEstimateRequest, CommuteEstimateResponse
from app.schemas.rental import AnchorInput
from app.services.amap_service import AmapService
from app.services.city_guard import CityGuard
from app.services.commute_service import CommuteService

router = APIRouter(prefix="/api/commute", tags=["commute"])


@router.post("/estimate", response_model=CommuteEstimateResponse)
async def estimate_commute(
    request: CommuteEstimateRequest,
    session: Session = Depends(get_db),
    key_overrides: dict[str, str] = Depends(request_settings_overrides),
) -> CommuteEstimateResponse:
    with temporary_settings_override(key_overrides):
        guard = CityGuard()
        guard.assert_request_allowed(request.city)
        if request.origin.lng is None or request.origin.lat is None:
            if not request.origin.address:
                return CommuteEstimateResponse(
                    routes=[],
                    unavailable_reason="origin 必须提供上海内坐标或可地理编码的上海地址；不会编造起点坐标。",
                )
            geocode = await AmapService(city_guard=guard).geocode(request.origin.address, city=request.city)
            if geocode.status != "ok" or geocode.lng is None or geocode.lat is None:
                return CommuteEstimateResponse(
                    routes=[],
                    unavailable_reason=geocode.message or "origin 地址暂不可地理编码，路线不可用。",
                )
            request.origin.lng = geocode.lng
            request.origin.lat = geocode.lat
        guard.assert_point_in_shanghai(lng=request.origin.lng, lat=request.origin.lat, label="通勤起点")
        anchor = AnchorInput(
            label=request.destination.label or "目的地",
            address=request.destination.address,
            lng=request.destination.lng,
            lat=request.destination.lat,
        )
        candidate = {
            "id": "origin",
            "title": request.origin.label or "候选点",
            "city": "上海",
            "lng": request.origin.lng,
            "lat": request.origin.lat,
        }
        routes = await CommuteService(city_guard=guard).batch_estimate(
            [candidate],
            [anchor],
            request.modes,
            session=session,
        )
        summaries = routes.get("origin", [])
        unavailable = None
        if summaries and all(route.route_status != "ok" for route in summaries):
            unavailable = "未取得可用高德路线结果，route_status 已标记为 unavailable/error。"
        return CommuteEstimateResponse(routes=summaries, unavailable_reason=unavailable)
