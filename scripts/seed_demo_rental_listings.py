import csv
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models.rental_listing import RentalListing
from app.services.city_guard import CityGuard


def _int(value: Any) -> int | None:
    return int(float(value)) if value not in (None, "") else None


def _float(value: Any) -> float | None:
    return float(value) if value not in (None, "") else None


def _bool(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    return str(value).lower() in {"true", "1", "yes", "y"}


def _date(value: Any) -> date | None:
    return date.fromisoformat(value) if value else None


def _datetime(value: Any) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _normalize_district(value: str | None, guard: CityGuard, external_id: str) -> str | None:
    if not value:
        return None
    normalized = guard.normalize_districts([value])
    if not normalized:
        raise ValueError(f"demo 房源行政区不属于上海行政区：{external_id} district={value!r}")
    return normalized[0]


def upsert_row(session, row: dict[str, str], guard: CityGuard) -> None:
    if row["city"] != "上海":
        raise ValueError(f"只允许导入上海 demo 房源：{row['external_id']}")
    if not _bool(row.get("is_demo"), default=True):
        raise ValueError(f"demo seed 文件中的 is_demo 必须为 true：{row['external_id']}")
    guard.assert_point_in_shanghai(lng=float(row["lng"]), lat=float(row["lat"]), label=row["title"])
    listing = session.scalar(
        select(RentalListing).where(RentalListing.external_id == row["external_id"])
    )
    if listing is None:
        listing = RentalListing(external_id=row["external_id"])
        session.add(listing)
    listing.source = row.get("source") or "demo"
    listing.title = row["title"]
    listing.city = "上海"
    listing.district = _normalize_district(row.get("district"), guard, row["external_id"])
    listing.subdistrict = row.get("subdistrict") or None
    listing.community_name = row.get("community_name") or None
    listing.address = row.get("address") or None
    listing.lng = _float(row.get("lng"))
    listing.lat = _float(row.get("lat"))
    listing.coordinate_system = row.get("coordinate_system") or "gcj02"
    listing.rent_monthly = int(row["rent_monthly"])
    listing.deposit_months = _float(row.get("deposit_months"))
    listing.payment_cycle = row.get("payment_cycle") or None
    listing.rooms = _int(row.get("rooms"))
    listing.halls = _int(row.get("halls"))
    listing.bathrooms = _int(row.get("bathrooms"))
    listing.area_sqm = _float(row.get("area_sqm"))
    listing.floor = _int(row.get("floor"))
    listing.total_floors = _int(row.get("total_floors"))
    listing.orientation = row.get("orientation") or None
    listing.decoration = row.get("decoration") or None
    listing.has_elevator = _bool(row.get("has_elevator"))
    listing.nearby_metro_station = row.get("nearby_metro_station") or None
    listing.metro_distance_m = _int(row.get("metro_distance_m"))
    listing.available_from = _date(row.get("available_from"))
    listing.status = row.get("status") or "available"
    listing.last_seen_at = _datetime(row.get("last_seen_at"))
    listing.listing_url = row.get("listing_url") or None
    listing.contact_name = row.get("contact_name") or None
    listing.contact_phone = row.get("contact_phone") or None
    listing.is_verified = _bool(row.get("is_verified"))
    listing.is_demo = True
    listing.raw_payload = row


def main() -> None:
    init_db()
    guard = CityGuard()
    path = Path("data/demo/rental_listings_demo.csv")
    with SessionLocal() as session, path.open(encoding="utf-8", newline="") as fp:
        count = 0
        for row in csv.DictReader(fp):
            upsert_row(session, row, guard)
            count += 1
        session.commit()
    print(f"Seeded/updated {count} demo rental listings.")


if __name__ == "__main__":
    main()
