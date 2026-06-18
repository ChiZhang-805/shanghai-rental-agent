import pytest

from app.services.city_guard import CityGuard, CityGuardError


def test_outside_shanghai_requests_are_rejected() -> None:
    guard = CityGuard()
    with pytest.raises(CityGuardError):
        guard.assert_request_allowed("帮我推荐昆山花桥的房子")
    with pytest.raises(CityGuardError):
        guard.assert_request_allowed("分析一下苏州园区的租赁市场")


def test_shanghai_districts_are_allowed() -> None:
    guard = CityGuard()
    assert guard.assert_request_allowed("我想看浦东张江附近两房").allowed is True
    assert guard.assert_request_allowed("静安南京西路租房").allowed is True
    assert guard.normalize_districts("浦东新区和静安区") == ["静安", "浦东"] or guard.normalize_districts(
        "浦东新区和静安区"
    ) == ["浦东", "静安"]


def test_coordinate_guard_rejects_nearby_non_shanghai_points() -> None:
    guard = CityGuard()
    guard.assert_point_in_shanghai(lng=121.4737, lat=31.2304, label="人民广场")
    guard.assert_point_in_shanghai(lng=121.237, lat=31.391, label="嘉定北")
    guard.assert_point_in_shanghai(lng=121.931, lat=30.895, label="临港滴水湖")
    guard.assert_point_in_shanghai(lng=121.341, lat=30.724, label="金山城市沙滩")
    with pytest.raises(CityGuardError):
        guard.assert_point_in_shanghai(lng=121.09, lat=31.30, label="昆山花桥")
    with pytest.raises(CityGuardError):
        guard.assert_point_in_shanghai(lng=121.13, lat=31.45, label="太仓")
    with pytest.raises(CityGuardError):
        guard.assert_point_in_shanghai(lng=120.92, lat=30.84, label="嘉善")


def test_unknown_district_raises_city_guard_error() -> None:
    with pytest.raises(CityGuardError):
        CityGuard().validate_listing_rows([{"city": "上海", "district": "火星"}])
