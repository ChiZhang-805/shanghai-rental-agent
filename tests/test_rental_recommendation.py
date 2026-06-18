import asyncio
from typing import Any

import pytest
from pydantic import ValidationError

from app.agents.rental_recommendation_agent import RentalRecommendationAgent
from app.schemas.commute import CommuteRouteSummary
from app.schemas.geo import GeocodeResponse
from app.schemas.rental import AnchorInput, RentalRecommendationRequest
from app.services.city_guard import CityGuardError
from app.services.amap_service import AmapService
from app.services.rental_data_service import RentalDataService


@pytest.fixture()
def fake_amap(monkeypatch: pytest.MonkeyPatch) -> None:
    async def geocode(self: AmapService, address: str, city: str = "上海") -> GeocodeResponse:
        return GeocodeResponse(address=address, city="上海", district="浦东", lng=121.5968, lat=31.1937, status="ok")

    async def search_communities_around(
        self: AmapService,
        lng: float,
        lat: float,
        *,
        radius_m: int = 5000,
        page_size: int = 25,
        pages: int = 3,
    ) -> list[dict[str, Any]]:
        return [
            {"id": "amap-1", "name": "张江汤臣豪园", "location": "121.598,31.195", "adname": "浦东新区", "address": "晨晖路"},
            {"id": "amap-2", "name": "玉兰香苑", "location": "121.592,31.199", "adname": "浦东新区", "address": "张江路"},
            {"id": "amap-3", "name": "汇智家园", "location": "121.585,31.201", "adname": "浦东新区", "address": "科苑路"},
        ]

    async def route(
        self: AmapService,
        origin_lng: float,
        origin_lat: float,
        destination_lng: float,
        destination_lat: float,
        mode: str = "transit",
        city1: str = "021",
        city2: str = "021",
        anchor_label: str = "目的地",
    ) -> CommuteRouteSummary:
        return CommuteRouteSummary(
            anchor_label=anchor_label,
            mode=mode,
            duration_min=24.0,
            distance_m=1500,
            route_status="ok",
            summary="fake amap route",
        )

    monkeypatch.setattr(AmapService, "live_enabled", property(lambda self: True))
    monkeypatch.setattr(AmapService, "geocode", geocode)
    monkeypatch.setattr(AmapService, "search_communities_around", search_communities_around)
    monkeypatch.setattr(AmapService, "route", route)


def test_demo_listing_mode_is_forced_to_amap_community_candidates(fake_amap: None) -> None:
    response = asyncio.run(
        RentalRecommendationAgent().recommend(
            RentalRecommendationRequest(
                query="我在张江上班，预算5500，想租一室户，通勤45分钟以内",
                anchors=[AnchorInput(label="公司", address="上海 张江")],
                allow_demo_data=True,
            )
        )
    )
    assert response.mode == "area_mode"
    assert response.data_warning
    assert response.results
    assert all(item.item_type == "community" for item in response.results)
    assert all(item.is_demo is False for item in response.results)
    assert response.request_summary["global_demo_listing_count"] == 0
    assert response.map_layers.markers_geojson["features"]
    assert "score_breakdown" in response.results[0].model_dump()


def test_area_mode_when_demo_not_allowed_uses_amap_communities(fake_amap: None) -> None:
    response = asyncio.run(
        RentalRecommendationAgent().recommend(
            RentalRecommendationRequest(
                query="我在张江上班，预算5500，想租一室户，通勤45分钟以内",
                anchors=[AnchorInput(label="公司", address="上海 张江")],
                allow_demo_data=False,
            )
        )
    )
    assert response.mode == "area_mode"
    assert response.data_warning
    assert response.results
    assert all(item.item_type == "community" for item in response.results)
    assert all(item.is_demo is False for item in response.results)


def test_outside_shanghai_rejected() -> None:
    with pytest.raises(CityGuardError):
        asyncio.run(
            RentalRecommendationAgent().recommend(
                RentalRecommendationRequest(query="我在苏州工业园区上班，帮我推荐昆山租房")
            )
        )


def test_demo_request_does_not_load_demo_listings(fake_amap: None) -> None:
    class FakeDataService:
        database_available = True

        def __init__(self) -> None:
            self.listings_loaded = False
            self.demo_counted = False

        def count_available_real_listings(self, session: Any = None) -> int:
            return 3

        def count_demo_listings(self, session: Any = None) -> int:
            self.demo_counted = True
            return 1

        def get_candidate_listings(
            self, request: RentalRecommendationRequest, *, mode: str, session: Any = None
        ) -> list[dict[str, Any]]:
            self.listings_loaded = True
            return []

        def build_community_candidates_from_pois(
            self, pois: list[dict[str, Any]], request: RentalRecommendationRequest
        ) -> list[dict[str, Any]]:
            return [
                {
                    "item_type": "community",
                    "id": "amap-1",
                    "source": "amap_poi_around",
                    "title": "张江汤臣豪园",
                    "city": "上海",
                    "district": "浦东",
                    "community_name": "张江汤臣豪园",
                    "address": "上海浦东张江",
                    "lng": 121.598,
                    "lat": 31.195,
                    "rent_monthly": 5500,
                    "room_rents": {"1": 5500, "2": 8500, "3": 12000},
                    "metro_distance_m": 500,
                    "status": "available",
                    "is_verified": False,
                    "is_demo": False,
                }
            ]

        def get_candidate_areas(
            self, request: RentalRecommendationRequest, *, session: Any = None
        ) -> list[dict[str, Any]]:
            return []

    data_service = FakeDataService()
    response = asyncio.run(
        RentalRecommendationAgent(data_service=data_service).recommend(
            RentalRecommendationRequest(query="我在张江上班，预算5500，想租一室户", allow_demo_data=True)
        )
    )

    assert response.mode == "area_mode"
    assert response.results[0].item_type == "community"
    assert response.results[0].is_demo is False
    assert data_service.listings_loaded is False
    assert data_service.demo_counted is False


def test_required_metro_distance_filters_demo_candidates() -> None:
    rows = RentalDataService().get_candidate_listings(
        RentalRecommendationRequest(rooms=1, require_metro_distance_m=500),
        mode="demo_listing_mode",
    )

    assert rows
    assert all(row["metro_distance_m"] is not None and row["metro_distance_m"] <= 500 for row in rows)


def test_customer_id_schema_matches_integer_model_id() -> None:
    assert RentalRecommendationRequest(customer_id=1).customer_id == 1
    with pytest.raises(ValidationError):
        RentalRecommendationRequest(customer_id="not-an-int")


def test_required_metro_distance_filters_area_candidates() -> None:
    rows = RentalDataService().get_candidate_areas(
        RentalRecommendationRequest(require_metro_distance_m=300)
    )

    assert rows
    assert all(row["metro_distance_m"] == 0 for row in rows)


def test_rental_request_rejects_invalid_ranges_and_empty_modes() -> None:
    with pytest.raises(ValidationError):
        RentalRecommendationRequest(min_rent_monthly=8000, max_rent_monthly=5000)
    with pytest.raises(ValidationError):
        RentalRecommendationRequest(rooms=0)
    with pytest.raises(ValidationError):
        RentalRecommendationRequest(commute_modes=[])


def test_demo_count_uses_csv_fallback_when_db_has_no_demo_rows() -> None:
    class EmptyDemoSession:
        def scalar(self, value: object) -> int:
            return 0

        def rollback(self) -> None:
            raise AssertionError("rollback should not be called")

    service = RentalDataService()

    assert service.count_demo_listings(EmptyDemoSession()) == service.count_demo_listings(None) > 0


def test_demo_candidates_not_loaded_when_demo_not_allowed(fake_amap: None) -> None:
    class FakeDataService:
        database_available = True

        def __init__(self) -> None:
            self.demo_loaded = False
            self.demo_counted = False

        def count_available_real_listings(self, session: Any = None) -> int:
            return 0

        def count_demo_listings(self, session: Any = None) -> int:
            self.demo_counted = True
            return 9

        def get_candidate_listings(
            self, request: RentalRecommendationRequest, *, mode: str, session: Any = None
        ) -> list[dict[str, Any]]:
            if mode == "demo_listing_mode":
                self.demo_loaded = True
            return []

        def get_candidate_areas(
            self, request: RentalRecommendationRequest, *, session: Any = None
        ) -> list[dict[str, Any]]:
            raise AssertionError("area fallback should not be used for amap community recommendations")

        def build_community_candidates_from_pois(
            self, pois: list[dict[str, Any]], request: RentalRecommendationRequest
        ) -> list[dict[str, Any]]:
            return [
                {
                    "item_type": "community",
                    "id": "amap-1",
                    "title": "张江汤臣豪园",
                    "name": "张江汤臣豪园",
                    "source": "amap_poi_around",
                    "city": "上海",
                    "district": "浦东",
                    "community_name": "张江汤臣豪园",
                    "address": "上海浦东张江",
                    "lng": 121.598,
                    "lat": 31.195,
                    "rent_monthly": 5500,
                    "typical_rent": 5500,
                    "room_rents": {"1": 5500, "2": 8500, "3": 12000},
                    "metro_distance_m": 500,
                    "status": "available",
                    "is_verified": False,
                    "is_demo": False,
                }
            ]

    data_service = FakeDataService()
    response = asyncio.run(
        RentalRecommendationAgent(data_service=data_service).recommend(
            RentalRecommendationRequest(query="我在张江上班，预算5500", allow_demo_data=False)
        )
    )

    assert response.mode == "area_mode"
    assert response.results
    assert all(item.item_type == "community" for item in response.results)
    assert all(item.is_demo is False for item in response.results)
    assert data_service.demo_loaded is False
    assert data_service.demo_counted is False
