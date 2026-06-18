from datetime import datetime
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserAnchor(Base):
    __tablename__ = "user_anchors"
    __table_args__ = (CheckConstraint("city = '上海'", name="ck_user_anchors_city_shanghai"),)

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("customers.id"), index=True, nullable=True)
    label: Mapped[str] = mapped_column(String(128))
    anchor_type: Mapped[str] = mapped_column(String(64), default="workplace")
    address: Mapped[str] = mapped_column(String(500))
    city: Mapped[str] = mapped_column(String(32), default="上海")
    district: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    coordinate_system: Mapped[str] = mapped_column(String(32), default="gcj02")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    arrival_time: Mapped[str | None] = mapped_column(String(16), nullable=True)
    allowed_modes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CandidateArea(Base):
    __tablename__ = "candidate_areas"
    __table_args__ = (CheckConstraint("city = '上海'", name="ck_candidate_areas_city_shanghai"),)

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    area_type: Mapped[str] = mapped_column(String(64))
    city: Mapped[str] = mapped_column(String(32), default="上海", index=True)
    district: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    lng: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)
    coordinate_system: Mapped[str] = mapped_column(String(32), default="gcj02")
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    typical_rent_1br: Mapped[int | None] = mapped_column(nullable=True)
    typical_rent_2br: Mapped[int | None] = mapped_column(nullable=True)
    metro_lines: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(default=True)
