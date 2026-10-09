"""Core data contracts. No dependency on VectorPM code: the adapter translates
Reservoir structures into these, so the evaluator stays reusable."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from enum import Enum, IntEnum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "0.1"


class Level(IntEnum):
    L0 = 0  # Blocked
    L1 = 1  # Recommend: human takes the action
    L2 = 2  # Approval required before execution
    L3 = 3  # Autonomous within grants and policy

    @property
    def label(self) -> str:
        return {0: "Blocked", 1: "Recommend", 2: "Approval required", 3: "Autonomous"}[self.value]


# Mirrors the experiment's EvidenceStrength values; ordered so they can be compared.
STRENGTH_ORDER = {"INSUFFICIENT": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


class Reason(str, Enum):
    WITHIN_POLICY = "WITHIN_POLICY"
    EXECUTE_GRANTED = "EXECUTE_GRANTED"  # informational: authority alone would allow L3
    UNKNOWN_ACTION_TYPE = "UNKNOWN_ACTION_TYPE"
    UNKNOWN_PRINCIPAL = "UNKNOWN_PRINCIPAL"
    PROHIBITED = "PROHIBITED"
    NO_AUTHORITY = "NO_AUTHORITY"
    AUTHORITY_RECOMMEND_ONLY = "AUTHORITY_RECOMMEND_ONLY"
    AUTHORITY_PREPARE_ONLY = "AUTHORITY_PREPARE_ONLY"
    RISK_EXTERNAL = "RISK_EXTERNAL"
    RISK_CUSTOMER_FACING = "RISK_CUSTOMER_FACING"
    RISK_IRREVERSIBLE = "RISK_IRREVERSIBLE"
    RISK_CONSEQUENTIAL = "RISK_CONSEQUENTIAL"
    NO_ELIGIBLE_APPROVER = "NO_ELIGIBLE_APPROVER"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"
    CONTEXT_EXPIRED = "CONTEXT_EXPIRED"
    EVIDENCE_NOT_CITED = "EVIDENCE_NOT_CITED"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    EVIDENCE_WEAK = "EVIDENCE_WEAK"
    ASSUMPTION_UNVERIFIED = "ASSUMPTION_UNVERIFIED"
    UNRESOLVED_CONTRADICTION = "UNRESOLVED_CONTRADICTION"
    SUPERSEDED_EVIDENCE = "SUPERSEDED_EVIDENCE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    EVALUATION_ERROR = "EVALUATION_ERROR"


REASON_TEXT = {
    Reason.WITHIN_POLICY: "Granted, low-risk, reversible, adequately evidenced. Nothing limits autonomy.",
    Reason.EXECUTE_GRANTED: "Principal holds execute permission; authority alone would allow L3.",
    Reason.UNKNOWN_ACTION_TYPE: "Action type is not in the registry. Unknown actions fail closed.",
    Reason.UNKNOWN_PRINCIPAL: "Proposing principal is not a known identity.",
    Reason.PROHIBITED: "An explicit prohibition covers this action for this principal. Nothing overrides it.",
    Reason.NO_AUTHORITY: "Principal holds no recommend, prepare or execute grant for this action.",
    Reason.AUTHORITY_RECOMMEND_ONLY: "Principal may only recommend this action.",
    Reason.AUTHORITY_PREPARE_ONLY: "Principal may prepare this action but not execute it.",
    Reason.RISK_EXTERNAL: "Action has effects outside the organisation.",
    Reason.RISK_CUSTOMER_FACING: "Action is visible to customers.",
    Reason.RISK_IRREVERSIBLE: "Action cannot be undone.",
    Reason.RISK_CONSEQUENTIAL: "Action is classed as consequential.",
    Reason.NO_ELIGIBLE_APPROVER: "No other human holds approve permission, so approval cannot be obtained.",
    Reason.INTEGRITY_FAILURE: "Context packet failed integrity checks. Invalid context fails closed.",
    Reason.CONTEXT_EXPIRED: "Context packet is older than the policy allows.",
    Reason.EVIDENCE_NOT_CITED: "Proposal cites no evidence from the context packet.",
    Reason.EVIDENCE_INSUFFICIENT: "Cited evidence is rated INSUFFICIENT.",
    Reason.EVIDENCE_WEAK: "Cited evidence is below the strength policy requires for more autonomy.",
    Reason.ASSUMPTION_UNVERIFIED: "Proposal relies on an assumption the evidence does not support.",
    Reason.UNRESOLVED_CONTRADICTION: "Cited evidence has contradicting sources.",
    Reason.SUPERSEDED_EVIDENCE: "Cited evidence rests on a superseded source.",
    Reason.STALE_EVIDENCE: "Cited evidence rests on a stale source.",
    Reason.EVALUATION_ERROR: "Evaluation raised an error. Errors fail closed.",
}


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------- context packet

class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceRef(_Frozen):
    """A ContextSource from the Reservoir, minus full content. `content_sha256`
    lets integrity checks detect a source whose text or labels were altered."""
    source_id: str
    source_type: str
    title: str
    created_at: date
    status: str  # current | historical | stale | superseded
    superseded_by: Optional[str] = None
    source_reference: str
    decision_owner: Optional[str] = None
    content_sha256: str


class PacketFinding(_Frozen):
    """A SynthesisFinding: statement + deterministic strength + cited sources."""
    finding_id: str
    section: str  # what_we_know | what_challenges | strategic_context
    statement: str
    strength: str  # HIGH | MEDIUM | LOW | INSUFFICIENT
    supporting_ids: tuple[str, ...] = ()
    contradictory_ids: tuple[str, ...] = ()
    historical_ids: tuple[str, ...] = ()
    challenger_verdict: Optional[str] = None  # set for constructed packets so strength can be re-derived


class PacketAssumption(_Frozen):
    assumption_id: str
    assumption: str
    evidence_status: str  # SUPPORTED | WEAK | CONTRADICTED | INSUFFICIENT_CONTEXT
    source_ids: tuple[str, ...] = ()


class PacketDecision(_Frozen):
    """A prior decision, as context only. approval_state is fixed: the Reservoir
    records no approvals, so nothing here may be read as authority."""
    decision_id: str
    summary: str
    source_ids: tuple[str, ...] = ()
    approval_state: Literal["unverified"] = "unverified"


class Freshness(_Frozen):
    as_of: date
    stale_ids: tuple[str, ...] = ()
    superseded_ids: tuple[str, ...] = ()
    oldest_source_age_days: int
    newest_source_age_days: int


class ContextPacketBody(_Frozen):
    contract_version: str = CONTRACT_VERSION
    generated_at: datetime
    origin: dict  # e.g. {"kind": "review", "review_id": "REV-..."}
    corpus_fingerprint: str
    query: str
    sources: tuple[SourceRef, ...]
    findings: tuple[PacketFinding, ...] = ()
    assumptions: tuple[PacketAssumption, ...] = ()
    decisions: tuple[PacketDecision, ...] = ()
    missing_information: tuple[str, ...] = ()
    freshness: Freshness

    def compute_id(self) -> str:
        return "cp_" + sha256_hex(canonical_json(self.model_dump(mode="json")))


class ContextPacket(_Frozen):
    packet_id: str
    body: ContextPacketBody

    @classmethod
    def seal(cls, body: ContextPacketBody) -> "ContextPacket":
        return cls(packet_id=body.compute_id(), body=body)

    def source(self, source_id: str) -> Optional[SourceRef]:
        return next((s for s in self.body.sources if s.source_id == source_id), None)

    def finding(self, finding_id: str) -> Optional[PacketFinding]:
        return next((f for f in self.body.findings if f.finding_id == finding_id), None)

    def assumption(self, assumption_id: str) -> Optional[PacketAssumption]:
        return next((a for a in self.body.assumptions if a.assumption_id == assumption_id), None)


# ---------------------------------------------------------------- proposal + decision

class ActionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposer_id: str
    action_type: str
    target: str = Field(description="What the action acts on, e.g. a ticket or account (fictional).")
    summary: str
    parameters: dict = Field(default_factory=dict)
    relies_on: list[str] = Field(default_factory=list, description="finding_ids / assumption_ids in the packet")
    claimed_confidence: float = Field(ge=0.0, le=1.0, description="Agent self-report. Audited, never used by policy.")
    context_packet: ContextPacket


class Ceiling(BaseModel):
    dimension: Literal["identity", "authority", "risk", "approval", "integrity", "context", "evidence", "policy"]
    level: Level
    reason: Reason
    detail: str = ""


class AutonomyDecision(BaseModel):
    evaluation_id: str
    level: Level
    level_label: str
    reasons: list[Reason]  # the binding reasons: ceilings equal to the final level
    ceilings: list[Ceiling]  # every limit that applied, binding or not
    requires_approval: bool
    eligible_approvers: list[str] = Field(default_factory=list)
    policy_version: str
    packet_id: str
    integrity_ok: bool
    integrity_errors: list[str] = Field(default_factory=list)
    claimed_confidence: float
    confidence_used: Literal[False] = False
    evaluated_at: datetime
