from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RepairTicket(Base):
    __tablename__ = "repair_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[str] = mapped_column(String(32), default="上海", index=True)
    issue_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    summary: Mapped[str] = mapped_column(Text)
    ticket_title: Mapped[str] = mapped_column(String(255))
    ticket_description: Mapped[str] = mapped_column(Text)
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

