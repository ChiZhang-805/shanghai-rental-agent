import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models.geo import CandidateArea
from app.services.city_guard import CityGuard


def _int(value: Any) -> int | None:
    return int(float(value)) if value not in (None, "") else None


def _bool(value: Any) -> bool:
    return str(value).lower() in {"true", "1", "yes", "y"}


def _json_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    return json.loads(value)


def _normalize_district(value: str | None, guard: CityGuard, name: str) -> str | None:
    if not value:
        return None
    normalized = guard.normalize_districts([value])
    if not normalized:
        raise ValueError(f"候选区域行政区不属于上海行政区：{name} district={value!r}")
    return normalized[0]


def main() -> None:
    init_db()
    guard = CityGuard()
    path = Path("data/demo/shanghai_candidate_areas.csv")
    with SessionLocal() as session, path.open(encoding="utf-8", newline="") as fp:
        count = 0
        for row in csv.DictReader(fp):
            guard.assert_request_allowed(f"{row['city']} {row['district']} {row['name']}")
            guard.assert_point_in_shanghai(lng=float(row["lng"]), lat=float(row["lat"]), label=row["name"])
            area = session.scalar(select(CandidateArea).where(CandidateArea.name == row["name"]))
            if area is None:
                area = CandidateArea(name=row["name"])
                session.add(area)
            area.area_type = row["area_type"]
            area.city = "上海"
            area.district = _normalize_district(row.get("district"), guard, row["name"])
            area.lng = float(row["lng"])
            area.lat = float(row["lat"])
            area.coordinate_system = "gcj02"
            area.tags = _json_list(row.get("tags"))
            area.typical_rent_1br = _int(row.get("typical_rent_1br"))
            area.typical_rent_2br = _int(row.get("typical_rent_2br"))
            area.metro_lines = _json_list(row.get("metro_lines"))
            area.description = row.get("description") or None
            area.is_demo = _bool(row.get("is_demo"))
            count += 1
        session.commit()
    print(f"Seeded/updated {count} Shanghai candidate areas.")


if __name__ == "__main__":
    main()
