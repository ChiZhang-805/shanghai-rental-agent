from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.commute import CommuteCache
from app.schemas.commute import CommuteRouteSummary


class CommuteCacheService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @staticmethod
    def build_commute_cache_key(
        origin_lng: float,
        origin_lat: float,
        dest_lng: float,
        dest_lat: float,
        mode: str,
    ) -> str:
        raw = (
            f"{round(origin_lng, 5)},{round(origin_lat, 5)}->"
            f"{round(dest_lng, 5)},{round(dest_lat, 5)}:{mode}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(
        self,
        session: Session | None,
        origin_lng: float,
        origin_lat: float,
        dest_lng: float,
        dest_lat: float,
        mode: str,
        *,
        anchor_label: str,
    ) -> CommuteRouteSummary | None:
        if session is None:
            return None
        key = self.build_commute_cache_key(origin_lng, origin_lat, dest_lng, dest_lat, mode)
        try:
            cache = session.scalar(
                select(CommuteCache).where(
                    CommuteCache.cache_key == key, CommuteCache.expires_at > datetime.utcnow()
                )
            )
        except Exception:
            session.rollback()
            return None
        if cache is None:
            return None
        return CommuteRouteSummary(
            anchor_label=anchor_label,
            mode=cache.mode,
            duration_min=cache.duration_min,
            distance_m=cache.distance_m,
            transfers=cache.transfers,
            walking_distance_m=cache.walking_distance_m,
            summary=cache.summary,
            route_status=cache.route_status,  # type: ignore[arg-type]
            route_geojson=cache.route_polyline,
        )

    def set(
        self,
        session: Session | None,
        origin_lng: float,
        origin_lat: float,
        dest_lng: float,
        dest_lat: float,
        mode: str,
        route: CommuteRouteSummary,
    ) -> None:
        if session is None or route.route_status == "error":
            return
        key = self.build_commute_cache_key(origin_lng, origin_lat, dest_lng, dest_lat, mode)
        try:
            cache = session.scalar(select(CommuteCache).where(CommuteCache.cache_key == key))
            if cache is None:
                cache = CommuteCache(
                    mode=mode,
                    origin_lng=origin_lng,
                    origin_lat=origin_lat,
                    destination_lng=dest_lng,
                    destination_lat=dest_lat,
                    city1=self.settings.amap_default_city_code,
                    city2=self.settings.amap_default_city_code,
                    cache_key=key,
                    route_status=route.route_status,
                    expires_at=datetime.utcnow() + timedelta(hours=self.settings.amap_cache_ttl_hours),
                )
                session.add(cache)
            cache.route_status = route.route_status
            cache.duration_min = route.duration_min
            cache.distance_m = route.distance_m
            cache.transfers = route.transfers
            cache.walking_distance_m = route.walking_distance_m
            cache.summary = route.summary
            cache.route_polyline = route.route_geojson
            cache.expires_at = datetime.utcnow() + timedelta(hours=self.settings.amap_cache_ttl_hours)
            session.commit()
        except Exception:
            session.rollback()
            return
