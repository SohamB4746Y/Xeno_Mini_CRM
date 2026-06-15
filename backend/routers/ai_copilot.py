from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from services.ai_agent import generate_proactive_insights, process_chat

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str
    tools_used: list[str]
    actions_taken: list[dict[str, Any]]
    conversation_history: list[dict[str, Any]]


class OpportunityCard(BaseModel):
    id: str
    priority: str
    icon: str
    title: str
    description: str
    suggested_action: str
    estimated_audience: Optional[int]
    quick_prompt: str
    suggested_channel: Optional[str] = None
    suggested_filter_rules: Optional[dict[str, Any]] = None


class InsightsResponse(BaseModel):
    opportunities: list[OpportunityCard]
    generated_at: str


class QuickLaunchRequest(BaseModel):
    quick_prompt: str
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    result = await process_chat(
        db=db,
        conversation_history=request.conversation_history,
        new_message=request.message,
    )
    return ChatResponse(**result)


@router.get("/insights", response_model=InsightsResponse)
async def get_insights(
    db: AsyncSession = Depends(get_db),
) -> InsightsResponse:
    cards = await generate_proactive_insights(db)
    return InsightsResponse(
        opportunities=cards,
        generated_at=datetime.now(UTC).isoformat(),
    )


@router.post("/quick-launch", response_model=ChatResponse)
async def quick_launch(
    request: QuickLaunchRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    enhanced_prompt = (
        f"{request.quick_prompt}. "
        "I have reviewed the plan and I confirm I want to launch this campaign. "
        "Please proceed with creating the segment and launching the campaign."
    )
    result = await process_chat(
        db=db,
        conversation_history=request.conversation_history,
        new_message=enhanced_prompt,
    )
    return ChatResponse(**result)
