from __future__ import annotations

import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.geo import CandidateArea
from app.models.rental_listing import RentalListing
from app.schemas.rental import RentalRecommendationRequest
from app.services.city_guard import CityGuard


class RentalDataService:
    COMMUNITY_RENT_MEMORY_PATH = Path("data/generated/community_rent_memory.json")

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        city_guard: CityGuard | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.city_guard = city_guard or CityGuard()
        self.database_available = True

    def count_available_real_listings(self, session: Session | None = None) -> int:
        if session is None or not self.database_available:
            return 0
        try:
            return int(
                session.scalar(
                    select(func.count()).select_from(RentalListing).where(
                        RentalListing.city == "上海",
                        RentalListing.status == "available",
                        RentalListing.is_demo.is_(False),
                    )
                )
                or 0
            )
        except Exception:
            session.rollback()
            self.database_available = False
            return 0

    def count_demo_listings(self, session: Session | None = None) -> int:
        if session is None or not self.database_available:
            return len(self._load_demo_listings())
        try:
            db_count = int(
                session.scalar(
                    select(func.count()).select_from(RentalListing).where(
                        RentalListing.city == "上海",
                        RentalListing.status == "available",
                        RentalListing.is_demo.is_(True),
                    )
                )
                or 0
            )
            return max(db_count, len(self._load_demo_listings()))
        except Exception:
            session.rollback()
            self.database_available = False
            return len(self._load_demo_listings())

    def get_candidate_listings(
        self,
        request: RentalRecommendationRequest,
        *,
        mode: str,
        session: Session | None = None,
    ) -> list[dict[str, Any]]:
        rows = self._query_db_listings(request, mode=mode, session=session) if session is not None else []
        if not rows and mode == "demo_listing_mode":
            rows = self._load_demo_listings()
        filtered = [row for row in rows if self._matches_request(row, request)]
        if not filtered and mode == "demo_listing_mode":
            rows = self._load_demo_listings()
            filtered = [row for row in rows if self._matches_request(row, request)]
        self._validate_items(filtered)
        return filtered[: request.result_limit * 2]

    def get_candidate_areas(
        self,
        request: RentalRecommendationRequest,
        *,
        session: Session | None = None,
    ) -> list[dict[str, Any]]:
        rows = self._query_db_areas(request, session=session) if session is not None else []
        if not rows:
            rows = self._load_candidate_areas()
        filtered = [row for row in rows if self._area_matches_request(row, request)]
        self._validate_items(filtered)
        return filtered[: request.result_limit * 2]

    def get_candidate_communities(
        self,
        request: RentalRecommendationRequest,
        *,
        session: Session | None = None,
    ) -> list[dict[str, Any]]:
        rows = self._load_candidate_communities()
        if not rows:
            rows = self._areas_as_community_candidates(self._load_candidate_areas())
        rows = [self._with_requested_room_rent(row, request.rooms) for row in rows]
        filtered = [row for row in rows if self._community_matches_request(row, request)]
        if not filtered:
            filtered = self._nearest_budget_communities(rows, request)
        self._validate_items(filtered)
        return filtered[: request.result_limit * 2]

    def build_community_candidates_from_pois(
        self,
        pois: list[dict[str, Any]],
        request: RentalRecommendationRequest,
    ) -> list[dict[str, Any]]:
        rent_memory = self._load_community_rent_memory()
        changed = False
        rows: list[dict[str, Any]] = []
        for poi in pois:
            name = str(poi.get("name") or "").strip()
            lng, lat = self._split_location(poi.get("location"))
            if not name or lng is None or lat is None:
                continue
            if not self.city_guard.is_point_in_shanghai(lng=lng, lat=lat):
                continue
            if name not in rent_memory:
                rent_memory[name] = self._generate_room_rents(name)
                changed = True
            room_rents = self._normalize_room_rents(rent_memory[name])
            rent_memory[name] = room_rents
            rent_monthly = self._rent_for_rooms(room_rents, request.rooms)
            business = poi.get("business") if isinstance(poi.get("business"), dict) else {}
            district = poi.get("adname") or poi.get("district") or business.get("business_area")
            rows.append(
                {
                    "item_type": "community",
                    "id": str(poi.get("id") or self._stable_id(name, lng, lat)),
                    "external_id": str(poi.get("id") or self._stable_id(name, lng, lat)),
                    "title": name,
                    "name": name,
                    "source": "amap_poi_around",
                    "city": "上海",
                    "district": self._normalize_district(str(district) if district else None),
                    "subdistrict": None,
                    "community_name": name,
                    "address": self._poi_address(poi, name),
                    "lng": lng,
                    "lat": lat,
                    "rent_monthly": rent_monthly,
                    "typical_rent": rent_monthly,
                    "room_rents": room_rents,
                    "metro_distance_m": None,
                    "nearby_metro_station": None,
                    "area_type": "community",
                    "tags": ["高德小区"],
                    "is_verified": False,
                    "is_demo": False,
                    "status": "available",
                }
            )
        if changed:
            self._save_community_rent_memory(rent_memory)
        rows = [self._with_requested_room_rent(row, request.rooms) for row in rows]
        filtered = [row for row in rows if self._community_matches_request(row, request)]
        if not filtered:
            filtered = self._nearest_budget_communities(rows, request)
        self._validate_items(filtered)
        return filtered

    def _query_db_listings(
        self,
        request: RentalRecommendationRequest,
        *,
        mode: str,
        session: Session | None,
    ) -> list[dict[str, Any]]:
        if session is None:
            return []
        stmt = select(RentalListing).where(RentalListing.city == "上海", RentalListing.status == "available")
        if mode == "listing_mode":
            stmt = stmt.where(RentalListing.is_demo.is_(False))
        elif mode == "demo_listing_mode":
            stmt = stmt.where(RentalListing.is_demo.is_(True))
        if request.budget_monthly:
            stmt = stmt.where(RentalListing.rent_monthly <= int(request.budget_monthly * 1.2))
        if request.min_rent_monthly:
            stmt = stmt.where(RentalListing.rent_monthly >= request.min_rent_monthly)
        if request.max_rent_monthly:
            stmt = stmt.where(RentalListing.rent_monthly <= request.max_rent_monthly)
        if request.rooms:
            stmt = stmt.where(RentalListing.rooms == request.rooms)
        if request.require_metro_distance_m is not None:
            stmt = stmt.where(
                RentalListing.metro_distance_m.is_not(None),
                RentalListing.metro_distance_m <= request.require_metro_distance_m,
            )
        districts = self.city_guard.normalize_districts(request.preferred_districts)
        if districts:
            stmt = stmt.where(RentalListing.district.in_(districts))
        try:
            return [self._listing_to_dict(row) for row in session.scalars(stmt).all()]
        except Exception:
            session.rollback()
            return []

    def _query_db_areas(
        self,
        request: RentalRecommendationRequest,
        *,
        session: Session | None,
    ) -> list[dict[str, Any]]:
        if session is None:
            return []
        stmt = select(CandidateArea).where(CandidateArea.city == "上海")
        districts = self.city_guard.normalize_districts(request.preferred_districts)
        if districts:
            stmt = stmt.where(CandidateArea.district.in_(districts))
        if request.require_metro_distance_m is not None:
            stmt = stmt.where(CandidateArea.area_type == "metro_station")
        try:
            return [self._area_to_dict(row) for row in session.scalars(stmt).all()]
        except Exception:
            session.rollback()
            return []

    def _matches_request(self, row: dict[str, Any], request: RentalRecommendationRequest) -> bool:
        if row.get("city") != "上海" or row.get("status") != "available":
            return False
        if request.rooms is not None and row.get("rooms") != request.rooms:
            return False
        if request.budget_monthly is not None and row.get("rent_monthly") is not None:
            if row["rent_monthly"] > int(request.budget_monthly * 1.2):
                return False
        if request.min_rent_monthly is not None and row.get("rent_monthly") is not None:
            if row["rent_monthly"] < request.min_rent_monthly:
                return False
        if request.max_rent_monthly is not None and row.get("rent_monthly") is not None:
            if row["rent_monthly"] > request.max_rent_monthly:
                return False
        if request.require_metro_distance_m is not None:
            metro_distance = row.get("metro_distance_m")
            if metro_distance is None or metro_distance > request.require_metro_distance_m:
                return False
        preferred = self.city_guard.normalize_districts(request.preferred_districts)
        if preferred and self._normalize_district(row.get("district")) not in preferred:
            return False
        excluded = self.city_guard.normalize_districts(request.excluded_districts)
        if excluded and self._normalize_district(row.get("district")) in excluded:
            return False
        return True

    def _area_matches_request(self, row: dict[str, Any], request: RentalRecommendationRequest) -> bool:
        preferred = self.city_guard.normalize_districts(request.preferred_districts)
        if preferred and self._normalize_district(row.get("district")) not in preferred:
            return False
        excluded = self.city_guard.normalize_districts(request.excluded_districts)
        if excluded and self._normalize_district(row.get("district")) in excluded:
            return False
        if request.require_metro_distance_m is not None:
            metro_distance = row.get("metro_distance_m")
            if metro_distance is None or metro_distance > request.require_metro_distance_m:
                return False
        return True

    def _community_matches_request(self, row: dict[str, Any], request: RentalRecommendationRequest) -> bool:
        preferred = self.city_guard.normalize_districts(request.preferred_districts)
        if preferred and self._normalize_district(row.get("district")) not in preferred:
            return False
        excluded = self.city_guard.normalize_districts(request.excluded_districts)
        if excluded and self._normalize_district(row.get("district")) in excluded:
            return False
        if request.require_metro_distance_m is not None:
            metro_distance = row.get("metro_distance_m")
            if metro_distance is None or metro_distance > request.require_metro_distance_m:
                return False
        rent = row.get("rent_monthly")
        if request.budget_monthly is not None and rent is not None and rent > int(request.budget_monthly * 1.2):
            return False
        if request.min_rent_monthly is not None and rent is not None and rent < request.min_rent_monthly:
            return False
        if request.max_rent_monthly is not None and rent is not None and rent > request.max_rent_monthly:
            return False
        return True

    def _validate_items(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            if row.get("city") != "上海":
                raise ValueError("租房推荐只允许上海数据。")
            self.city_guard.assert_point_in_shanghai(
                lng=row.get("lng"), lat=row.get("lat"), label=row.get("title") or row.get("name") or "候选点"
            )

    @staticmethod
    def _listing_to_dict(row: RentalListing) -> dict[str, Any]:
        return {
            "item_type": "listing",
            "id": str(row.id),
            "external_id": row.external_id,
            "source": row.source,
            "title": row.title,
            "city": row.city,
            "district": row.district,
            "subdistrict": row.subdistrict,
            "community_name": row.community_name,
            "address": row.address,
            "lng": row.lng,
            "lat": row.lat,
            "rent_monthly": row.rent_monthly,
            "rooms": row.rooms,
            "metro_distance_m": row.metro_distance_m,
            "nearby_metro_station": row.nearby_metro_station,
            "status": row.status,
            "last_seen_at": row.last_seen_at,
            "is_verified": row.is_verified,
            "is_demo": row.is_demo,
        }

    @staticmethod
    def _area_to_dict(row: CandidateArea) -> dict[str, Any]:
        return {
            "item_type": "area",
            "id": str(row.id),
            "title": row.name,
            "name": row.name,
            "source": "candidate_area",
            "city": row.city,
            "district": row.district,
            "community_name": None,
            "address": row.description,
            "lng": row.lng,
            "lat": row.lat,
            "rent_monthly": None,
            "typical_rent_1br": row.typical_rent_1br,
            "typical_rent_2br": row.typical_rent_2br,
            "typical_rent": row.typical_rent_1br,
            "metro_distance_m": 0 if row.area_type == "metro_station" else None,
            "area_type": row.area_type,
            "tags": row.tags,
            "is_verified": False,
            "is_demo": row.is_demo,
            "status": "available",
        }

    def _load_demo_listings(self) -> list[dict[str, Any]]:
        path = Path("data/demo/rental_listings_demo.csv")
        if not path.exists() or not self.settings.enable_demo_rental_data:
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8", newline="") as fp:
            for row in csv.DictReader(fp):
                if not self._bool(row.get("is_demo"), default=True):
                    raise ValueError(f"demo 房源 CSV 中 is_demo 必须为 true：{row.get('external_id')}")
                rows.append(
                    {
                        "item_type": "listing",
                        "id": row["external_id"],
                        "external_id": row["external_id"],
                        "source": row.get("source") or "demo",
                        "title": row["title"],
                        "city": row["city"],
                        "district": self._normalize_district(row.get("district")),
                        "subdistrict": row.get("subdistrict") or None,
                        "community_name": row.get("community_name") or None,
                        "address": row.get("address") or None,
                        "lng": self._float(row.get("lng")),
                        "lat": self._float(row.get("lat")),
                        "rent_monthly": self._int(row.get("rent_monthly")),
                        "rooms": self._int(row.get("rooms")),
                        "metro_distance_m": self._int(row.get("metro_distance_m")),
                        "nearby_metro_station": row.get("nearby_metro_station") or None,
                        "status": row.get("status") or "available",
                        "last_seen_at": row.get("last_seen_at") or None,
                        "is_verified": self._bool(row.get("is_verified")),
                        "is_demo": self._bool(row.get("is_demo"), default=True),
                    }
                )
        return rows

    def _load_candidate_areas(self) -> list[dict[str, Any]]:
        path = Path("data/demo/shanghai_candidate_areas.csv")
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8", newline="") as fp:
            for row in csv.DictReader(fp):
                if not self._bool(row.get("is_demo"), default=True):
                    raise ValueError(f"候选区域 demo CSV 中 is_demo 必须为 true：{row.get('name')}")
                typical = self._int(row.get("typical_rent_1br"))
                rows.append(
                    {
                        "item_type": "area",
                        "id": row["name"],
                        "title": row["name"],
                        "name": row["name"],
                        "source": "candidate_area",
                        "city": row["city"],
                        "district": self._normalize_district(row.get("district")),
                        "community_name": None,
                        "address": row.get("description") or row["name"],
                        "lng": self._float(row.get("lng")),
                        "lat": self._float(row.get("lat")),
                        "rent_monthly": None,
                        "typical_rent_1br": typical,
                        "typical_rent_2br": self._int(row.get("typical_rent_2br")),
                        "typical_rent": typical,
                        "metro_distance_m": 0 if row.get("area_type") == "metro_station" else None,
                        "area_type": row.get("area_type"),
                        "tags": self._json_list(row.get("tags")),
                        "metro_lines": self._json_list(row.get("metro_lines")),
                        "is_verified": False,
                        "is_demo": self._bool(row.get("is_demo"), default=True),
                        "status": "available",
                    }
                )
        return rows

    def _load_candidate_communities(self) -> list[dict[str, Any]]:
        path = Path("data/demo/shanghai_candidate_communities.csv")
        if not path.exists():
            return []
        rent_memory = self._load_community_rent_memory()
        changed = False
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8", newline="") as fp:
            for row in csv.DictReader(fp):
                if row.get("city") != "上海":
                    raise ValueError(f"候选小区 CSV 只允许上海数据：{row.get('name')}")
                if not self._bool(row.get("is_demo"), default=True):
                    raise ValueError(f"候选小区 CSV 中 is_demo 必须为 true：{row.get('name')}")
                name = row["name"].strip()
                if name not in rent_memory:
                    rent_memory[name] = self._generate_room_rents(name)
                    changed = True
                room_rents = self._normalize_room_rents(rent_memory[name])
                rent_memory[name] = room_rents
                rent_monthly = self._rent_for_rooms(room_rents, row.get("rooms"))
                rows.append(
                    {
                        "item_type": "community",
                        "id": row.get("external_id") or name,
                        "external_id": row.get("external_id") or name,
                        "title": name,
                        "name": name,
                        "source": "community_candidate",
                        "city": "上海",
                        "district": self._normalize_district(row.get("district")),
                        "subdistrict": row.get("subdistrict") or None,
                        "community_name": name,
                        "address": row.get("address") or name,
                        "lng": self._float(row.get("lng")),
                        "lat": self._float(row.get("lat")),
                        "rent_monthly": rent_monthly,
                        "typical_rent": rent_monthly,
                        "room_rents": room_rents,
                        "metro_distance_m": self._int(row.get("metro_distance_m")),
                        "nearby_metro_station": row.get("nearby_metro_station") or None,
                        "area_type": "community",
                        "tags": self._json_list(row.get("tags")),
                        "is_verified": False,
                        "is_demo": self._bool(row.get("is_demo"), default=True),
                        "status": "available",
                    }
                )
        if changed:
            self._save_community_rent_memory(rent_memory)
        return rows

    def _areas_as_community_candidates(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        communities: list[dict[str, Any]] = []
        rent_memory = self._load_community_rent_memory()
        changed = False
        for row in rows:
            name = f"{row['title']}小区候选"
            if name not in rent_memory:
                rent_memory[name] = self._generate_room_rents(name)
                changed = True
            room_rents = self._normalize_room_rents(rent_memory[name])
            rent_memory[name] = room_rents
            communities.append(
                {
                    **row,
                    "item_type": "community",
                    "id": name,
                    "title": name,
                    "name": name,
                    "source": "community_candidate",
                    "community_name": name,
                    "rent_monthly": room_rents["1"],
                    "typical_rent": room_rents["1"],
                    "room_rents": room_rents,
                    "area_type": "community",
                }
            )
        if changed:
            self._save_community_rent_memory(rent_memory)
        return communities

    def _rent_for_rooms(self, room_rents: dict[str, int], rooms: str | int | None) -> int:
        room_count = self._int(rooms) or 1
        room_key = str(min(3, max(1, room_count)))
        return room_rents[room_key]

    def _with_requested_room_rent(self, row: dict[str, Any], rooms: int | None) -> dict[str, Any]:
        room_rents = row.get("room_rents")
        if not isinstance(room_rents, dict):
            return row
        rent = self._rent_for_rooms(self._normalize_room_rents(room_rents), rooms)
        return {**row, "rent_monthly": rent, "typical_rent": rent}

    def _nearest_budget_communities(
        self,
        rows: list[dict[str, Any]],
        request: RentalRecommendationRequest,
    ) -> list[dict[str, Any]]:
        preferred = self.city_guard.normalize_districts(request.preferred_districts)
        excluded = self.city_guard.normalize_districts(request.excluded_districts)
        district_filtered = [
            row for row in rows
            if (not preferred or self._normalize_district(row.get("district")) in preferred)
            and (not excluded or self._normalize_district(row.get("district")) not in excluded)
        ]
        candidates = district_filtered or rows
        if request.budget_monthly is None:
            return candidates
        return sorted(
            candidates,
            key=lambda row: abs((row.get("rent_monthly") or request.budget_monthly) - request.budget_monthly),
        )

    def _load_community_rent_memory(self) -> dict[str, dict[str, int]]:
        path = self.COMMUNITY_RENT_MEMORY_PATH
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {
            str(name): self._normalize_room_rents(value)
            for name, value in data.items()
            if isinstance(value, dict)
        }

    def _save_community_rent_memory(self, memory: dict[str, dict[str, int]]) -> None:
        path = self.COMMUNITY_RENT_MEMORY_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(memory, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def _generate_room_rents(self, community_name: str) -> dict[str, int]:
        seed = int(hashlib.sha256(community_name.encode("utf-8")).hexdigest()[:16], 16)
        rng = random.Random(seed)
        one = rng.randint(2000, 9500)
        two = rng.randint(max(one + 500, 3000), min(15000, one + 5200))
        three = rng.randint(max(two + 500, 4200), 15000)
        return {"1": one, "2": two, "3": three}

    def _normalize_room_rents(self, value: dict[str, Any]) -> dict[str, int]:
        normalized = {
            "1": max(2000, min(15000, int(value.get("1") or value.get("one") or 2000))),
            "2": max(2000, min(15000, int(value.get("2") or value.get("two") or 3000))),
            "3": max(2000, min(15000, int(value.get("3") or value.get("three") or 4000))),
        }
        if normalized["2"] < normalized["1"]:
            normalized["2"] = normalized["1"]
        if normalized["3"] < normalized["2"]:
            normalized["3"] = normalized["2"]
        return normalized

    @staticmethod
    def _stable_id(name: str, lng: float, lat: float) -> str:
        digest = hashlib.sha256(f"{name}:{lng:.6f}:{lat:.6f}".encode("utf-8")).hexdigest()[:16]
        return f"community-{digest}"

    @staticmethod
    def _poi_address(poi: dict[str, Any], fallback_name: str) -> str:
        address = poi.get("address")
        if isinstance(address, list):
            address = " ".join(str(part) for part in address if part)
        address_text = str(address or "").strip()
        if address_text:
            return address_text
        return fallback_name

    @staticmethod
    def _split_location(value: Any) -> tuple[float | None, float | None]:
        if not value or "," not in str(value):
            return None, None
        lng, lat = str(value).split(",", 1)
        try:
            return float(lng), float(lat)
        except ValueError:
            return None, None

    @staticmethod
    def _normalize_district(value: str | None) -> str | None:
        if not value:
            return None
        value = value.replace("上海市", "").replace("浦东新区", "浦东")
        if value.endswith("区"):
            value = value[:-1]
        return value

    @staticmethod
    def _int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        return int(float(value))

    @staticmethod
    def _float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        return float(value)

    @staticmethod
    def _bool(value: Any, *, default: bool = False) -> bool:
        if value in (None, ""):
            return default
        return str(value).strip().lower() in {"true", "1", "yes", "y"}

    @staticmethod
    def _json_list(value: str | None) -> list[str] | None:
        if not value:
            return None
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else None
        except json.JSONDecodeError:
            return [part.strip() for part in value.split("|") if part.strip()]
