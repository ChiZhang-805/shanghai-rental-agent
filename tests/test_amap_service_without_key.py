import asyncio

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.api.routes import commute as commute_route
from app.api.routes.commute import estimate_commute
from app.schemas.commute import CommuteEstimateRequest, CoordinatePoint
from app.schemas.geo import GeocodeResponse
from app.services.amap_service import AmapService


def test_amap_service_without_key_returns_unavailable() -> None:
    service = AmapService(Settings(amap_web_service_key="", amap_enable_live=True))
    geocode = asyncio.run(service.geocode("张江高科"))
    assert geocode.status == "unavailable"
    route = asyncio.run(service.route(121.598, 31.207, 121.4737, 31.2304))
    assert route.route_status == "unavailable"


def test_commute_endpoint_origin_address_without_key_returns_unavailable(monkeypatch) -> None:
    class FakeAmapService:
        def __init__(self, *args, **kwargs) -> None:
            return None

        async def geocode(self, address: str, city: str = "上海") -> GeocodeResponse:
            return GeocodeResponse(address=address, city=city, status="unavailable", message="no key")

    monkeypatch.setattr(commute_route, "AmapService", FakeAmapService)
    response = asyncio.run(
        estimate_commute(
            CommuteEstimateRequest(
                origin=CoordinatePoint(label="起点", address="上海 张江高科"),
                destination=CoordinatePoint(label="终点", lng=121.4737, lat=31.2304),
            ),
            session=None,
        )
    )
    assert response.routes == []
    assert response.unavailable_reason


def test_amap_route_without_duration_is_unavailable() -> None:
    route = AmapService()._parse_route(
        {"route": {"paths": [{"distance": "1200", "steps": []}]}},
        mode="walking",
        anchor_label="公司",
    )

    assert route.route_status == "unavailable"
    assert route.duration_min is None


def test_amap_polyline_parser_accepts_nested_v5_shapes() -> None:
    route = AmapService()._parse_route(
        {
            "route": {
                "paths": [
                    {
                        "duration": "600",
                        "distance": "1200",
                        "steps": [
                            {"polyline": {"polyline": "121.1,31.1;121.2,31.2"}},
                            {"polyline": [{"polyline": "121.2,31.2;121.3,31.3"}]},
                        ],
                    }
                ]
            }
        },
        mode="walking",
        anchor_label="公司",
    )

    assert route.route_status == "ok"
    assert route.route_geojson
    assert route.route_geojson["coordinates"][-1] == [121.3, 31.3]


def test_commute_request_rejects_empty_modes() -> None:
    with pytest.raises(ValidationError):
        CommuteEstimateRequest(
            origin=CoordinatePoint(label="起点", lng=121.598, lat=31.207),
            destination=CoordinatePoint(label="终点", lng=121.4737, lat=31.2304),
            modes=[],
        )
