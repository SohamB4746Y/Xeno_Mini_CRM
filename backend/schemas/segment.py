from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from schemas.customer import CustomerResponse


class FilterCondition(BaseModel):
    model_config = ConfigDict(extra="allow")

    field: str
    operator: str
    value: Any = None


class FilterRules(BaseModel):
    operator: str = "AND"
    conditions: list[FilterCondition] = Field(default_factory=list)


class SegmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    filter_rules: FilterRules
    ai_generated: bool = False
    prompt_used: Optional[str] = None


class SegmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    filter_rules: Optional[FilterRules] = None


class SegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str] = None
    filter_rules: dict[str, Any] = Field(default_factory=dict)
    ai_generated: bool
    prompt_used: Optional[str] = None
    customer_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SegmentPreview(BaseModel):
    customer_count: int
    sample_customers: list[CustomerResponse]


class SegmentListResponse(BaseModel):
    items: list[SegmentResponse]
    total: int
