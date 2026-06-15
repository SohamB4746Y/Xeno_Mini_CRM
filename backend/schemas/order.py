from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrderItem(BaseModel):
    product_id: str
    name: str
    category: str
    quantity: int
    price: Decimal


class OrderCreate(BaseModel):
    customer_id: UUID
    order_date: datetime
    amount: Decimal
    status: str = "completed"
    channel: str = "website"
    items: list[OrderItem]


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    order_date: datetime
    amount: Decimal
    status: str
    channel: str
    items: list[OrderItem]
    created_at: datetime


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total: int
