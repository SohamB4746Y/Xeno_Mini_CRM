from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models import Customer, Order
from schemas.order import OrderCreate, OrderListResponse, OrderResponse

router = APIRouter()


def _derive_tier(total_spend: Decimal, total_orders: int) -> str:
    if total_spend > Decimal("20000") or total_orders >= 10:
        return "platinum"
    if total_spend > Decimal("8000") or total_orders >= 5:
        return "gold"
    if total_spend > Decimal("2000") or total_orders >= 3:
        return "silver"
    return "bronze"


async def _get_order_or_404(db: AsyncSession, order_id: UUID) -> Order:
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


async def _recalculate_customer_metrics(db: AsyncSession, customer_id: UUID) -> None:
    result = await db.execute(
        select(
            func.coalesce(func.sum(Order.amount), Decimal("0")),
            func.count(Order.id),
            func.max(Order.order_date),
        ).where(Order.customer_id == customer_id, Order.status == "completed")
    )
    total_spend, total_orders, last_purchase_at = result.one()
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    customer.total_spend = total_spend
    customer.total_orders = int(total_orders)
    customer.last_purchase_at = last_purchase_at
    customer.tier = _derive_tier(total_spend, int(total_orders))


@router.get("/", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    customer_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
) -> OrderListResponse:
    filters = []
    if status_filter is not None:
        filters.append(Order.status == status_filter)
    if customer_id is not None:
        filters.append(Order.customer_id == customer_id)

    count_query = select(func.count(Order.id))
    query = select(Order).order_by(Order.order_date.desc())
    if filters:
        count_query = count_query.where(*filters)
        query = query.where(*filters)

    total = int(await db.scalar(count_query) or 0)
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    return OrderListResponse(items=list(result.scalars().all()), total=total)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Order:
    return await _get_order_or_404(db, order_id)


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
) -> Order:
    customer = await db.get(Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    order = Order(
        customer_id=payload.customer_id,
        order_date=payload.order_date,
        amount=payload.amount,
        status=payload.status,
        channel=payload.channel,
        items=[item.model_dump(mode="json") for item in payload.items],
    )
    db.add(order)

    if payload.status == "completed":
        await db.flush()
        await _recalculate_customer_metrics(db, payload.customer_id)

    await db.commit()
    await db.refresh(order)
    return order
