from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Customer, Order


def render_message(template: str, customer: Customer, last_product: str) -> str:
    if customer.last_purchase_at is None:
        days_since_purchase = "a while"
    else:
        now = datetime.now(customer.last_purchase_at.tzinfo or UTC)
        days_since_purchase = str(max((now - customer.last_purchase_at).days, 0))

    substitutions = {
        "{{name}}": customer.name,
        "{{city}}": customer.city,
        "{{tier}}": customer.tier.title(),
        "{{last_product}}": last_product,
        "{{total_orders}}": str(customer.total_orders),
        "{{total_spend}}": f"₹{float(customer.total_spend):,.0f}",
        "{{days_since_purchase}}": days_since_purchase,
        "{{preferred_channel}}": customer.preferred_channel,
    }

    rendered_message = template
    for token, value in substitutions.items():
        rendered_message = rendered_message.replace(token, value)
    return rendered_message


async def get_last_product(db: AsyncSession, customer_id: UUID) -> str:
    result = await db.execute(
        select(Order)
        .where(Order.customer_id == customer_id, Order.status == "completed")
        .order_by(Order.order_date.desc())
        .limit(1)
    )
    order = result.scalar_one_or_none()
    if order is None or not order.items:
        return "your favourite ZURI pick"

    first_item = order.items[0]
    if isinstance(first_item, dict):
        return str(first_item.get("name") or "your favourite ZURI pick")
    return "your favourite ZURI pick"


async def render_message_for_customer(
    db: AsyncSession,
    template: str,
    customer: Customer,
) -> str:
    last_product = await get_last_product(db, customer.id)
    return render_message(template, customer, last_product)
