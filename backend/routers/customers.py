from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models import Customer, Order
from schemas.customer import CustomerCreate, CustomerListResponse, CustomerResponse, CustomerUpdate
from schemas.order import OrderListResponse

router = APIRouter()


async def _get_customer_or_404(db: AsyncSession, customer_id: UUID) -> Customer:
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.get("/", response_model=CustomerListResponse)
async def list_customers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tier: Optional[str] = None,
    city: Optional[str] = None,
    gender: Optional[str] = None,
    preferred_channel: Optional[str] = None,
    min_spend: Optional[Decimal] = None,
    max_spend: Optional[Decimal] = None,
    min_orders: Optional[int] = None,
    max_orders: Optional[int] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> CustomerListResponse:
    filters = []
    if tier is not None:
        filters.append(Customer.tier == tier)
    if city is not None:
        filters.append(Customer.city == city)
    if gender is not None:
        filters.append(Customer.gender == gender)
    if preferred_channel is not None:
        filters.append(Customer.preferred_channel == preferred_channel)
    if min_spend is not None:
        filters.append(Customer.total_spend >= min_spend)
    if max_spend is not None:
        filters.append(Customer.total_spend <= max_spend)
    if min_orders is not None:
        filters.append(Customer.total_orders >= min_orders)
    if max_orders is not None:
        filters.append(Customer.total_orders <= max_orders)
    if search:
        search_pattern = f"%{search}%"
        filters.append(or_(Customer.name.ilike(search_pattern), Customer.email.ilike(search_pattern)))

    count_query = select(func.count(Customer.id))
    query = select(Customer).order_by(Customer.created_at.desc())
    if filters:
        count_query = count_query.where(*filters)
        query = query.where(*filters)

    total = int(await db.scalar(count_query) or 0)
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    customers = list(result.scalars().all())
    return CustomerListResponse(items=customers, total=total, page=page, page_size=page_size)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Customer:
    return await _get_customer_or_404(db, customer_id)


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreate,
    db: AsyncSession = Depends(get_db),
) -> Customer:
    customer = Customer(**payload.model_dump())
    db.add(customer)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer with this email already exists",
        ) from exc
    await db.refresh(customer)
    return customer


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
) -> Customer:
    customer = await _get_customer_or_404(db, customer_id)
    updates = payload.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(customer, field, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer with this email already exists",
        ) from exc
    await db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    customer = await _get_customer_or_404(db, customer_id)
    await db.delete(customer)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{customer_id}/orders", response_model=OrderListResponse)
async def list_customer_orders(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> OrderListResponse:
    await _get_customer_or_404(db, customer_id)
    result = await db.execute(
        select(Order)
        .where(Order.customer_id == customer_id)
        .order_by(Order.order_date.desc())
    )
    orders = list(result.scalars().all())
    return OrderListResponse(items=orders, total=len(orders))
