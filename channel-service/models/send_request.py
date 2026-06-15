from typing import Any

from pydantic import BaseModel, Field


class CommunicationItem(BaseModel):
    communication_id: str
    recipient: str
    channel: str
    message: str
    callback_url: str


class SendRequest(BaseModel):
    communications: list[CommunicationItem] = Field(min_length=1, max_length=50)


class SendResponse(BaseModel):
    accepted: int
    job_ids: list[str]
    status: str = "accepted"


class CallbackPayload(BaseModel):
    communication_id: str
    event: str
    timestamp: str
    metadata: dict[str, Any] = Field(default_factory=dict)
