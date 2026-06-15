from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.database import get_db
from models import Campaign, CampaignAnalytics, Communication, Customer, Segment
from schemas.analytics import CampaignAnalyticsResponse, DashboardMetrics

router = APIRouter()


@router.get("/dashboard", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
) -> DashboardMetrics:
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_customers = int(await db.scalar(select(func.count(Customer.id))) or 0)
    active_segments = int(await db.scalar(select(func.count(Segment.id)).where(Segment.is_active.is_(True))) or 0)
    campaigns_this_month = int(
        await db.scalar(select(func.count(Campaign.id)).where(Campaign.created_at >= month_start)) or 0
    )
    total_communications_sent = int(await db.scalar(select(func.coalesce(func.sum(CampaignAnalytics.total_sent), 0))) or 0)
    average_delivery_rate = float(
        await db.scalar(
            select(func.coalesce(func.avg(CampaignAnalytics.delivery_rate), 0))
            .where(CampaignAnalytics.total_sent > 0)
        )
        or 0
    )
    average_open_rate = float(
        await db.scalar(
            select(func.coalesce(func.avg(CampaignAnalytics.open_rate), 0))
            .where(CampaignAnalytics.total_sent > 0)
        )
        or 0
    )

    best_result = await db.execute(
        select(Campaign.name, CampaignAnalytics.open_rate, CampaignAnalytics.click_rate)
        .join(CampaignAnalytics, CampaignAnalytics.campaign_id == Campaign.id)
        .order_by(CampaignAnalytics.open_rate.desc())
        .limit(1)
    )
    best_row = best_result.one_or_none()
    best_campaign: dict[str, Any] | None = None
    if best_row is not None:
        best_campaign = {
            "name": best_row.name,
            "open_rate": float(best_row.open_rate),
            "click_rate": float(best_row.click_rate),
        }

    recent_result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.analytics))
        .order_by(Campaign.created_at.desc())
        .limit(5)
    )

    return DashboardMetrics(
        total_customers=total_customers,
        active_segments=active_segments,
        campaigns_this_month=campaigns_this_month,
        total_communications_sent=total_communications_sent,
        average_delivery_rate=average_delivery_rate,
        average_open_rate=average_open_rate,
        best_campaign=best_campaign,
        recent_campaigns=list(recent_result.scalars().all()),
    )


@router.get("/campaigns")
async def list_campaign_analytics(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(
            CampaignAnalytics.campaign_id,
            Campaign.name.label("campaign_name"),
            Campaign.channel,
            Campaign.status,
            CampaignAnalytics.total_sent,
            CampaignAnalytics.delivery_rate,
            CampaignAnalytics.open_rate,
            CampaignAnalytics.click_rate,
            CampaignAnalytics.conversion_rate,
            Campaign.launched_at,
        )
        .join(Campaign, Campaign.id == CampaignAnalytics.campaign_id)
        .order_by(desc(Campaign.launched_at).nullslast())
    )
    return [
        {
            "campaign_id": row.campaign_id,
            "campaign_name": row.campaign_name,
            "channel": row.channel,
            "status": row.status,
            "total_sent": row.total_sent,
            "delivery_rate": row.delivery_rate,
            "open_rate": row.open_rate,
            "click_rate": row.click_rate,
            "conversion_rate": row.conversion_rate,
            "launched_at": row.launched_at,
        }
        for row in result.all()
    ]


@router.get("/campaigns/{campaign_id}", response_model=CampaignAnalyticsResponse)
async def get_campaign_analytics(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CampaignAnalytics:
    campaign_exists = await db.scalar(select(Campaign.id).where(Campaign.id == campaign_id))
    if campaign_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    result = await db.execute(
        select(CampaignAnalytics).where(CampaignAnalytics.campaign_id == campaign_id)
    )
    analytics = result.scalar_one_or_none()
    if analytics is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign analytics not found")
    return analytics
