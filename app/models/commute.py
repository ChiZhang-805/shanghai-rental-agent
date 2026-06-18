from datetime import datetime
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CommuteCache(Base):
    __tablename__ = "commute_cache"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(32), default="amap")
    mode: Mapped[str] = mapped_column(String(32), index=True)

    origin_lng: Mapped[float] = mapped_column(Float)
    origin_lat: Mapped[float] = mapped_column(Float)
    destination_lng: Mapped[float] = mapped_column(Float)
    destination_lat: Mapped[float] = mapped_column(Float)
    city1: Mapped[str | None] = mapped_column(String(32), nullable=True)
    city2: Mapped[str | None] = mapped_column(String(32), nullable=True)

    cache_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    route_status: Mapped[str] = mapped_column(String(32))
    duration_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transfers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    walking_distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    taxi_cost_yuan: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)

    route_polyline: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

