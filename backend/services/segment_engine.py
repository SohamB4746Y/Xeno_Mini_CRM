from __future__ import annotations

# Segment Engine: builds SQL WHERE clauses from filter_rules JSONB at query time.
# Tradeoff: on-demand evaluation is simple and correct for demo scale (<10k customers).
# At production scale, segment membership would be pre-computed into a
# customer_segment_memberships table and refreshed on a schedule or event trigger.

from datetime import timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Interval, Select, all_, and_, any_, bindparam, func, or_, select, update
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only
from sqlalchemy.sql.elements import ColumnElement

from models import Customer, Segment

SUPPORTED_FIELDS = {
    "total_orders": Customer.total_orders,
    "total_spend": Customer.total_spend,
    "last_purchase_at": Customer.last_purchase_at,
    "tier": Customer.tier,
    "preferred_channel": Customer.preferred_channel,
    "city": Customer.city,
    "state": Customer.state,
    "gender": Customer.gender,
    "age": Customer.age,
    "created_at": Customer.created_at,
}

SUPPORTED_OPERATORS = {
    "eq",
    "neq",
    "gte",
    "lte",
    "gt",
    "lt",
    "in",
    "not_in",
    "days_ago_gte",
    "days_ago_lte",
    "is_null",
    "is_not_null",
}

CUSTOMER_LOAD_COLUMNS = (
    Customer.id,
    Customer.name,
    Customer.email,
    Customer.tier,
    Customer.city,
    Customer.total_spend,
    Customer.total_orders,
    Customer.last_purchase_at,
)


def _as_dict(filter_rules: dict[str, Any] | Any) -> dict[str, Any]:
    if hasattr(filter_rules, "model_dump"):
        return filter_rules.model_dump()
    if isinstance(filter_rules, dict):
        return filter_rules
    raise ValueError("filter_rules must be a dict or Pydantic model")


def _field_expression(field_name: str) -> Any:
    try:
        return SUPPORTED_FIELDS[field_name]
    except KeyError as exc:
        supported = ", ".join(sorted(SUPPORTED_FIELDS))
        raise ValueError(f"Unsupported segment field '{field_name}'. Supported fields: {supported}") from exc


def _validate_operator(operator: str) -> None:
    if operator not in SUPPORTED_OPERATORS:
        supported = ", ".join(sorted(SUPPORTED_OPERATORS))
        raise ValueError(f"Unsupported segment operator '{operator}'. Supported operators: {supported}")


def _parameter_name(index: int, suffix: str = "value") -> str:
    return f"segment_{suffix}_{index}"


def _array_parameter(column: Any, value: Any, parameter_name: str) -> Any:
    if not isinstance(value, list) or not value:
        raise ValueError("Operators 'in' and 'not_in' require a non-empty list value")
    return bindparam(parameter_name, value=value, type_=ARRAY(column.type))


def _scalar_parameter(value: Any, parameter_name: str) -> Any:
    if isinstance(value, float):
        value = Decimal(str(value))
    return bindparam(parameter_name, value=value)


def _days_interval(value: Any, parameter_name: str) -> Any:
    try:
        days = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("days_ago operators require an integer day value") from exc
    if days < 0:
        raise ValueError("days_ago operators require a non-negative day value")
    return bindparam(parameter_name, value=timedelta(days=days), type_=Interval())


def _condition_expression(condition: dict[str, Any], index: int) -> ColumnElement[bool]:
    field_name = condition.get("field")
    operator = condition.get("operator")
    if not isinstance(field_name, str) or not field_name:
        raise ValueError("Each segment condition must include a non-empty field")
    if not isinstance(operator, str) or not operator:
        raise ValueError("Each segment condition must include a non-empty operator")

    _validate_operator(operator)
    column = _field_expression(field_name)

    if operator == "is_null":
        return column.is_(None)
    if operator == "is_not_null":
        return column.is_not(None)

    if "value" not in condition:
        raise ValueError(f"Operator '{operator}' requires a value")

    value = condition["value"]
    parameter_name = _parameter_name(index)

    if operator == "eq":
        return column == _scalar_parameter(value, parameter_name)
    if operator == "neq":
        return column != _scalar_parameter(value, parameter_name)
    if operator == "gte":
        return column >= _scalar_parameter(value, parameter_name)
    if operator == "lte":
        return column <= _scalar_parameter(value, parameter_name)
    if operator == "gt":
        return column > _scalar_parameter(value, parameter_name)
    if operator == "lt":
        return column < _scalar_parameter(value, parameter_name)
    if operator == "in":
        return column == any_(_array_parameter(column, value, parameter_name))
    if operator == "not_in":
        return column != all_(_array_parameter(column, value, parameter_name))
    if operator == "days_ago_gte":
        return column <= func.now() - _days_interval(value, parameter_name)
    if operator == "days_ago_lte":
        return column >= func.now() - _days_interval(value, parameter_name)

    raise ValueError(f"Unsupported segment operator '{operator}'")


def _where_clause(filter_rules: dict[str, Any] | Any) -> Optional[ColumnElement[bool]]:
    rules = _as_dict(filter_rules)
    operator = str(rules.get("operator", "AND")).upper()
    if operator not in {"AND", "OR"}:
        raise ValueError("Segment rule operator must be 'AND' or 'OR'")

    raw_conditions = rules.get("conditions", [])
    if raw_conditions is None:
        raw_conditions = []
    if not isinstance(raw_conditions, list):
        raise ValueError("Segment rule conditions must be a list")
    if not raw_conditions:
        return None

    expressions = []
    for index, raw_condition in enumerate(raw_conditions):
        if hasattr(raw_condition, "model_dump"):
            raw_condition = raw_condition.model_dump()
        if not isinstance(raw_condition, dict):
            raise ValueError("Each segment condition must be an object")
        expressions.append(_condition_expression(raw_condition, index))

    return and_(*expressions) if operator == "AND" else or_(*expressions)


def _customer_query(where_clause: Optional[ColumnElement[bool]]) -> Select[tuple[Customer]]:
    query = select(Customer).options(load_only(*CUSTOMER_LOAD_COLUMNS)).order_by(Customer.updated_at.desc())
    if where_clause is not None:
        query = query.where(where_clause)
    return query


def _count_query(where_clause: Optional[ColumnElement[bool]]) -> Select[tuple[int]]:
    query = select(func.count(Customer.id))
    if where_clause is not None:
        query = query.where(where_clause)
    return query


async def evaluate_segment(
    db: AsyncSession,
    filter_rules: dict[str, Any],
    limit: Optional[int] = None,
    offset: int = 0,
) -> tuple[list[Customer], int]:
    """
    Evaluates a segment's filter rules against the customers table.
    Returns (matching_customers, total_count).
    limit=None means return all matching customers.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    if offset < 0:
        raise ValueError("offset must be non-negative")

    where = _where_clause(filter_rules)
    total = int(await db.scalar(_count_query(where)) or 0)

    query = _customer_query(where).offset(offset)
    if limit is not None:
        query = query.limit(limit)
    result = await db.scalars(query)
    return list(result.unique().all()), total


async def preview_segment(
    db: AsyncSession,
    filter_rules: dict[str, Any],
    sample_size: int = 5,
) -> tuple[int, list[Customer]]:
    """
    Returns (total_count, sample_customers) for a segment preview.
    Does NOT save anything to database.
    """
    if sample_size < 0:
        raise ValueError("sample_size must be non-negative")
    customers, total = await evaluate_segment(db, filter_rules, limit=sample_size, offset=0)
    return total, customers


async def refresh_segment_count(
    db: AsyncSession,
    segment_id: UUID,
) -> int:
    """
    Re-evaluates a segment's filter_rules, updates customer_count in DB,
    returns the new count.
    """
    segment = await db.get(Segment, segment_id)
    if segment is None:
        raise ValueError(f"Segment '{segment_id}' was not found")

    _, total = await evaluate_segment(db, segment.filter_rules)
    await db.execute(
        update(Segment)
        .where(Segment.id == segment_id)
        .values(customer_count=total, updated_at=func.now())
    )
    await db.commit()
    return total
