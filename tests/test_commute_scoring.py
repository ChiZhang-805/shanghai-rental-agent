from app.schemas.commute import CommuteRouteSummary
from app.schemas.rental import RentalPreferenceWeights
from app.services.rental_scoring_service import RentalScoringService


def test_budget_score() -> None:
    scoring = RentalScoringService()
    assert scoring.budget_score(4500, 5500) == 100.0
    assert scoring.budget_score(5500, 5500) == 75.0
    assert scoring.budget_score(7000, 5500) == 20.0


def test_commute_and_transit_scores() -> None:
    scoring = RentalScoringService()
    assert scoring.commute_duration_score(30, 45) == 100.0
    assert scoring.commute_duration_score(None, 45) == 30.0
    assert scoring.commute_penalty(3, 1200) > 0
    assert scoring.transit_access_score(450) == 100.0
    assert scoring.transit_access_score(1500) == 45.0


def test_total_score_contains_breakdown() -> None:
    scoring = RentalScoringService()
    route = CommuteRouteSummary(
        anchor_label="公司",
        mode="transit",
        duration_min=35,
        distance_m=9000,
        transfers=1,
        walking_distance_m=600,
        route_status="ok",
    )
    total, breakdown, risk_notes = scoring.total_score(
        item={
            "rent_monthly": 5200,
            "metro_distance_m": 600,
            "is_demo": True,
            "is_verified": False,
            "status": "available",
            "last_seen_at": None,
        },
        routes=[route],
        budget=5500,
        min_rent=None,
        max_rent=None,
        max_commute_min=45,
        anchor_weights={"公司": 1.0},
        weights=RentalPreferenceWeights(),
    )
    assert total > 0
    assert set(breakdown) == {"commute", "budget", "transit_access", "listing_quality", "amenities", "risk"}
    assert risk_notes


def test_total_score_normalizes_extreme_weights() -> None:
    scoring = RentalScoringService()
    total, _, _ = scoring.total_score(
        item={
            "rent_monthly": 5000,
            "metro_distance_m": 400,
            "is_demo": False,
            "is_verified": True,
            "status": "available",
            "last_seen_at": "2026-01-01T00:00:00",
        },
        routes=[],
        budget=5500,
        min_rent=None,
        max_rent=None,
        max_commute_min=45,
        anchor_weights={},
        weights=RentalPreferenceWeights(
            commute=1,
            budget=1,
            transit_access=1,
            listing_quality=1,
            amenities=1,
            risk=1,
        ),
    )
    assert 0 <= total <= 100
