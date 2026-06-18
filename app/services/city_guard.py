from collections.abc import Iterable
from typing import Any

from app.schemas.common import (
    OUTSIDE_SHANGHAI_CITY_KEYWORDS,
    SHANGHAI_DISTRICTS,
    CityGuardResult,
)

SHANGHAI_LNG_RANGE = (120.85, 122.25)
SHANGHAI_LAT_RANGE = (30.67, 31.90)

SHANGHAI_MAINLAND_POLYGON = [
    (120.85, 30.69),
    (121.02, 30.67),
    (121.28, 30.72),
    (121.56, 30.78),
    (121.82, 30.86),
    (122.02, 31.00),
    (122.02, 31.14),
    (121.90, 31.25),
    (121.72, 31.35),
    (121.50, 31.42),
    (121.33, 31.41),
    (121.18, 31.34),
    (121.14, 31.27),
    (121.01, 31.23),
    (120.88, 31.13),
    (120.85, 30.92),
]
SHANGHAI_CHONGMING_POLYGON = [
    (121.10, 31.49),
    (121.32, 31.43),
    (121.70, 31.45),
    (122.05, 31.54),
    (122.18, 31.67),
    (122.02, 31.82),
    (121.64, 31.88),
    (121.28, 31.80),
    (121.08, 31.64),
]
SHANGHAI_CHANGXING_HENGSHA_POLYGON = [
    (121.52, 31.30),
    (121.88, 31.27),
    (121.92, 31.39),
    (121.55, 31.43),
]
SHANGHAI_JIADING_POLYGON = [
    (121.10, 31.20),
    (121.34, 31.18),
    (121.40, 31.45),
    (121.18, 31.45),
    (121.10, 31.32),
]
SHANGHAI_LINGANG_POLYGON = [
    (121.70, 30.78),
    (122.04, 30.78),
    (122.08, 31.02),
    (121.86, 31.10),
    (121.66, 30.95),
]
SHANGHAI_JINSHAN_POLYGON = [
    (121.00, 30.70),
    (121.45, 30.70),
    (121.48, 30.95),
    (121.02, 30.96),
]
NON_SHANGHAI_JIASHAN_POLYGON = [
    (120.85, 30.72),
    (121.00, 30.72),
    (121.00, 30.98),
    (120.85, 30.98),
]
SHANGHAI_SERVICE_POLYGONS = [
    SHANGHAI_MAINLAND_POLYGON,
    SHANGHAI_CHONGMING_POLYGON,
    SHANGHAI_CHANGXING_HENGSHA_POLYGON,
    SHANGHAI_JIADING_POLYGON,
    SHANGHAI_LINGANG_POLYGON,
    SHANGHAI_JINSHAN_POLYGON,
]
NON_SHANGHAI_EXCLUSION_POLYGONS = [
    NON_SHANGHAI_JIASHAN_POLYGON,
]


class CityGuardError(ValueError):
    def __init__(self, message: str, result: CityGuardResult | None = None) -> None:
        super().__init__(message)
        self.result = result


class CityGuard:
    city = "上海"

    def normalize_districts(self, values: str | Iterable[str] | None) -> list[str]:
        if values is None:
            return []
        if isinstance(values, str):
            haystack = values
            found: list[str] = []
            for district in SHANGHAI_DISTRICTS:
                if district in haystack or f"{district}区" in haystack:
                    found.append(district)
            if "浦东新区" in haystack and "浦东" not in found:
                found.append("浦东")
            return self._dedupe(found)

        normalized: list[str] = []
        for value in values:
            item = value.strip().replace("上海市", "")
            item = item.replace("浦东新区", "浦东")
            if item.endswith("区"):
                item = item[:-1]
            if item.endswith("新区"):
                item = item[:-2]
            if item in SHANGHAI_DISTRICTS:
                normalized.append(item)
        return self._dedupe(normalized)

    def detect_outside_shanghai(self, text: str | None) -> list[str]:
        if not text:
            return []
        cleaned = text
        for local_name in ["苏州河", "南京西路", "南京东路", "北京西路", "北京东路"]:
            cleaned = cleaned.replace(local_name, "")
        return [keyword for keyword in OUTSIDE_SHANGHAI_CITY_KEYWORDS if keyword in cleaned]

    def check_request(self, text: str | None) -> CityGuardResult:
        outside = self.detect_outside_shanghai(text)
        districts = self.normalize_districts(text)
        if outside:
            return CityGuardResult(
                allowed=False,
                districts=districts,
                outside_keywords=outside,
                reason=f"公司只服务上海，不能处理上海以外城市请求：{', '.join(outside)}。",
            )
        return CityGuardResult(allowed=True, districts=districts, reason="上海范围请求。")

    def assert_request_allowed(self, text: str | None) -> CityGuardResult:
        result = self.check_request(text)
        if not result.allowed:
            raise CityGuardError(result.reason, result)
        return result

    def force_listing_filters(self, filters: dict[str, Any]) -> dict[str, Any]:
        city = filters.get("city") or self.city
        if city != self.city:
            raise CityGuardError(f"公司只服务上海，不能使用 city={city!r} 的房源过滤条件。")
        forced = dict(filters)
        forced["city"] = self.city
        forced["districts"] = self.normalize_districts(filters.get("districts"))
        return forced

    def validate_listing_rows(self, rows: Iterable[Any]) -> list[Any]:
        valid_rows: list[Any] = []
        for row in rows:
            city = self._get_value(row, "city")
            district = self._get_value(row, "district")
            if city != self.city:
                raise CityGuardError(f"房源必须限定上海，发现 city={city!r}。")
            normalized = self.normalize_districts([district]) if district else []
            normalized_district = normalized[0] if normalized else None
            if normalized_district not in SHANGHAI_DISTRICTS:
                raise CityGuardError(f"房源行政区不属于上海行政区：{district!r}。")
            valid_rows.append(row)
        return valid_rows

    def assert_point_in_shanghai(
        self,
        *,
        lng: float | None,
        lat: float | None,
        label: str = "地图点",
    ) -> None:
        if lng is None or lat is None:
            raise CityGuardError(f"{label}缺少坐标，不能用于上海地图或通勤计算。")
        if not self.is_point_in_shanghai(lng=lng, lat=lat):
            raise CityGuardError(f"{label}坐标不在上海服务范围内。")

    @staticmethod
    def is_point_in_shanghai(*, lng: float, lat: float) -> bool:
        if not (
            SHANGHAI_LNG_RANGE[0] <= lng <= SHANGHAI_LNG_RANGE[1]
            and SHANGHAI_LAT_RANGE[0] <= lat <= SHANGHAI_LAT_RANGE[1]
        ):
            return False
        if any(CityGuard._point_in_polygon(lng, lat, polygon) for polygon in NON_SHANGHAI_EXCLUSION_POLYGONS):
            return False
        return any(CityGuard._point_in_polygon(lng, lat, polygon) for polygon in SHANGHAI_SERVICE_POLYGONS)

    @staticmethod
    def _point_in_polygon(lng: float, lat: float, polygon: list[tuple[float, float]]) -> bool:
        inside = False
        j = len(polygon) - 1
        for i, (lng_i, lat_i) in enumerate(polygon):
            lng_j, lat_j = polygon[j]
            intersects = (lat_i > lat) != (lat_j > lat) and lng < (
                (lng_j - lng_i) * (lat - lat_i) / (lat_j - lat_i) + lng_i
            )
            if intersects:
                inside = not inside
            j = i
        return inside

    @staticmethod
    def _dedupe(values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result

    @staticmethod
    def _get_value(row: Any, key: str) -> Any:
        if isinstance(row, dict):
            return row.get(key)
        return getattr(row, key, None)
