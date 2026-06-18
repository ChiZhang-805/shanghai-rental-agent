from __future__ import annotations

from typing import Any

from app.schemas.commute import CommuteRouteSummary
from app.schemas.rental import RentalPreferenceWeights


class RentalScoringService:
    @staticmethod
    def budget_score(
        rent: int | None,
        budget: int | None,
        min_rent: int | None = None,
        max_rent: int | None = None,
    ) -> float:
        if rent is None:
            return 50.0
        if min_rent is not None and rent < min_rent:
            return 70.0
        if max_rent is not None:
            budget = max_rent
        if budget is None:
            return 50.0
        if rent <= budget * 0.85:
            return 100.0
        if rent <= budget:
            return 90.0 - (rent - budget * 0.85) / (budget * 0.15) * 15.0
        if rent <= budget * 1.15:
            return 70.0 - (rent - budget) / (budget * 0.15) * 35.0
        return 20.0

    @staticmethod
    def commute_duration_score(duration_min: float | None, target_min: int) -> float:
        if duration_min is None:
            return 30.0
        if duration_min <= target_min * 0.8:
            return 100.0
        if duration_min <= target_min:
            return 100.0 - (duration_min - target_min * 0.8) / (target_min * 0.2) * 20.0
        if duration_min <= target_min + 15:
            return 80.0 - (duration_min - target_min) / 15.0 * 25.0
        if duration_min <= target_min + 30:
            return 55.0 - (duration_min - target_min - 15) / 15.0 * 30.0
        return 10.0

    @staticmethod
    def commute_penalty(transfers: int | None, walking_distance_m: int | None) -> float:
        transfer_penalty = max(0, (transfers or 0) - 1) * 8.0
        walk_penalty = 0.0
        if walking_distance_m and walking_distance_m > 800:
            walk_penalty = min(15.0, (walking_distance_m - 800) / 100 * 1.5)
        return transfer_penalty + walk_penalty

    @staticmethod
    def multi_anchor_commute_score(anchor_scores: list[tuple[float, float]]) -> float:
        if not anchor_scores:
            return 30.0
        total_weight = sum(weight for _, weight in anchor_scores) or 1.0
        weighted = sum(score * weight for score, weight in anchor_scores) / total_weight
        worst = min(score for score, _ in anchor_scores)
        return 0.8 * weighted + 0.2 * worst

    @staticmethod
    def transit_access_score(metro_distance_m: int | None) -> float:
        if metro_distance_m is None:
            return 50.0
        if metro_distance_m <= 500:
            return 100.0
        if metro_distance_m <= 800:
            return 90.0
        if metro_distance_m <= 1200:
            return 70.0
        if metro_distance_m <= 1800:
            return 45.0
        return 20.0

    @staticmethod
    def risk_score(item: Any) -> tuple[float, list[str]]:
        score = 100.0
        notes: list[str] = []
        if RentalScoringService._value(item, "is_demo", False):
            score -= 20.0
            if RentalScoringService._value(item, "item_type", "listing") == "area":
                notes.append("区域候选仅供找房方向参考，不代表具体可租房源")
            else:
                notes.append("该条为 demo 数据，不能作为真实可租房源")
        if RentalScoringService._value(item, "item_type", "listing") == "listing":
            if RentalScoringService._value(item, "is_verified", False) is False:
                score -= 15.0
                notes.append("房源未标记为已核验")
            if RentalScoringService._value(item, "status", "unknown") != "available":
                score -= 40.0
                notes.append("房源状态不是 available")
            if RentalScoringService._value(item, "last_seen_at", None) is None:
                score -= 10.0
                notes.append("缺少最近更新时间")
        return max(score, 0.0), notes

    def commute_score_for_routes(
        self,
        routes: list[CommuteRouteSummary],
        target_min: int,
        anchor_weights: dict[str, float],
    ) -> float:
        best_by_anchor: dict[str, float] = {}
        for route in routes:
            raw = self.commute_duration_score(route.duration_min, target_min)
            penalty = self.commute_penalty(route.transfers, route.walking_distance_m)
            score = max(0.0, raw - penalty)
            current = best_by_anchor.get(route.anchor_label)
            if current is None or score > current:
                best_by_anchor[route.anchor_label] = score
        weighted = [
            (score, anchor_weights.get(label, 1.0)) for label, score in best_by_anchor.items()
        ]
        return self.multi_anchor_commute_score(weighted)

    def total_score(
        self,
        *,
        item: Any,
        routes: list[CommuteRouteSummary],
        budget: int | None,
        min_rent: int | None,
        max_rent: int | None,
        max_commute_min: int,
        anchor_weights: dict[str, float],
        weights: RentalPreferenceWeights,
    ) -> tuple[float, dict[str, float], list[str]]:
        rent = self._value(item, "rent_monthly", None)
        if rent is None:
            rent = self._value(item, "typical_rent", None)
        budget_value = self.budget_score(rent, budget, min_rent, max_rent)
        commute_value = self.commute_score_for_routes(routes, max_commute_min, anchor_weights)
        transit_value = self.transit_access_score(self._value(item, "metro_distance_m", None))
        risk_value, risk_notes = self.risk_score(item)
        listing_quality = 70.0
        if self._value(item, "is_verified", False):
            listing_quality = 90.0
        amenities = 70.0
        normalized_weights = self._normalized_weights(weights)
        total = (
            normalized_weights["commute"] * commute_value
            + normalized_weights["budget"] * budget_value
            + normalized_weights["transit_access"] * transit_value
            + normalized_weights["listing_quality"] * listing_quality
            + normalized_weights["amenities"] * amenities
            + normalized_weights["risk"] * risk_value
        )
        breakdown = {
            "commute": round(commute_value, 2),
            "budget": round(budget_value, 2),
            "transit_access": round(transit_value, 2),
            "listing_quality": round(listing_quality, 2),
            "amenities": round(amenities, 2),
            "risk": round(risk_value, 2),
        }
        return round(total, 2), breakdown, risk_notes

    @staticmethod
    def _value(item: Any, key: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    @staticmethod
    def _normalized_weights(weights: RentalPreferenceWeights) -> dict[str, float]:
        values = {key: max(0.0, float(value)) for key, value in weights.model_dump().items()}
        total = sum(values.values())
        if total <= 0:
            values = RentalPreferenceWeights().model_dump()
            total = sum(values.values())
        return {key: value / total for key, value in values.items()}
