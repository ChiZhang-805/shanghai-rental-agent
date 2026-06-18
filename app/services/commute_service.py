from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_effective_settings
from app.schemas.commute import CommuteMode, CommuteRouteSummary
from app.schemas.rental import AnchorInput
from app.services.amap_service import AmapService
from app.services.city_guard import CityGuard
from app.services.commute_cache_service import CommuteCacheService


class CommuteService:
    def __init__(
        self,
        *,
        amap_service: AmapService | None = None,
        cache_service: CommuteCacheService | None = None,
        city_guard: CityGuard | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_effective_settings()
        self.city_guard = city_guard or CityGuard()
        self.amap_service = amap_service or AmapService(self.settings, city_guard=self.city_guard)
        self.cache_service = cache_service or CommuteCacheService(self.settings)

    async def batch_estimate(
        self,
        candidates: list[dict[str, Any]],
        anchors: list[AnchorInput],
        modes: list[CommuteMode],
        *,
        session: Session | None = None,
    ) -> dict[str, list[CommuteRouteSummary]]:
        anchors_with_coords = await self._ensure_anchor_coordinates(anchors)
        semaphore = asyncio.Semaphore(self.settings.amap_live_call_concurrency)
        tasks: list[asyncio.Task[tuple[str, CommuteRouteSummary]]] = []
        for candidate in candidates[:50]:
            candidate_id = str(candidate["id"])
            self.city_guard.assert_point_in_shanghai(
                lng=float(candidate["lng"]), lat=float(candidate["lat"]), label=candidate.get("title", "候选点")
            )
            for anchor in anchors_with_coords:
                if anchor.lng is None or anchor.lat is None:
                    for mode in modes:
                        tasks.append(
                            asyncio.create_task(
                                self._unavailable(candidate_id, anchor.label, mode, "锚点缺少可用上海坐标。")
                            )
                        )
                    continue
                for mode in modes:
                    if not self.amap_service.live_enabled:
                        tasks.append(
                            asyncio.create_task(
                                self._unavailable(
                                    candidate_id,
                                    anchor.label,
                                    mode,
                                    "未配置高德 Web Service Key，路线暂不可用。",
                                )
                            )
                        )
                        continue
                    cached = self.cache_service.get(
                        session,
                        float(candidate["lng"]),
                        float(candidate["lat"]),
                        anchor.lng,
                        anchor.lat,
                        mode,
                        anchor_label=anchor.label,
                    )
                    if cached is not None:
                        tasks.append(asyncio.create_task(self._existing(candidate_id, cached)))
                    else:
                        tasks.append(
                            asyncio.create_task(
                                self._route_with_limit(
                                    semaphore,
                                    candidate_id,
                                    float(candidate["lng"]),
                                    float(candidate["lat"]),
                                    anchor.lng,
                                    anchor.lat,
                                    mode,
                                    anchor.label,
                                    session,
                                )
                            )
                        )
        result: dict[str, list[CommuteRouteSummary]] = {str(candidate["id"]): [] for candidate in candidates}
        for candidate_id, route in await asyncio.gather(*tasks):
            result.setdefault(candidate_id, []).append(route)
        return result

    async def _ensure_anchor_coordinates(self, anchors: list[AnchorInput]) -> list[AnchorInput]:
        resolved: list[AnchorInput] = []
        for anchor in anchors:
            if anchor.lng is not None and anchor.lat is not None:
                self.city_guard.assert_point_in_shanghai(lng=anchor.lng, lat=anchor.lat, label=anchor.label)
                resolved.append(anchor)
                continue
            if anchor.address:
                geocode = await self.amap_service.geocode(anchor.address, city=self.settings.amap_default_city)
                resolved.append(anchor.model_copy(update={"lng": geocode.lng, "lat": geocode.lat}))
            else:
                resolved.append(anchor)
        return resolved

    async def _route_with_limit(
        self,
        semaphore: asyncio.Semaphore,
        candidate_id: str,
        origin_lng: float,
        origin_lat: float,
        dest_lng: float,
        dest_lat: float,
        mode: CommuteMode,
        anchor_label: str,
        session: Session | None,
    ) -> tuple[str, CommuteRouteSummary]:
        async with semaphore:
            route = await self.amap_service.route(
                origin_lng,
                origin_lat,
                dest_lng,
                dest_lat,
                mode=mode,
                anchor_label=anchor_label,
            )
            self.cache_service.set(session, origin_lng, origin_lat, dest_lng, dest_lat, mode, route)
            return candidate_id, route

    @staticmethod
    async def _existing(candidate_id: str, route: CommuteRouteSummary) -> tuple[str, CommuteRouteSummary]:
        return candidate_id, route

    @staticmethod
    async def _unavailable(
        candidate_id: str, anchor_label: str, mode: str, reason: str
    ) -> tuple[str, CommuteRouteSummary]:
        return (
            candidate_id,
            CommuteRouteSummary(
                anchor_label=anchor_label,
                mode=mode,
                duration_min=None,
                distance_m=None,
                route_status="unavailable",
                summary=reason,
            ),
        )
