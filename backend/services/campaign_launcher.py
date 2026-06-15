from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
import logging
import os
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.database import AsyncSessionLocal
from models import Communication
from services.message_renderer import render_message_for_customer

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


def _channel_service_url() -> str:
    url = os.getenv("CHANNEL_SERVICE_URL")
    if not url:
        raise RuntimeError("CHANNEL_SERVICE_URL is required")
    return url.rstrip("/")


def _crm_webhook_url() -> str:
    url = os.getenv("CRM_WEBHOOK_URL")
    if not url:
        raise RuntimeError("CRM_WEBHOOK_URL is required")
    return url


def _recipient_for_channel(communication: Communication) -> str:
    customer = communication.customer
    if communication.channel in {"whatsapp", "sms"}:
        return customer.phone
    return customer.email


def _chunks(items: Sequence[Communication], size: int) -> list[Sequence[Communication]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


async def mark_communications_failed(
    db: AsyncSession,
    communication_ids: list[UUID],
    reason: str,
) -> None:
    if not communication_ids:
        return

    await db.execute(
        update(Communication)
        .where(Communication.id.in_(communication_ids))
        .values(
            status="failed",
            failed_at=datetime.now(UTC),
            failure_reason=reason,
            updated_at=datetime.now(UTC),
        )
    )


async def _load_pending_communications(db: AsyncSession, campaign_id: UUID) -> list[Communication]:
    result = await db.execute(
        select(Communication)
        .options(selectinload(Communication.customer))
        .where(Communication.campaign_id == campaign_id, Communication.status == "pending")
        .order_by(Communication.created_at.asc())
    )
    return list(result.scalars().all())


async def _prepare_batch_payload(
    db: AsyncSession,
    communications: Sequence[Communication],
    callback_url: str,
) -> dict[str, list[dict[str, str]]]:
    payload_items: list[dict[str, str]] = []

    for communication in communications:
        personalized_message = await render_message_for_customer(
            db,
            communication.personalized_message,
            communication.customer,
        )
        communication.personalized_message = personalized_message
        payload_items.append(
            {
                "communication_id": str(communication.id),
                "recipient": _recipient_for_channel(communication),
                "channel": communication.channel,
                "message": personalized_message,
                "callback_url": callback_url,
            }
        )

    return {"communications": payload_items}


def _response_job_id(response_payload: dict[str, Any], communication_id: UUID) -> str | None:
    if isinstance(response_payload.get("job_id"), str):
        return response_payload["job_id"]

    jobs = response_payload.get("jobs")
    if isinstance(jobs, list):
        for job in jobs:
            if isinstance(job, dict) and str(job.get("communication_id")) == str(communication_id):
                job_id = job.get("job_id")
                return str(job_id) if job_id else None
    return None


async def _apply_channel_message_ids(
    db: AsyncSession,
    communications: Sequence[Communication],
    response_payload: dict[str, Any],
) -> None:
    for communication in communications:
        job_id = _response_job_id(response_payload, communication.id)
        if job_id is not None:
            communication.channel_message_id = job_id


async def dispatch_campaign(campaign_id: UUID) -> None:
    try:
        channel_service_url = _channel_service_url()
        callback_url = _crm_webhook_url()
    except RuntimeError:
        logger.exception("Campaign dispatch configuration is missing", extra={"campaign_id": str(campaign_id)})
        return

    async with AsyncSessionLocal() as db:
        communications = await _load_pending_communications(db, campaign_id)
        async with httpx.AsyncClient(timeout=10.0) as client:
            for batch in _chunks(communications, BATCH_SIZE):
                communication_ids = [communication.id for communication in batch]
                try:
                    payload = await _prepare_batch_payload(db, batch, callback_url)
                    response = await client.post(f"{channel_service_url}/send", json=payload)
                except httpx.HTTPError:
                    logger.exception("Channel service request failed", extra={"campaign_id": str(campaign_id)})
                    await mark_communications_failed(db, communication_ids, "Channel service error")
                    await db.commit()
                    continue

                if response.status_code != 202:
                    logger.error(
                        "Channel service rejected dispatch batch",
                        extra={"campaign_id": str(campaign_id), "status_code": response.status_code},
                    )
                    await mark_communications_failed(db, communication_ids, "Channel service error")
                    await db.commit()
                    continue

                try:
                    response_payload = response.json()
                except ValueError:
                    response_payload = {}

                await _apply_channel_message_ids(db, batch, response_payload)
                await db.commit()
                logger.info(
                    "Dispatched campaign batch",
                    extra={"campaign_id": str(campaign_id), "batch_size": len(batch)},
                )

    logger.info("Campaign dispatch complete", extra={"campaign_id": str(campaign_id)})
