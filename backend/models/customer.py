from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID as PythonUUID

from sqlalchemy import DateTime, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[str] = mapped_column(Text, nullable=False, default="bronze", server_default=text("'bronze'"))
    preferred_channel: Mapped[str] = mapped_column(Text, nullable=False, default="email", server_default=text("'email'"))
    total_spend: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"))
    total_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    last_purchase_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    orders = relationship("Order", back_populates="customer", lazy="selectin")

    @property
    def days_since_purchase(self) -> Optional[int]:
        if self.last_purchase_at is None:
            return None
        now = datetime.now(self.last_purchase_at.tzinfo)
        return max((now - self.last_purchase_at).days, 0)
