from datetime import date, datetime
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RentalListing(Base):
    __tablename__ = "rental_listings"
    __table_args__ = (CheckConstraint("city = '上海'", name="ck_rental_listings_city_shanghai"),)

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    external_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="demo", index=True)
    title: Mapped[str] = mapped_column(String(255))

    city: Mapped[str] = mapped_column(String(32), index=True, default="上海")
    district: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    subdistrict: Mapped[str | None] = mapped_column(String(64), nullable=True)
    community_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    coordinate_system: Mapped[str] = mapped_column(String(32), default="gcj02")

    rent_monthly: Mapped[int] = mapped_column(Integer, index=True)
    deposit_months: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_cycle: Mapped[str | None] = mapped_column(String(64), nullable=True)

    rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    halls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orientation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decoration: Mapped[str | None] = mapped_column(String(64), nullable=True)
    has_elevator: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    nearby_metro_station: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metro_distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)

    available_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="available", index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    listing_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

