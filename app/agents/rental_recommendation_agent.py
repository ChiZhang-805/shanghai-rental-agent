from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.commute_agent import CommuteAgent
from app.agents.compliance_agent import ComplianceAgent
from app.agents.data_availability_agent import DataAvailabilityAgent, DataAvailabilityDecision
from app.agents.map_visualization_agent import MapVisualizationAgent
from app.schemas.rental import (
    AnchorInput,
    RentalRecommendationItem,
    RentalRecommendationRequest,
    RentalRecommendationResponse,
)
from app.services.city_guard import CityGuardError
from app.services.amap_service import AmapService
from app.services.rental_data_service import RentalDataService
from app.services.rental_scoring_service import RentalScoringService


class RentalRecommendationAgent(BaseAgent):
    name = "rental_recommendation_agent"

    def __init__(
        self,
        *,
        data_service: RentalDataService | None = None,
        scoring_service: RentalScoringService | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.data_service = data_service or RentalDataService(city_guard=self.city_guard)
        self.scoring_service = scoring_service or RentalScoringService()

    async def recommend(
        self,
        request: RentalRecommendationRequest,
        *,
        session: Session | None = None,
    ) -> RentalRecommendationResponse:
        request = self._augment_from_query(request)
        request = request.model_copy(
            update={
                "allow_demo_data": False,
                "recommendation_unit": "community",
            }
        )
        self._validate_request(request)

        global_real_count = self.data_service.count_available_real_listings(session)
        global_demo_count = self.data_service.count_demo_listings(session) if request.allow_demo_data else 0
        active_session = session if self.data_service.database_available else None
        if request.recommendation_unit == "community":
            real_candidates: list[dict[str, Any]] = []
            demo_candidates: list[dict[str, Any]] = []
            decision = DataAvailabilityDecision(
                mode="area_mode",
                data_warning="当前使用高德小区候选进行推荐；租金为本地固定估算值，不代表真实可租房源报价。",
                real_count=global_real_count,
                demo_count=global_demo_count,
            )
            candidates = await self._get_candidate_communities(request, session=active_session)
        else:
            real_candidates = self.data_service.get_candidate_listings(
                request, mode="listing_mode", session=active_session
            )
            demo_candidates = (
                self.data_service.get_candidate_listings(
                    request, mode="demo_listing_mode", session=active_session
                )
                if request.allow_demo_data
                else []
            )
            decision = DataAvailabilityAgent(city_guard=self.city_guard, openai_service=self.openai_service).decide_mode(
                available_real_count=len(real_candidates),
                available_demo_count=len(demo_candidates),
                allow_demo=request.allow_demo_data,
            )

            if decision.mode == "listing_mode":
                candidates = real_candidates
            elif decision.mode == "demo_listing_mode":
                candidates = demo_candidates
            else:
                candidates = self.data_service.get_candidate_areas(request, session=active_session)

        commute_result = await CommuteAgent(
            city_guard=self.city_guard, openai_service=self.openai_service
        ).analyze(
            candidates=candidates,
            anchors=request.anchors,
            modes=request.commute_modes,
            max_commute_min=request.max_commute_min,
            session=active_session,
        )

        anchor_weights = {anchor.label: anchor.weight for anchor in request.anchors}
        items: list[RentalRecommendationItem] = []
        for candidate in candidates:
            routes = commute_result.get(str(candidate["id"]), {}).get("routes", [])
            total, breakdown, risk_notes = self.scoring_service.total_score(
                item=candidate,
                routes=routes,
                budget=request.budget_monthly,
                min_rent=request.min_rent_monthly,
                max_rent=request.max_rent_monthly,
                max_commute_min=request.max_commute_min,
                anchor_weights=anchor_weights,
                weights=request.weights,
            )
            item = self._candidate_to_item(candidate, routes, total, breakdown, risk_notes, decision.mode)
            items.append(item)

        if request.recommendation_unit == "community":
            items = self._filter_by_max_commute(items, request.max_commute_min)
        items.sort(key=lambda item: item.total_score, reverse=True)
        items = items[: request.result_limit]
        for item in items:
            compliance = ComplianceAgent(
                city_guard=self.city_guard, openai_service=self.openai_service
            ).check(item.recommendation_reason)
            if not compliance.allowed:
                item.risk_notes.extend(compliance.violations)
        map_layers = MapVisualizationAgent(city_guard=self.city_guard).build_layers(items)
        return RentalRecommendationResponse(
            mode=decision.mode,
            data_warning=decision.data_warning,
            request_summary={
                "budget_monthly": request.budget_monthly,
                "rooms": request.rooms,
                "max_commute_min": request.max_commute_min,
                "commute_modes": request.commute_modes,
                "anchors": [anchor.model_dump() for anchor in request.anchors],
                "real_listing_count": len(real_candidates),
                "demo_listing_count": len(demo_candidates),
                "global_real_listing_count": global_real_count,
                "global_demo_listing_count": global_demo_count,
                "recommendation_unit": request.recommendation_unit,
            },
            results=items,
            map_layers=map_layers,
        )

    async def _get_candidate_communities(
        self,
        request: RentalRecommendationRequest,
        *,
        session: Session | None,
    ) -> list[dict[str, Any]]:
        anchor = await self._primary_anchor_with_coordinates(request)
        if (
            anchor is not None
            and hasattr(self.data_service, "build_community_candidates_from_pois")
        ):
            radius = self._community_search_radius(request)
            pois = await AmapService(city_guard=self.city_guard).search_communities_around(
                anchor.lng,
                anchor.lat,
                radius_m=radius,
                page_size=20,
                pages=2,
            )
            candidates = self.data_service.build_community_candidates_from_pois(pois, request)
            if candidates:
                return candidates[: request.result_limit]
        return []

    async def _primary_anchor_with_coordinates(
        self,
        request: RentalRecommendationRequest,
    ) -> AnchorInput | None:
        if not request.anchors:
            return None
        anchor = request.anchors[0]
        if anchor.lng is not None and anchor.lat is not None:
            return anchor
        if not anchor.address:
            return None
        geocode = await AmapService(city_guard=self.city_guard).geocode(anchor.address)
        if geocode.status != "ok" or geocode.lng is None or geocode.lat is None:
            return None
        return anchor.model_copy(update={"lng": geocode.lng, "lat": geocode.lat})

    @staticmethod
    def _community_search_radius(request: RentalRecommendationRequest) -> int:
        mode = request.commute_modes[0] if request.commute_modes else "transit"
        minutes = max(5, request.max_commute_min)
        if mode == "walking":
            return min(8000, max(1200, minutes * 95 + 1000))
        if mode in {"bicycling", "electrobike"}:
            return min(15000, max(2500, minutes * 260 + 1500))
        if mode == "driving":
            return min(30000, max(5000, minutes * 700 + 3000))
        return min(25000, max(5000, minutes * 550 + 3000))

    @staticmethod
    def _filter_by_max_commute(
        items: list[RentalRecommendationItem],
        max_commute_min: int,
    ) -> list[RentalRecommendationItem]:
        has_live_duration = any(
            route.route_status == "ok" and route.duration_min is not None
            for item in items
            for route in item.commute_routes
        )
        if not has_live_duration:
            return items
        filtered = [
            item
            for item in items
            if any(
                route.route_status == "ok"
                and route.duration_min is not None
                and route.duration_min <= max_commute_min
                for route in item.commute_routes
            )
        ]
        return filtered

    def _validate_request(self, request: RentalRecommendationRequest) -> None:
        pieces = [
            request.query or "",
            " ".join(request.preferred_districts),
            " ".join(request.excluded_districts),
            " ".join(anchor.address or "" for anchor in request.anchors),
        ]
        self.city_guard.assert_request_allowed(" ".join(pieces))
        for anchor in request.anchors:
            if anchor.lng is not None or anchor.lat is not None:
                self.city_guard.assert_point_in_shanghai(lng=anchor.lng, lat=anchor.lat, label=anchor.label)

    def _augment_from_query(self, request: RentalRecommendationRequest) -> RentalRecommendationRequest:
        if not request.query:
            return request
        self.city_guard.assert_request_allowed(request.query)
        updates: dict[str, Any] = {}
        if request.budget_monthly is None:
            budget = self._extract_monthly_budget(request.query)
            if budget:
                updates["budget_monthly"] = budget
        if request.rooms is None:
            rooms = self._extract_rooms(request.query)
            if rooms:
                updates["rooms"] = rooms
        if not request.anchors:
            anchor = self._extract_anchor(request.query)
            if anchor:
                updates["anchors"] = [anchor]
        commute = self._extract_max_commute(request.query)
        if commute:
            updates["max_commute_min"] = commute
        if "骑" in request.query:
            updates["commute_modes"] = ["bicycling"]
        elif "开车" in request.query or "驾车" in request.query:
            updates["commute_modes"] = ["driving"]
        elif "步行" in request.query:
            updates["commute_modes"] = ["walking"]
        return request.model_copy(update=updates)

    @staticmethod
    def _extract_monthly_budget(text: str) -> int | None:
        explicit = re.search(r"(?:预算|租金|月租)[^\d]{0,8}(\d{3,6})\s*(?:元|块)?", text)
        if explicit:
            value = int(explicit.group(1))
            if 1000 <= value <= 100000:
                return value
        for match in re.finditer(r"(\d{3,6})\s*(?:元|块)?", text):
            value = int(match.group(1))
            if 1000 <= value <= 100000:
                return value
        return None

    @staticmethod
    def _extract_rooms(text: str) -> int | None:
        cn = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4}
        match = re.search(r"([一二两三四]|\d+)\s*(?:室|房|居)", text)
        if not match:
            if "一室户" in text:
                return 1
            return None
        raw = match.group(1)
        return cn.get(raw, int(raw) if raw.isdigit() else None)

    @staticmethod
    def _extract_anchor(text: str) -> AnchorInput | None:
        patterns = [
            r"我在([^，,。；;]+?)上班",
            r"公司在([^，,。；;]+)",
            r"工作地点(?:在|是)?([^，,。；;]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                address = match.group(1).strip()
                return AnchorInput(label="公司", address=f"上海 {address}", anchor_type="workplace")
        return None

    @staticmethod
    def _extract_max_commute(text: str) -> int | None:
        match = re.search(r"(\d{1,3})\s*分钟", text)
        if match:
            return max(5, min(180, int(match.group(1))))
        return None

    @staticmethod
    def _candidate_to_item(
        candidate: dict[str, Any],
        routes: list,
        total: float,
        breakdown: dict[str, float],
        risk_notes: list[str],
        mode: str,
    ) -> RentalRecommendationItem:
        best_route = next(
            (route for route in routes if route.route_status == "ok" and route.duration_min is not None),
            None,
        )
        if best_route:
            commute_text = f"高德返回最短通勤约 {best_route.duration_min} 分钟"
        elif routes:
            commute_text = "通勤路线暂未取得，已按 unavailable 低分处理"
        else:
            commute_text = "未提供通勤锚点，未计算通勤路线"
        item_type = candidate.get("item_type", "listing")
        if item_type == "community":
            next_action = "可点击卡片生成通勤路径，并按该小区继续查找具体房源。"
        elif mode == "area_mode":
            next_action = "建议在该板块继续核验真实房源，不把区域推荐等同于具体可租房。"
        elif candidate.get("is_demo"):
            next_action = "仅用于演示，请导入真实房源后再联系看房。"
        else:
            next_action = "可继续核验房源状态、委托和带看时间。"
        title = candidate.get("title") or candidate.get("name")
        reason = (
            f"{title}位于上海{candidate.get('district') or ''}，综合分 {total}。"
            f"预算分 {breakdown['budget']}，通勤分 {breakdown['commute']}，"
            f"地铁便利分 {breakdown['transit_access']}。{commute_text}。"
        )
        if mode == "area_mode" and item_type == "area":
            area_note = "区域候选仅供找房方向参考，不代表具体可租房源"
            if area_note not in risk_notes:
                risk_notes.append(area_note)
        elif item_type == "community":
            community_note = "小区候选仅用于通勤和预算排序，不代表该小区当前有可租房源"
            if community_note not in risk_notes:
                risk_notes.append(community_note)
        elif candidate.get("is_demo") and "该条为 demo 数据，不能作为真实可租房源" not in risk_notes:
            risk_notes.append("该条为 demo 数据，不能作为真实可租房源")
        return RentalRecommendationItem(
            item_type=item_type,
            id=str(candidate["id"]),
            title=title,
            city="上海",
            district=candidate.get("district"),
            community_name=candidate.get("community_name"),
            address=candidate.get("address"),
            lng=float(candidate["lng"]),
            lat=float(candidate["lat"]),
            rent_monthly=candidate.get("rent_monthly") or candidate.get("typical_rent"),
            room_rents=candidate.get("room_rents"),
            is_demo=bool(candidate.get("is_demo", False)),
            data_source=candidate.get("source") or "unknown",
            total_score=total,
            score_breakdown=breakdown,
            commute_routes=routes,
            recommendation_reason=reason,
            risk_notes=risk_notes,
            next_action=next_action,
        )
