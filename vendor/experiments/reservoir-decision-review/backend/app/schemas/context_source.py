from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    STRATEGY = "strategy"
    OKR = "okr"
    CUSTOMER_INTERVIEW = "customer_interview"
    ANALYTICS = "analytics"
    SUPPORT_THEME = "support_theme"
    STAKEHOLDER_SIGNAL = "stakeholder_signal"  # sales/exec opinion — never treated as customer evidence
    COMPETITIVE_RESEARCH = "competitive_research"
    ENGINEERING_NOTE = "engineering_note"
    DECISION_RECORD = "decision_record"
    ROADMAP = "roadmap"


class SourceStatus(str, Enum):
    CURRENT = "current"
    HISTORICAL = "historical"
    STALE = "stale"
    SUPERSEDED = "superseded"


class ContextSource(BaseModel):
    source_id: str
    source_type: SourceType
    title: str
    created_at: date
    product_area: str
    status: SourceStatus
    content: str
    source_reference: str
    superseded_by: Optional[str] = None
    related_sources: list[str] = Field(default_factory=list)

    # Additional metadata (spec section 7) — kept minimal, only fields actually used downstream.
    segment: Optional[str] = None
    author_role: Optional[str] = None
    strategic_area: Optional[str] = None
    decision_owner: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    tags: list[str] = Field(default_factory=list)
