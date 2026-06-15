from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CommunicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    customer_id: UUID
    channel: str
    personalized_message: str
    status: str
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    converted_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    channel_message_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CommunicationListResponse(BaseModel):
    items: list[CommunicationResponse]
    total: int
    campaign_id: UUID


class WebhookPayload(BaseModel):
    communication_id: UUID
    event: str
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
