import asyncio

import pytest
from fastapi.testclient import TestClient

from app.agents.supervisor import SupervisorAgent
from app.main import app
from app.schemas.commute import CommuteRouteSummary
from app.schemas.geo import GeocodeResponse
from app.services.amap_service import AmapService


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
    ) -> list[dict]:
        return [
            {"id": "amap-1", "name": "张江汤臣豪园", "location": "121.598,31.195", "adname": "浦东新区", "address": "晨晖路"},
            {"id": "amap-2", "name": "玉兰香苑", "location": "121.592,31.199", "adname": "浦东新区", "address": "张江路"},
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


def test_agent_page_loads() -> None:
    response = TestClient(app).get("/agent")

    assert response.status_code == 200
    assert "上海租房对话 Agent" in response.text


def test_supervisor_routes_rental_prompt_to_recommendation() -> None:
    assert (
        SupervisorAgent.detect_intent("我在张江高科上班，预算5500，想租一室，通勤45分钟以内")
        == "rental_map_recommendation"
    )


def test_supervisor_routes_no_demo_area_prompt_to_rental_recommendation() -> None:
    message = "不允许 demo 数据，我在漕河泾上班，预算6000，看看适合哪些区域"

    assert SupervisorAgent.detect_intent(message) == "rental_map_recommendation"
    request = SupervisorAgent._rental_request_from_message(message)
    assert request.allow_demo_data is False


def test_chat_response_contains_readable_rental_summary(fake_amap: None) -> None:
    response = asyncio.run(
        SupervisorAgent().handle_async("我在张江高科上班，预算5500，想租一室，通勤45分钟以内")
    )

    assert response.intent == "rental_map_recommendation"
    assert "高德" in response.answer
    assert "总分" not in response.answer
    assert "score_breakdown" not in response.answer
    assert "24 分钟" in response.answer
    assert "demo" not in response.answer
    assert response.data["results"]
    assert all(item["item_type"] == "community" for item in response.data["results"])
    assert all(item["is_demo"] is False for item in response.data["results"])


def test_no_demo_area_prompt_returns_amap_community_candidates(fake_amap: None) -> None:
    response = asyncio.run(
        SupervisorAgent().handle_async("不允许 demo 数据，我在漕河泾上班，预算6000，看看适合哪些区域")
    )

    assert response.intent == "rental_map_recommendation"
    assert response.data["mode"] == "area_mode"
    assert all(item["item_type"] == "community" for item in response.data["results"])
    assert all(item["is_demo"] is False for item in response.data["results"])
    assert "demo" not in response.answer
    assert "高德小区候选" in response.answer
