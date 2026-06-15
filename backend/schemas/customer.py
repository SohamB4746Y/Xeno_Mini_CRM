from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    name: str
    email: str
    phone: str
    city: str
    state: str
    age: int
    gender: str
    preferred_channel: str = "email"


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    preferred_channel: Optional[str] = None
    tier: Optional[str] = None


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    phone: str
    city: str
    state: str
    age: int
    gender: str
    tier: str
    preferred_channel: str
    total_spend: Decimal
    total_orders: int
    last_purchase_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    days_since_purchase: Optional[int] = None


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    total: int
    page: int
    page_size: int


class CustomerFilterParams(BaseModel):
    tier: Optional[str] = None
    city: Optional[str] = None
    gender: Optional[str] = None
    preferred_channel: Optional[str] = None
    min_spend: Optional[Decimal] = None
    max_spend: Optional[Decimal] = None
    min_orders: Optional[int] = None
    max_orders: Optional[int] = None
