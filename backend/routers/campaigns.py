from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.database import get_db
from models import Campaign, CampaignAnalytics, Communication, Customer, Segment
from schemas.campaign import CampaignCreate, CampaignListResponse, CampaignResponse, CampaignUpdate
from schemas.communication import CommunicationListResponse
from services.campaign_launcher import dispatch_campaign
from services.message_renderer import render_message_for_customer
from services.segment_engine import evaluate_segment

router = APIRouter()

ALLOWED_STATUS_TRANSITIONS = {
    "draft": {"paused"},
    "running": {"paused"},
    "paused": {"running"},
}


async def _get_campaign_or_404(db: AsyncSession, campaign_id: UUID) -> Campaign:
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.analytics))
        .where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign


async def _load_full_customers(db: AsyncSession, customers: list[Customer]) -> list[Customer]:
    customer_ids = [customer.id for customer in customers]
    if not customer_ids:
        return []
    result = await db.execute(select(Customer).where(Customer.id.in_(customer_ids)))
    full_customers = list(result.scalars().all())
    customer_by_id = {customer.id: customer for customer in full_customers}
    return [customer_by_id[customer_id] for customer_id in customer_ids if customer_id in customer_by_id]


@router.get("/", response_model=CampaignListResponse)
async def list_campaigns(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> CampaignListResponse:
    filters = []
    if status_filter is not None:
        filters.append(Campaign.status == status_filter)

    count_query = select(func.count(Campaign.id))
    query = select(Campaign).options(selectinload(Campaign.analytics)).order_by(Campaign.created_at.desc())
    if filters:
        count_query = count_query.where(*filters)
        query = query.where(*filters)

    total = int(await db.scalar(count_query) or 0)
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    return CampaignListResponse(items=list(result.scalars().all()), total=total)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Campaign:
    return await _get_campaign_or_404(db, campaign_id)


@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreate,
    db: AsyncSession = Depends(get_db),
) -> Campaign:
    if payload.segment_id is not None:
        segment = await db.get(Segment, payload.segment_id)
        if segment is None or not segment.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    campaign = Campaign(**payload.model_dump())
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return await _get_campaign_or_404(db, campaign.id)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: UUID,
    payload: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
) -> Campaign:
    campaign = await _get_campaign_or_404(db, campaign_id)
    updates = payload.model_dump(exclude_none=True)

    next_status = updates.get("status")
    if next_status is not None:
        allowed_next_statuses = ALLOWED_STATUS_TRANSITIONS.get(campaign.status, set())
        if next_status not in allowed_next_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot change campaign status from {campaign.status} to {next_status}",
            )

    for field, value in updates.items():
        setattr(campaign, field, value)

    await db.commit()
    await db.refresh(campaign)
    return await _get_campaign_or_404(db, campaign_id)


@router.post("/{campaign_id}/launch")
async def launch_campaign(
    campaign_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    campaign = await _get_campaign_or_404(db, campaign_id)
    if campaign.status not in {"draft", "paused"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign must be in draft or paused status to launch",
        )
    if campaign.segment_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign must have a segment")

    segment = await db.get(Segment, campaign.segment_id)
    if segment is None or not segment.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    try:
        segment_customers, total_count = await evaluate_segment(db, segment.filter_rules)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if total_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Segment has no customers")

    customers = await _load_full_customers(db, segment_customers)
    await db.execute(delete(Communication).where(Communication.campaign_id == campaign.id))
    await db.execute(delete(CampaignAnalytics).where(CampaignAnalytics.campaign_id == campaign.id))

    for customer in customers:
        personalized_message = await render_message_for_customer(db, campaign.message_template, customer)
        db.add(
            Communication(
                campaign_id=campaign.id,
                customer_id=customer.id,
                channel=campaign.channel,
                personalized_message=personalized_message,
                status="pending",
            )
        )

    db.add(CampaignAnalytics(campaign_id=campaign.id))
    campaign.status = "running"
    campaign.launched_at = datetime.now(UTC)
    campaign.completed_at = None
    campaign.total_recipients = len(customers)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Campaign communications already exist for one or more customers",
        ) from exc

    background_tasks.add_task(dispatch_campaign, campaign.id)
    return {
        "campaign_id": str(campaign.id),
        "status": "running",
        "total_recipients": len(customers),
        "message": "Campaign launched. Communications being dispatched.",
    }


@router.get("/{campaign_id}/communications", response_model=CommunicationListResponse)
async def list_campaign_communications(
    campaign_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> CommunicationListResponse:
    await _get_campaign_or_404(db, campaign_id)
    filters = [Communication.campaign_id == campaign_id]
    if status_filter is not None:
        filters.append(Communication.status == status_filter)

    total = int(await db.scalar(select(func.count(Communication.id)).where(*filters)) or 0)
    result = await db.execute(
        select(Communication)
        .where(*filters)
        .order_by(Communication.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return CommunicationListResponse(items=list(result.scalars().all()), total=total, campaign_id=campaign_id)


@router.delete("/{campaign_id}", status_code=status.HTTP_200_OK)
async def delete_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    campaign = await _get_campaign_or_404(db, campaign_id)
    name = campaign.name
    await db.execute(delete(Communication).where(Communication.campaign_id == campaign_id))
    await db.execute(delete(CampaignAnalytics).where(CampaignAnalytics.campaign_id == campaign_id))
    await db.delete(campaign)
    await db.commit()
    return {"deleted": True, "campaign_id": str(campaign_id), "campaign_name": name}


@router.post("/cleanup-zombies")
async def cleanup_zombie_campaigns(
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Remove campaigns that were 'launched' but have 0 sent — failed dispatches."""
    zombie_query = (
        select(Campaign.id, Campaign.name)
        .join(CampaignAnalytics, CampaignAnalytics.campaign_id == Campaign.id)
        .where(
            Campaign.status == "running",
            CampaignAnalytics.total_sent == 0,
            CampaignAnalytics.total_delivered == 0,
        )
    )
    result = await db.execute(zombie_query)
    zombies = result.all()

    deleted = []
    for campaign_id, campaign_name in zombies:
        await db.execute(delete(Communication).where(Communication.campaign_id == campaign_id))
        await db.execute(delete(CampaignAnalytics).where(CampaignAnalytics.campaign_id == campaign_id))
        await db.execute(delete(Campaign).where(Campaign.id == campaign_id))
        deleted.append({"campaign_id": str(campaign_id), "name": campaign_name})

    await db.commit()
    return {"deleted_count": len(deleted), "deleted_campaigns": deleted}

