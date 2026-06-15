from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models import Customer, Segment
from schemas.segment import FilterRules, SegmentCreate, SegmentListResponse, SegmentPreview, SegmentResponse, SegmentUpdate
from services.segment_engine import preview_segment, refresh_segment_count

router = APIRouter()


class SegmentPreviewRequest(BaseModel):
    filter_rules: FilterRules


async def _get_segment_or_404(db: AsyncSession, segment_id: UUID) -> Segment:
    segment = await db.get(Segment, segment_id)
    if segment is None or not segment.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    return segment


async def _load_full_customers(db: AsyncSession, customers: list[Customer]) -> list[Customer]:
    customer_ids = [customer.id for customer in customers]
    if not customer_ids:
        return []
    result = await db.execute(select(Customer).where(Customer.id.in_(customer_ids)))
    full_customers = list(result.scalars().all())
    customer_by_id = {customer.id: customer for customer in full_customers}
    return [customer_by_id[customer_id] for customer_id in customer_ids if customer_id in customer_by_id]


@router.get("/", response_model=SegmentListResponse)
async def list_segments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> SegmentListResponse:
    import logging
    logger = logging.getLogger(__name__)
    try:
        filters = [Segment.is_active.is_(True)]
        total = int(await db.scalar(select(func.count(Segment.id)).where(*filters)) or 0)
        result = await db.execute(
            select(Segment)
            .where(*filters)
            .order_by(Segment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return SegmentListResponse(items=list(result.scalars().all()), total=total)
    except Exception as e:
        logger.error("Segment list error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
async def create_segment(
    payload: SegmentCreate,
    db: AsyncSession = Depends(get_db),
) -> Segment:
    segment = Segment(
        name=payload.name,
        description=payload.description,
        filter_rules=payload.filter_rules.model_dump(),
        ai_generated=payload.ai_generated,
        prompt_used=payload.prompt_used,
    )
    db.add(segment)
    await db.commit()
    await db.refresh(segment)

    try:
        await refresh_segment_count(db, segment.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.refresh(segment)
    return segment


@router.patch("/{segment_id}", response_model=SegmentResponse)
async def update_segment(
    segment_id: UUID,
    payload: SegmentUpdate,
    db: AsyncSession = Depends(get_db),
) -> Segment:
    segment = await _get_segment_or_404(db, segment_id)
    updates = payload.model_dump(exclude_none=True)
    filter_rules_changed = "filter_rules" in updates

    if "filter_rules" in updates and updates["filter_rules"] is not None:
        updates["filter_rules"] = payload.filter_rules.model_dump()

    for field, value in updates.items():
        setattr(segment, field, value)

    await db.commit()
    await db.refresh(segment)

    if filter_rules_changed:
        try:
            await refresh_segment_count(db, segment.id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        await db.refresh(segment)

    return segment


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(
    segment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    segment = await _get_segment_or_404(db, segment_id)
    segment.is_active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/preview", response_model=SegmentPreview)
async def preview_unsaved_segment(
    payload: SegmentPreviewRequest,
    db: AsyncSession = Depends(get_db),
) -> SegmentPreview:
    try:
        customer_count, sample_customers = await preview_segment(db, payload.filter_rules.model_dump(), sample_size=5)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    full_sample_customers = await _load_full_customers(db, sample_customers)
    return SegmentPreview(customer_count=customer_count, sample_customers=full_sample_customers)


@router.get("/{segment_id}", response_model=SegmentResponse)
async def get_segment(
    segment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Segment:
    return await _get_segment_or_404(db, segment_id)


@router.post("/{segment_id}/refresh")
async def refresh_segment(
    segment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await _get_segment_or_404(db, segment_id)
    try:
        customer_count = await refresh_segment_count(db, segment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "segment_id": str(segment_id),
        "customer_count": customer_count,
        "refreshed_at": datetime.now(UTC),
    }
