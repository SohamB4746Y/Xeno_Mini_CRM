from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CampaignAnalyticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    total_sent: int
    total_delivered: int
    total_failed: int
    total_opened: int
    total_read: int
    total_clicked: int
    total_converted: int
    delivery_rate: Decimal
    open_rate: Decimal
    click_rate: Decimal
    conversion_rate: Decimal
    updated_at: datetime


class DashboardMetrics(BaseModel):
    total_customers: int
    active_segments: int
    campaigns_this_month: int
    total_communications_sent: int
    average_delivery_rate: float
    average_open_rate: float
    best_campaign: Optional[dict[str, Any]] = None
    recent_campaigns: list["CampaignResponse"]


from schemas.campaign import CampaignResponse

DashboardMetrics.model_rebuild()
