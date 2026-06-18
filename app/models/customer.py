from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone_masked: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="internal")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    needs: Mapped[list["CustomerNeed"]] = relationship(back_populates="customer")


class CustomerNeed(Base):
    __tablename__ = "customer_needs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    city: Mapped[str] = mapped_column(String(32), default="上海", index=True)
    purpose: Mapped[str | None] = mapped_column(String(16), nullable=True)
    districts: Mapped[list[str]] = mapped_column(JSON, default=list)
    budget_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rooms_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rooms_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area_min: Mapped[float | None] = mapped_column(nullable=True)
    area_max: Mapped[float | None] = mapped_column(nullable=True)
    commute_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    structured: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped[Customer | None] = relationship(back_populates="needs")

