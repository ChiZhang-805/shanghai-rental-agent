from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, get_effective_settings
from app.schemas.commute import CommuteMode, CommuteRouteSummary
from app.schemas.geo import GeocodeResponse
from app.services.city_guard import CityGuard, CityGuardError


class AmapService:
    base_url = "https://restapi.amap.com"

    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
        city_guard: CityGuard | None = None,
    ) -> None:
        self.settings = settings or get_effective_settings()
        self.http_client = http_client
        self.city_guard = city_guard or CityGuard()

    @property
    def live_enabled(self) -> bool:
        return bool(self.settings.amap_web_service_key and self.settings.amap_enable_live)

    async def geocode(self, address: str, city: str = "上海") -> GeocodeResponse:
        try:
            self.city_guard.assert_request_allowed(f"{city} {address}")
        except CityGuardError as exc:
            return GeocodeResponse(address=address, city=city, status="error", message=str(exc))

        if not self.live_enabled:
            return GeocodeResponse(
                address=address,
                city=city,
                status="unavailable",
                message="未配置 AMAP_WEB_SERVICE_KEY 或 AMAP_ENABLE_LIVE=false，地理编码不可用。",
            )

        try:
            data = await self._get(
                "/v3/geocode/geo",
                {
                    "address": address,
                    "city": city or self.settings.amap_default_city,
                    "output": "json",
                },
            )
            geocodes = data.get("geocodes") or []
            if not geocodes:
                return GeocodeResponse(
                    address=address, city=city, status="unavailable", message="高德未返回地理编码结果。"
                )
            first = geocodes[0]
            province = str(first.get("province") or "")
            result_city = str(first.get("city") or city)
            district = str(first.get("district") or "") or None
            if "上海" not in province and "上海" not in result_city:
                return GeocodeResponse(
                    address=address, city=city, status="error", message="地理编码结果不在上海。"
                )
            lng, lat = self._split_location(first.get("location"))
            if lng is None or lat is None or not self.city_guard.is_point_in_shanghai(lng=lng, lat=lat):
                return GeocodeResponse(
                    address=address, city=city, status="error", message="地理编码坐标不在上海服务范围内。"
                )
            return GeocodeResponse(
                address=address,
                city="上海",
                district=district,
                lng=round(lng, 6),
                lat=round(lat, 6),
                status="ok",
            )
        except Exception as exc:
            return GeocodeResponse(address=address, city=city, status="error", message=str(exc))

    async def reverse_geocode(self, lng: float, lat: float) -> GeocodeResponse:
        try:
            self.city_guard.assert_point_in_shanghai(lng=lng, lat=lat, label="逆地理编码点")
        except CityGuardError as exc:
            return GeocodeResponse(
                address="",
                city="上海",
                lng=lng,
                lat=lat,
                status="error",
                message=str(exc),
            )
        if not self.live_enabled:
            return GeocodeResponse(
                address="",
                city="上海",
                lng=lng,
                lat=lat,
                status="unavailable",
                message="未配置 AMAP_WEB_SERVICE_KEY 或 AMAP_ENABLE_LIVE=false，逆地理编码不可用。",
            )
        try:
            data = await self._get(
                "/v3/geocode/regeo",
                {"location": f"{lng},{lat}", "output": "json", "radius": 1000},
            )
            regeo = data.get("regeocode") or {}
            component = regeo.get("addressComponent") or {}
            province = str(component.get("province") or "")
            city = str(component.get("city") or "上海")
            district = str(component.get("district") or "") or None
            if "上海" not in province and "上海" not in city:
                return GeocodeResponse(
                    address=regeo.get("formatted_address") or "",
                    city="上海",
                    lng=lng,
                    lat=lat,
                    status="error",
                    message="逆地理编码结果不在上海。",
                )
            return GeocodeResponse(
                address=regeo.get("formatted_address") or "",
                city="上海",
                district=district,
                lng=round(lng, 6),
                lat=round(lat, 6),
                status="ok",
            )
        except Exception as exc:
            return GeocodeResponse(address="", city="上海", lng=lng, lat=lat, status="error", message=str(exc))

    async def search_communities_around(
        self,
        lng: float,
        lat: float,
        *,
        radius_m: int = 5000,
        page_size: int = 25,
        pages: int = 3,
    ) -> list[dict[str, Any]]:
        try:
            self.city_guard.assert_point_in_shanghai(lng=lng, lat=lat, label="小区搜索中心点")
        except CityGuardError:
            return []
        if not self.live_enabled:
            return []

        pois: list[dict[str, Any]] = []
        seen: set[str] = set()
        radius = max(500, min(50000, int(radius_m)))
        page_size = max(1, min(25, int(page_size)))
        pages = max(1, min(10, int(pages)))
        for page_num in range(1, pages + 1):
            try:
                data = await self._get(
                    "/v5/place/around",
                    {
                        "location": f"{lng},{lat}",
                        "radius": radius,
                        "types": "120300|120301|120302|120303",
                        "region": self.settings.amap_default_city,
                        "city_limit": "true",
                        "sortrule": "distance",
                        "page_size": page_size,
                        "page_num": page_num,
                        "show_fields": "business,children",
                        "output": "json",
                    },
                )
            except Exception:
                break
            if str(data.get("status")) != "1":
                break
            page_pois = data.get("pois") or []
            if not page_pois:
                break
            for poi in page_pois:
                lng_lat = self._split_location(poi.get("location"))
                poi_lng, poi_lat = lng_lat
                if poi_lng is None or poi_lat is None:
                    continue
                if not self.city_guard.is_point_in_shanghai(lng=poi_lng, lat=poi_lat):
                    continue
                key = str(poi.get("id") or f"{poi.get('name')}:{poi_lng:.6f},{poi_lat:.6f}")
                if key in seen:
                    continue
                seen.add(key)
                pois.append(poi)
        return pois

    async def route(
        self,
        origin_lng: float,
        origin_lat: float,
        destination_lng: float,
        destination_lat: float,
        mode: CommuteMode = "transit",
        city1: str = "021",
        city2: str = "021",
        anchor_label: str = "目的地",
    ) -> CommuteRouteSummary:
        try:
            self.city_guard.assert_point_in_shanghai(lng=origin_lng, lat=origin_lat, label="通勤起点")
            self.city_guard.assert_point_in_shanghai(
                lng=destination_lng, lat=destination_lat, label="通勤终点"
            )
        except CityGuardError as exc:
            return CommuteRouteSummary(
                anchor_label=anchor_label,
                mode=mode,
                duration_min=None,
                distance_m=None,
                route_status="error",
                summary=str(exc),
            )

        if not self.live_enabled:
            return CommuteRouteSummary(
                anchor_label=anchor_label,
                mode=mode,
                duration_min=None,
                distance_m=None,
                route_status="unavailable",
                summary="未配置高德 Web Service Key，路线暂不可用。",
            )

        endpoint = self._route_endpoint(mode)
        params: dict[str, Any] = {
            "origin": f"{origin_lng},{origin_lat}",
            "destination": f"{destination_lng},{destination_lat}",
            "output": "json",
            "show_fields": "cost,polyline,navi",
        }
        if mode == "transit":
            params["city1"] = city1 or self.settings.amap_default_city_code
            params["city2"] = city2 or self.settings.amap_default_city_code

        try:
            data = await self._get(endpoint, params)
            if str(data.get("status")) != "1":
                return CommuteRouteSummary(
                    anchor_label=anchor_label,
                    mode=mode,
                    duration_min=None,
                    distance_m=None,
                    route_status="error",
                    summary=f"高德路线接口返回错误：{data.get('info') or data.get('infocode')}",
                )
            return self._parse_route(data, mode=mode, anchor_label=anchor_label)
        except Exception as exc:
            return CommuteRouteSummary(
                anchor_label=anchor_label,
                mode=mode,
                duration_min=None,
                distance_m=None,
                route_status="error",
                summary=str(exc),
            )

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = dict(params)
        params["key"] = self.settings.amap_web_service_key
        client = self.http_client
        if client is not None:
            response = await client.get(f"{self.base_url}{path}", params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        async with httpx.AsyncClient(timeout=10) as owned_client:
            response = await owned_client.get(f"{self.base_url}{path}", params=params)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _route_endpoint(mode: str) -> str:
        endpoints = {
            "driving": "/v5/direction/driving",
            "walking": "/v5/direction/walking",
            "bicycling": "/v5/direction/bicycling",
            "electrobike": "/v5/direction/electrobike",
            "transit": "/v5/direction/transit/integrated",
        }
        return endpoints.get(mode, "/v5/direction/transit/integrated")

    @staticmethod
    def _split_location(value: Any) -> tuple[float | None, float | None]:
        if not value or "," not in str(value):
            return None, None
        lng, lat = str(value).split(",", 1)
        return float(lng), float(lat)

    def _parse_route(self, data: dict[str, Any], *, mode: str, anchor_label: str) -> CommuteRouteSummary:
        route = data.get("route") or {}
        path = self._first_path(route, mode)
        if not path:
            return CommuteRouteSummary(
                anchor_label=anchor_label,
                mode=mode,
                duration_min=None,
                distance_m=None,
                route_status="unavailable",
                summary="高德未返回可用路线。",
            )
        duration_sec = self._to_float(path.get("duration") or path.get("cost", {}).get("duration"))
        distance_m = self._to_int(path.get("distance"))
        if duration_sec is None:
            return CommuteRouteSummary(
                anchor_label=anchor_label,
                mode=mode,
                duration_min=None,
                distance_m=distance_m,
                route_status="unavailable",
                summary="高德未返回通勤时间，路线不可用。",
            )
        transfers = self._extract_transfers(path, mode)
        walking_distance = self._extract_walking_distance(path, mode)
        polyline = self._extract_polyline(path, mode)
        return CommuteRouteSummary(
            anchor_label=anchor_label,
            mode=mode,
            duration_min=round(duration_sec / 60.0, 1) if duration_sec is not None else None,
            distance_m=distance_m,
            transfers=transfers,
            walking_distance_m=walking_distance,
            route_status="ok",
            route_geojson=polyline,
            summary=self._build_summary(mode, duration_sec, distance_m, transfers, walking_distance),
        )

    @staticmethod
    def _first_path(route: dict[str, Any], mode: str) -> dict[str, Any] | None:
        if mode == "transit":
            transits = route.get("transits") or []
            return transits[0] if transits else None
        paths = route.get("paths") or []
        return paths[0] if paths else None

    @staticmethod
    def _extract_transfers(path: dict[str, Any], mode: str) -> int | None:
        if mode != "transit":
            return None
        segments = path.get("segments") or []
        bus_count = sum(1 for segment in segments if segment.get("bus", {}).get("buslines"))
        subway_count = sum(1 for segment in segments if segment.get("railway") or segment.get("bus", {}).get("buslines"))
        ride_count = max(bus_count, subway_count)
        return max(0, ride_count - 1) if ride_count else 0

    @staticmethod
    def _extract_walking_distance(path: dict[str, Any], mode: str) -> int | None:
        if mode != "transit":
            return None
        total = 0
        found = False
        for segment in path.get("segments") or []:
            walking = segment.get("walking") or {}
            distance = AmapService._to_int(walking.get("distance"))
            if distance is not None:
                total += distance
                found = True
        return total if found else None

    @staticmethod
    def _extract_polyline(path: dict[str, Any], mode: str) -> dict | None:
        points: list[list[float]] = []
        if mode == "transit":
            for segment in path.get("segments") or []:
                for section in [segment.get("walking") or {}, segment.get("bus") or {}]:
                    AmapService._append_polyline(points, section.get("polyline"))
                    for busline in section.get("buslines") or []:
                        AmapService._append_polyline(points, busline.get("polyline"))
        else:
            for step in path.get("steps") or []:
                AmapService._append_polyline(points, step.get("polyline"))
        if len(points) < 2:
            return None
        return {"type": "LineString", "coordinates": points}

    @staticmethod
    def _append_polyline(points: list[list[float]], polyline: Any) -> None:
        if not polyline:
            return
        if isinstance(polyline, dict):
            for key in ("polyline", "points", "steps", "buslines"):
                AmapService._append_polyline(points, polyline.get(key))
            return
        if isinstance(polyline, list):
            for item in polyline:
                AmapService._append_polyline(points, item)
            return
        for pair in str(polyline).split(";"):
            if "," not in pair:
                continue
            lng, lat = pair.split(",", 1)
            try:
                points.append([round(float(lng), 6), round(float(lat), 6)])
            except ValueError:
                continue

    @staticmethod
    def _build_summary(
        mode: str,
        duration_sec: float | None,
        distance_m: int | None,
        transfers: int | None,
        walking_distance_m: int | None,
    ) -> str:
        parts = [f"出行方式：{mode}"]
        if duration_sec is not None:
            parts.append(f"高德返回约 {round(duration_sec / 60.0, 1)} 分钟")
        if distance_m is not None:
            parts.append(f"距离约 {distance_m} 米")
        if transfers is not None:
            parts.append(f"换乘 {transfers} 次")
        if walking_distance_m is not None:
            parts.append(f"步行约 {walking_distance_m} 米")
        return "，".join(parts)

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
