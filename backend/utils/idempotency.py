from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from models import WebhookEvent

logger = logging.getLogger(__name__)


async def check_and_record_event(
    db: AsyncSession,
    communication_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> bool:
    statement = (
        insert(WebhookEvent)
        .values(
            communication_id=communication_id,
            event_type=event_type,
            payload=payload,
        )
        .on_conflict_do_nothing(index_elements=["communication_id", "event_type"])
        .returning(WebhookEvent.id)
    )

    try:
        async with db.begin_nested():
            result = await db.execute(statement)
            return result.scalar_one_or_none() is not None
    except IntegrityError:
        return False
    except SQLAlchemyError:
        logger.exception(
            "Failed to record webhook event",
            extra={"communication_id": str(communication_id), "event_type": event_type},
        )
        return False
