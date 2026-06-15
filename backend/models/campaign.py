from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID as PythonUUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    segment_id: Mapped[Optional[PythonUUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("segments.id", ondelete="SET NULL"), nullable=True)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    ai_generated_message: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    ai_generated_segment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft", server_default=text("'draft'"))
    total_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    launched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    segment = relationship("Segment", back_populates="campaigns")
    communications = relationship("Communication", back_populates="campaign", lazy="selectin")
    analytics = relationship("CampaignAnalytics", back_populates="campaign", uselist=False)
