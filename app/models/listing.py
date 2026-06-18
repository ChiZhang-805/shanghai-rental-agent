from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.vector import vector_column_type

DISTRICT_CHECK = (
    "'黄浦','徐汇','长宁','静安','普陀','虹口','杨浦','闵行','宝山','嘉定',"
    "'浦东','金山','松江','青浦','奉贤','崇明'"
)


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("city = '上海'", name="ck_listings_city_shanghai"),
        CheckConstraint(f"district IN ({DISTRICT_CHECK})", name="ck_listings_district_shanghai"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    city: Mapped[str] = mapped_column(String(32), default="上海", index=True)
    district: Mapped[str] = mapped_column(String(32), index=True)
    subdistrict: Mapped[str | None] = mapped_column(String(64), nullable=True)
    community_name: Mapped[str] = mapped_column(String(128), index=True)
    address_masked: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    purpose: Mapped[str] = mapped_column(String(16), index=True)  # sale | rent
    property_type: Mapped[str] = mapped_column(String(32), default="residential")
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    halls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area_sqm: Mapped[float] = mapped_column(Float)
    floor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_floors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orientation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decoration: Mapped[str | None] = mapped_column(String(64), nullable=True)
    built_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_elevator: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    sale_price_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rent_price_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)

    verification_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="missing", index=True)
    entrusted_status: Mapped[str] = mapped_column(String(32), default="missing", index=True)
    listing_status: Mapped[str] = mapped_column(String(32), default="active", index=True)

    source: Mapped[str] = mapped_column(String(64), default="internal")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    embedding: Mapped["ListingEmbedding | None"] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )


class ListingEmbedding(Base):
    __tablename__ = "listing_embeddings"

    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(vector_column_type(1536))
    text_hash: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    listing: Mapped[Listing] = relationship(back_populates="embedding")

