import sys
import warnings
from collections.abc import Generator
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app


def _no_db() -> Generator[Any, None, None]:
    yield None


def main() -> None:
    app.dependency_overrides[get_db] = _no_db
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200, health.text
    assert health.json()["city"] == "上海"

    outside = client.post("/api/chat", json={"message": "帮我推荐苏州园区的房子"})
    assert outside.status_code == 200, outside.text
    assert outside.json()["intent"] == "out_of_scope"

    gas = client.post("/api/repair/triage", json={"description": "厨房有燃气异味"})
    assert gas.status_code == 200, gas.text
    assert gas.json()["severity"] == "emergency"
    assert gas.json()["needs_human"] is True

    marketing = client.post(
        "/api/marketing/generate",
        json={
            "channel": "朋友圈",
            "listing": {
                "listing_code": "SH-DEMO-SMOKE",
                "city": "上海",
                "district": "浦东",
                "community_name": "张江示例苑",
                "title": "张江核验两房",
                "purpose": "sale",
                "rooms": 2,
                "area_sqm": 88,
                "sale_price_total": 7200000,
                "rent_price_monthly": None,
                "verification_status": "verified",
                "entrusted_status": "active",
                "listing_status": "active",
            },
        },
    )
    assert marketing.status_code == 200, marketing.text
    assert marketing.json()["allowed"] is True

    map_page = client.get("/map")
    assert map_page.status_code == 200, map_page.text
    assert "上海租房地图推荐" in map_page.text

    rental = client.post(
        "/api/rental/recommend",
        json={"query": "我在张江上班，预算5500，想租一室户", "allow_demo_data": True},
    )
    assert rental.status_code == 200, rental.text
    rental_body = rental.json()
    assert rental_body["mode"] in {"demo_listing_mode", "area_mode"}
    assert "map_layers" in rental_body

    print("Smoke test passed.")


if __name__ == "__main__":
    main()
