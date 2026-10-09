from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.context_source import SourceStatus, SourceType


class EvidenceStrength(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class EvidenceExcerpt(BaseModel):
    """One citation, fully traceable — what the UI renders in the evidence drawer."""

    source_id: str
    title: str
    date: date
    source_type: SourceType
    status: SourceStatus
    excerpt: str


class FindingEvidence(BaseModel):
    supporting: list[EvidenceExcerpt] = Field(default_factory=list)
    contradictory: list[EvidenceExcerpt] = Field(default_factory=list)
    historical: list[EvidenceExcerpt] = Field(default_factory=list)


class SynthesisFinding(BaseModel):
    id: str
    statement: str
    strength: EvidenceStrength
    evidence: FindingEvidence


class PreviousDecisionSummary(BaseModel):
    decision_id: str
    date: date
    decision: str
    rationale_summary: str
    evidence: FindingEvidence


class ChangedContextSummary(BaseModel):
    change: str
    evidence: FindingEvidence


class AssumptionSummary(BaseModel):
    assumption: str
    evidence_status: str
    evidence: FindingEvidence


class DecisionReviewSynthesis(BaseModel):
    review_id: str
    proposed_decision: str
    overall_evidence_strength: EvidenceStrength

    what_we_know: list[SynthesisFinding] = Field(default_factory=list)
    what_challenges: list[SynthesisFinding] = Field(default_factory=list)
    strategic_context: list[SynthesisFinding] = Field(default_factory=list)
    previous_decisions: list[PreviousDecisionSummary] = Field(default_factory=list)
    what_changed: list[ChangedContextSummary] = Field(default_factory=list)
    assumptions: list[AssumptionSummary] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)
    questions_worth_answering: list[str] = Field(default_factory=list)

    created_at: datetime
