from __future__ import annotations

from app.schemas.map import MapLayerResponse
from app.schemas.rental import RentalRecommendationItem
from app.services.city_guard import CityGuard


class MapLayerService:
    def __init__(self, city_guard: CityGuard | None = None) -> None:
        self.city_guard = city_guard or CityGuard()

    def build_layers(self, items: list[RentalRecommendationItem]) -> MapLayerResponse:
        markers = {"type": "FeatureCollection", "features": []}
        routes = {"type": "FeatureCollection", "features": []}
        areas = {"type": "FeatureCollection", "features": []}

        for item in items:
            self.city_guard.assert_point_in_shanghai(lng=item.lng, lat=item.lat, label=item.title)
            marker = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [item.lng, item.lat]},
                "properties": {
                    "id": item.id,
                    "title": item.title,
                    "item_type": item.item_type,
                    "score": item.total_score,
                    "rent_monthly": item.rent_monthly,
                    "room_rents": item.room_rents,
                    "district": item.district,
                    "commute_min": self._best_commute_min(item),
                    "is_demo": item.is_demo,
                    "risk_notes": item.risk_notes,
                    "score_breakdown": item.score_breakdown,
                },
            }
            markers["features"].append(marker)
            if item.item_type in {"area", "community"}:
                areas["features"].append(marker)
            for route in item.commute_routes:
                if route.route_geojson and route.route_geojson.get("type") == "LineString":
                    routes["features"].append(
                        {
                            "type": "Feature",
                            "geometry": route.route_geojson,
                            "properties": {
                                "item_id": item.id,
                                "anchor_label": route.anchor_label,
                                "mode": route.mode,
                                "duration_min": route.duration_min,
                                "route_status": route.route_status,
                            },
                        }
                    )
        center = self._center(items)
        return MapLayerResponse(
            center=center,
            markers_geojson=markers,
            routes_geojson=routes,
            areas_geojson=areas,
            legend={
                "score": "score >= 85 优先；70-85 可考虑；<70 谨慎",
                "source": "高德小区候选用于通勤和预算排序",
            },
        )

    @staticmethod
    def _center(items: list[RentalRecommendationItem]) -> dict[str, float]:
        if not items:
            return {"lng": 121.4737, "lat": 31.2304}
        return {
            "lng": round(sum(item.lng for item in items) / len(items), 6),
            "lat": round(sum(item.lat for item in items) / len(items), 6),
        }

    @staticmethod
    def _best_commute_min(item: RentalRecommendationItem) -> float | None:
        durations = [
            route.duration_min
            for route in item.commute_routes
            if route.route_status == "ok" and route.duration_min is not None
        ]
        return min(durations) if durations else None
