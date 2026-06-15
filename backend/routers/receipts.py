from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models import Campaign, CampaignAnalytics, Communication
from schemas.communication import WebhookPayload
from utils.idempotency import check_and_record_event

router = APIRouter()
logger = logging.getLogger(__name__)

EVENT_COUNTERS = {
    "sent": "total_sent",
    "delivered": "total_delivered",
    "failed": "total_failed",
    "opened": "total_opened",
    "read": "total_read",
    "clicked": "total_clicked",
    "converted": "total_converted",
}

VALID_TRANSITIONS = {
    "sent": {"pending"},
    "delivered": {"sent"},
    "opened": {"delivered"},
    "read": {"opened"},
    "clicked": {"read"},
    "converted": {"clicked"},
    "failed": {"pending", "sent"},
}

TIMESTAMP_FIELDS = {
    "sent": "sent_at",
    "delivered": "delivered_at",
    "opened": "opened_at",
    "read": "read_at",
    "clicked": "clicked_at",
    "converted": "converted_at",
    "failed": "failed_at",
}


def _normalized_timestamp(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp


def _analytics_update_values(event_type: str) -> dict[object, object]:
    sent_increment = 1 if event_type == "sent" else 0
    delivered_increment = 1 if event_type == "delivered" else 0
    failed_increment = 1 if event_type == "failed" else 0
    opened_increment = 1 if event_type == "opened" else 0
    read_increment = 1 if event_type == "read" else 0
    clicked_increment = 1 if event_type == "clicked" else 0
    converted_increment = 1 if event_type == "converted" else 0

    new_total_sent = CampaignAnalytics.total_sent + sent_increment
    new_total_delivered = CampaignAnalytics.total_delivered + delivered_increment
    new_total_failed = CampaignAnalytics.total_failed + failed_increment
    new_total_opened = CampaignAnalytics.total_opened + opened_increment
    new_total_read = CampaignAnalytics.total_read + read_increment
    new_total_clicked = CampaignAnalytics.total_clicked + clicked_increment
    new_total_converted = CampaignAnalytics.total_converted + converted_increment

    hundred = Decimal("100.00")

    return {
        CampaignAnalytics.total_sent: new_total_sent,
        CampaignAnalytics.total_delivered: new_total_delivered,
        CampaignAnalytics.total_failed: new_total_failed,
        CampaignAnalytics.total_opened: new_total_opened,
        CampaignAnalytics.total_read: new_total_read,
        CampaignAnalytics.total_clicked: new_total_clicked,
        CampaignAnalytics.total_converted: new_total_converted,
        CampaignAnalytics.delivery_rate: case(
            (new_total_sent > 0, new_total_delivered * hundred / new_total_sent),
            else_=0,
        ),
        CampaignAnalytics.open_rate: case(
            (new_total_delivered > 0, new_total_opened * hundred / new_total_delivered),
            else_=0,
        ),
        CampaignAnalytics.click_rate: case(
            (new_total_delivered > 0, new_total_clicked * hundred / new_total_delivered),
            else_=0,
        ),
        CampaignAnalytics.conversion_rate: case(
            (new_total_sent > 0, new_total_converted * hundred / new_total_sent),
            else_=0,
        ),
        CampaignAnalytics.updated_at: func.now(),
    }


async def _ensure_campaign_analytics(db: AsyncSession, campaign_id: object) -> None:
    statement = (
        insert(CampaignAnalytics)
        .values(campaign_id=campaign_id)
        .on_conflict_do_nothing(index_elements=["campaign_id"])
    )
    await db.execute(statement)


async def _mark_campaign_complete_if_ready(db: AsyncSession, campaign_id: object) -> None:
    unfinished_count = int(
        await db.scalar(
            select(func.count(Communication.id))
            .where(
                Communication.campaign_id == campaign_id,
                Communication.status.in_(["pending", "sent"]),
            )
        )
        or 0
    )
    if unfinished_count == 0:
        await db.execute(
            update(Campaign)
            .where(Campaign.id == campaign_id)
            .values(status="completed", completed_at=func.now(), updated_at=func.now())
        )


@router.post("/webhook")
async def receive_webhook(
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    event_type = payload.event
    if event_type not in EVENT_COUNTERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported webhook event")

    event_payload = payload.model_dump(mode="json")

    async with db.begin():
        is_new_event = await check_and_record_event(
            db,
            payload.communication_id,
            event_type,
            event_payload,
        )
        if not is_new_event:
            communication = await db.get(Communication, payload.communication_id)
            if communication is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication not found")
            return {"status": "already processed", "event": event_type}

        communication = await db.get(Communication, payload.communication_id)
        if communication is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication not found")

        if communication.status not in VALID_TRANSITIONS[event_type]:
            logger.warning(
                "Ignoring invalid communication state transition",
                extra={
                    "communication_id": str(communication.id),
                    "current_status": communication.status,
                    "event_type": event_type,
                },
            )
            return {"status": "ignored", "event": event_type}

        timestamp = _normalized_timestamp(payload.timestamp)
        communication.status = event_type
        setattr(communication, TIMESTAMP_FIELDS[event_type], timestamp)
        communication.updated_at = datetime.now(UTC)
        if event_type == "failed":
            communication.failure_reason = str(payload.metadata.get("reason", "Unknown"))

        await _ensure_campaign_analytics(db, communication.campaign_id)
        await db.execute(
            update(CampaignAnalytics)
            .where(CampaignAnalytics.campaign_id == communication.campaign_id)
            .values(_analytics_update_values(event_type))
        )
        await _mark_campaign_complete_if_ready(db, communication.campaign_id)

    return {"status": "processed", "event": event_type}
