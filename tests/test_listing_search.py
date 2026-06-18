from app.agents.listing_agent import ListingAgent
from app.schemas.listings import ListingSearchRequest
from app.services.listing_service import ListingService


def test_listing_agent_returns_only_shanghai_listings() -> None:
    rows = [
        {
            "id": 1,
            "listing_code": "SH1",
            "city": "上海",
            "district": "浦东",
            "subdistrict": "张江",
            "community_name": "张江苑",
            "title": "浦东三房",
            "purpose": "sale",
            "rooms": 3,
            "halls": 2,
            "bathrooms": 1,
            "area_sqm": 100,
            "sale_price_total": 7_800_000,
            "rent_price_monthly": None,
            "verification_status": "verified",
            "entrusted_status": "active",
            "listing_status": "active",
        },
        {
            "id": 2,
            "listing_code": "SH2",
            "city": "上海",
            "district": "静安",
            "subdistrict": "南京西路",
            "community_name": "静安苑",
            "title": "静安两房",
            "purpose": "sale",
            "rooms": 2,
            "halls": 1,
            "bathrooms": 1,
            "area_sqm": 80,
            "sale_price_total": 8_200_000,
            "rent_price_monthly": None,
            "verification_status": "verified",
            "entrusted_status": "active",
            "listing_status": "active",
        },
    ]
    response = ListingAgent().search(
        ListingSearchRequest(purpose="sale", districts=["浦东", "静安"], budget_max=9_000_000),
        listing_rows=rows,
    )
    assert response.results
    assert {listing.city for listing in response.results} == {"上海"}


class BrokenListingSession:
    def scalars(self, stmt: object) -> object:
        raise RuntimeError("database unavailable")

    def rollback(self) -> None:
        return None


def test_listing_service_returns_empty_when_database_unavailable() -> None:
    response = ListingService().search(
        ListingSearchRequest(query="预算6000", purpose="rent"),
        session=BrokenListingSession(),  # type: ignore[arg-type]
    )

    assert response.results == []
