from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CampaignCreate(BaseModel):
    name: str
    segment_id: Optional[UUID] = None
    channel: str
    message_template: str
    ai_generated_message: bool = False
    ai_generated_segment: bool = False
    scheduled_at: Optional[datetime] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    message_template: Optional[str] = None
    status: Optional[str] = None


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    segment_id: Optional[UUID] = None
    channel: str
    message_template: str
    ai_generated_message: bool
    ai_generated_segment: bool
    status: str
    total_recipients: int
    scheduled_at: Optional[datetime] = None
    launched_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    analytics: Optional["CampaignAnalyticsResponse"] = None


class CampaignListResponse(BaseModel):
    items: list[CampaignResponse]
    total: int


from schemas.analytics import CampaignAnalyticsResponse

CampaignResponse.model_rebuild()
