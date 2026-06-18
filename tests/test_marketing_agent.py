from app.agents.marketing_agent import MarketingAgent


def test_marketing_rejects_unverified_listing() -> None:
    response = MarketingAgent().generate(
        listing={
            "listing_code": "SH-MISSING",
            "city": "上海",
            "district": "闵行",
            "community_name": "七宝花园",
            "title": "七宝两房",
            "purpose": "rent",
            "rooms": 2,
            "area_sqm": 76,
            "sale_price_total": None,
            "rent_price_monthly": 6500,
            "verification_status": "missing",
            "entrusted_status": "active",
            "listing_status": "active",
        },
        channel="朋友圈",
    )
    assert response.allowed is False
    assert "未核验" in response.refusal_reason

