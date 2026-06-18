from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.listing import Listing
from app.schemas.listings import ListingOut, ListingSearchRequest, ListingSearchResponse
from app.services.city_guard import CityGuard
from app.services.retrieval_service import keyword_score


@dataclass
class ListingCandidate:
    row: Any
    score: float


class ListingService:
    def __init__(self, city_guard: CityGuard | None = None) -> None:
        self.city_guard = city_guard or CityGuard()

    def search(
        self,
        request: ListingSearchRequest,
        *,
        session: Session | None = None,
        listing_rows: list[Any] | None = None,
    ) -> ListingSearchResponse:
        self.city_guard.assert_request_allowed(" ".join([request.query or "", " ".join(request.districts)]))
        filters = self.city_guard.force_listing_filters(request.model_dump())
        rows = listing_rows if listing_rows is not None else self._load_from_db(filters, session)
        rows = self.city_guard.validate_listing_rows(rows)

        candidates: list[ListingCandidate] = []
        for row in rows:
            if not self._matches(row, request):
                continue
            score = self._score(row, request)
            candidates.append(ListingCandidate(row=row, score=score))

        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        results = [self._to_listing_out(candidate) for candidate in candidates[: request.top_k]]
        return ListingSearchResponse(results=results)

    def _load_from_db(self, filters: dict[str, Any], session: Session | None) -> list[Listing]:
        if session is None:
            return []
        stmt = select(Listing).where(Listing.city == "上海", Listing.listing_status == "active")
        if filters.get("purpose"):
            stmt = stmt.where(Listing.purpose == filters["purpose"])
        if filters.get("districts"):
            stmt = stmt.where(Listing.district.in_(filters["districts"]))
        try:
            return list(session.scalars(stmt).all())
        except Exception:
            session.rollback()
            return []

    def _matches(self, row: Any, request: ListingSearchRequest) -> bool:
        if self._value(row, "city") != "上海":
            return False
        if self._value(row, "listing_status") != "active":
            return False
        if request.purpose and self._value(row, "purpose") != request.purpose:
            return False
        if request.districts:
            districts = self.city_guard.normalize_districts(request.districts)
            if self._value(row, "district") not in districts:
                return False
        price = self._price(row)
        if request.budget_min is not None and price is not None and price < request.budget_min:
            return False
        if request.budget_max is not None and price is not None and price > request.budget_max:
            return False
        rooms = self._value(row, "rooms")
        if request.rooms_min is not None and rooms is not None and rooms < request.rooms_min:
            return False
        if request.rooms_max is not None and rooms is not None and rooms > request.rooms_max:
            return False
        return True

    def _score(self, row: Any, request: ListingSearchRequest) -> float:
        score = 1.0
        if request.purpose and self._value(row, "purpose") == request.purpose:
            score += 2.0
        if request.districts and self._value(row, "district") in self.city_guard.normalize_districts(
            request.districts
        ):
            score += 2.0
        if request.budget_max is not None:
            price = self._price(row)
            if price is not None and price <= request.budget_max:
                score += 2.0
        if request.rooms_min is not None:
            rooms = self._value(row, "rooms")
            if rooms is not None and rooms >= request.rooms_min:
                score += 1.0
        if request.query:
            score += keyword_score(request.query, self.make_listing_text(row))
        if self._value(row, "verification_status") == "verified":
            score += 0.5
        if self._value(row, "entrusted_status") == "active":
            score += 0.5
        return score

    def _to_listing_out(self, candidate: ListingCandidate) -> ListingOut:
        row = candidate.row
        out = ListingOut(
            id=self._value(row, "id"),
            listing_code=self._value(row, "listing_code"),
            city=self._value(row, "city"),
            district=self._value(row, "district"),
            subdistrict=self._value(row, "subdistrict"),
            community_name=self._value(row, "community_name"),
            title=self._value(row, "title"),
            purpose=self._value(row, "purpose"),
            rooms=self._value(row, "rooms"),
            halls=self._value(row, "halls"),
            bathrooms=self._value(row, "bathrooms"),
            area_sqm=float(self._value(row, "area_sqm")),
            sale_price_total=self._value(row, "sale_price_total"),
            rent_price_monthly=self._value(row, "rent_price_monthly"),
            verification_status=self._value(row, "verification_status"),
            entrusted_status=self._value(row, "entrusted_status"),
            listing_status=self._value(row, "listing_status"),
            score=round(candidate.score, 4),
        )
        out.recommendation_reason = self._recommendation_reason(out)
        return out

    @staticmethod
    def make_listing_text(row: Any) -> str:
        parts = [
            "title",
            "community_name",
            "district",
            "subdistrict",
            "rooms",
            "area_sqm",
            "decoration",
            "description",
        ]
        return " ".join(str(ListingService._value(row, part) or "") for part in parts)

    @staticmethod
    def _recommendation_reason(listing: ListingOut) -> str:
        price = listing.sale_price_total or listing.rent_price_monthly
        price_text = f"，价格 {price} 元" if price else ""
        return (
            f"{listing.district}{listing.community_name}，{listing.area_sqm:g}平，"
            f"{listing.rooms or '?'}房{price_text}；房源城市为上海，状态为{listing.listing_status}。"
        )

    @staticmethod
    def _price(row: Any) -> int | None:
        return ListingService._value(row, "sale_price_total") or ListingService._value(
            row, "rent_price_monthly"
        )

    @staticmethod
    def _value(row: Any, key: str) -> Any:
        if isinstance(row, dict):
            return row.get(key)
        return getattr(row, key, None)
