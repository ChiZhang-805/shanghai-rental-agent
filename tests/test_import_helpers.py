from app.services.city_guard import CityGuard
from scripts.import_rental_listings_csv import _normalize_district as normalize_listing_district
from scripts.seed_demo_rental_listings import _normalize_district as normalize_demo_listing_district
from scripts.seed_shanghai_geo_data import _normalize_district as normalize_area_district


def test_import_helpers_normalize_pudong_new_area() -> None:
    guard = CityGuard()

    assert normalize_listing_district("浦东新区", guard, "listing-1") == "浦东"
    assert normalize_demo_listing_district("上海市浦东新区", guard, "demo-1") == "浦东"
    assert normalize_area_district("浦东新区", guard, "张江高科周边") == "浦东"
