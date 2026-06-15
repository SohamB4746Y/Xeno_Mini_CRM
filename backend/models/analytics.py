from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID as PythonUUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class CampaignAnalytics(Base):
    __tablename__ = "campaign_analytics"
    __table_args__ = (UniqueConstraint("campaign_id"),)

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    campaign_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    total_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    total_delivered: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    total_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    total_opened: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    total_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    total_clicked: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    total_converted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    delivery_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default=text("0"))
    open_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default=text("0"))
    click_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default=text("0"))
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    campaign = relationship("Campaign", back_populates="analytics")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("communication_id", "event_type"),)

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    communication_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("communications.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    communication = relationship("Communication", back_populates="webhook_events")
