"""Deterministic autonomy evaluator.

    level = min(every ceiling that applies), starting from L3.

Each ceiling carries a reason code. The binding reasons are the ceilings equal
to the final level; the rest are kept so the decision explains every limit, not
just the tightest one.

`claimed_confidence` is deliberately not read by any rule below. Errors of any
kind return L0 (fail closed).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from trust_layer.integrity import IntegrityReport
from trust_layer.policy import Policy
from trust_layer.schemas import (
    STRENGTH_ORDER, ActionProposal, AutonomyDecision, Ceiling, Level, Reason,
)


def _authority_ceiling(perms: frozenset[str]) -> Ceiling:
    if "execute" in perms:
        return Ceiling(dimension="authority", level=Level.L3, reason=Reason.EXECUTE_GRANTED)
    if "prepare" in perms:
        return Ceiling(dimension="authority", level=Level.L2, reason=Reason.AUTHORITY_PREPARE_ONLY)
    if "recommend" in perms:
        return Ceiling(dimension="authority", level=Level.L1, reason=Reason.AUTHORITY_RECOMMEND_ONLY)
    held = ", ".join(sorted(perms)) or "none"
    return Ceiling(dimension="authority", level=Level.L0, reason=Reason.NO_AUTHORITY,
                   detail=f"permissions held for this action: {held}")


def _evidence_ceilings(proposal: ActionProposal, policy: Policy, requires_evidence: bool) -> list[Ceiling]:
    packet = proposal.context_packet
    out: list[Ceiling] = []

    if not proposal.relies_on:
        if requires_evidence:
            out.append(Ceiling(dimension="evidence", level=Level.L1, reason=Reason.EVIDENCE_NOT_CITED))
        return out

    findings, assumptions = [], []
    for ref in proposal.relies_on:
        f, a = packet.finding(ref), packet.assumption(ref)
        if f is None and a is None:
            # A reference to evidence that isn't in the packet is invalid context.
            out.append(Ceiling(dimension="integrity", level=Level.L0, reason=Reason.INTEGRITY_FAILURE,
                               detail=f"relies_on references {ref!r}, which is not in the context packet"))
        elif f is not None:
            findings.append(f)
        else:
            assumptions.append(a)

    min_l2 = STRENGTH_ORDER[policy.settings["min_evidence_for_l2"]]
    min_l3 = STRENGTH_ORDER[policy.settings["min_evidence_for_l3"]]
    for f in findings:
        rank = STRENGTH_ORDER[f.strength]
        if rank == 0:
            out.append(Ceiling(dimension="evidence", level=Level.L1, reason=Reason.EVIDENCE_INSUFFICIENT,
                               detail=f"{f.finding_id} is INSUFFICIENT"))
        elif rank < min_l2:
            out.append(Ceiling(dimension="evidence", level=Level.L1, reason=Reason.EVIDENCE_WEAK,
                               detail=f"{f.finding_id} is {f.strength}; L2 needs {policy.settings['min_evidence_for_l2']}"))
        elif rank < min_l3:
            out.append(Ceiling(dimension="evidence", level=Level.L2, reason=Reason.EVIDENCE_WEAK,
                               detail=f"{f.finding_id} is {f.strength}; L3 needs {policy.settings['min_evidence_for_l3']}"))
        if f.contradictory_ids:
            out.append(Ceiling(dimension="evidence", level=Level.L2, reason=Reason.UNRESOLVED_CONTRADICTION,
                               detail=f"{f.finding_id} is contradicted by {', '.join(f.contradictory_ids)}"))

    for a in assumptions:
        if a.evidence_status != "SUPPORTED":
            out.append(Ceiling(dimension="evidence", level=Level.L1, reason=Reason.ASSUMPTION_UNVERIFIED,
                               detail=f"{a.assumption_id} is {a.evidence_status}"))

    # Freshness: support resting on superseded or stale sources.
    relied_sources = {sid for f in findings for sid in f.supporting_ids}
    relied_sources |= {sid for a in assumptions for sid in a.source_ids}
    for sid in sorted(relied_sources):
        s = packet.source(sid)
        if s is None:
            continue  # integrity checks already reject citations outside the packet
        if s.status == "superseded":
            out.append(Ceiling(dimension="context", level=Level.L1, reason=Reason.SUPERSEDED_EVIDENCE,
                               detail=f"{sid} is superseded by {s.superseded_by}"))
        elif s.status == "stale":
            out.append(Ceiling(dimension="context", level=Level.L1, reason=Reason.STALE_EVIDENCE,
                               detail=f"{sid} is stale"))
    return out


def _evaluate(proposal: ActionProposal, policy: Policy, integrity: IntegrityReport,
              now: datetime) -> tuple[list[Ceiling], list[str]]:
    ceilings: list[Ceiling] = []
    principal = policy.principal(proposal.proposer_id)
    action = policy.action(proposal.action_type)

    if principal is None:
        ceilings.append(Ceiling(dimension="identity", level=Level.L0, reason=Reason.UNKNOWN_PRINCIPAL,
                                detail=proposal.proposer_id))
    if action is None:
        ceilings.append(Ceiling(dimension="policy", level=Level.L0, reason=Reason.UNKNOWN_ACTION_TYPE,
                                detail=proposal.action_type))
    if not integrity.ok:
        ceilings.append(Ceiling(dimension="integrity", level=Level.L0, reason=Reason.INTEGRITY_FAILURE,
                                detail="; ".join(integrity.errors)))
    if principal is None or action is None:
        return ceilings, []

    # Authority. A prohibition is checked first and nothing below can lift it.
    prohibition = policy.prohibition_for(principal.principal_id, action.action_type)
    if prohibition:
        ceilings.append(Ceiling(dimension="authority", level=Level.L0, reason=Reason.PROHIBITED,
                                detail=prohibition.reason))
    ceilings.append(_authority_ceiling(policy.permissions(principal.principal_id, action.action_type)))

    # Risk, from the registry. Only internal, reversible, low-risk actions may reach L3.
    if action.scope == "external":
        ceilings.append(Ceiling(dimension="risk", level=Level.L2, reason=Reason.RISK_EXTERNAL))
    if action.customer_facing:
        ceilings.append(Ceiling(dimension="risk", level=Level.L2, reason=Reason.RISK_CUSTOMER_FACING))
    if not action.reversible:
        ceilings.append(Ceiling(dimension="risk", level=Level.L2, reason=Reason.RISK_IRREVERSIBLE))
    if action.risk != "low":
        ceilings.append(Ceiling(dimension="risk", level=Level.L2, reason=Reason.RISK_CONSEQUENTIAL))

    # Context and evidence, only meaningful when the packet itself is valid.
    if integrity.ok:
        age_h = (now - proposal.context_packet.body.generated_at).total_seconds() / 3600
        if age_h > policy.settings["max_packet_age_hours"]:
            ceilings.append(Ceiling(dimension="context", level=Level.L1, reason=Reason.CONTEXT_EXPIRED,
                                    detail=f"packet is {age_h:.0f}h old"))
        ceilings += _evidence_ceilings(proposal, policy, action.requires_evidence)

    # Approval feasibility: L2 is only meaningful if someone else can approve.
    approvers = policy.approvers_for(action.action_type, exclude=principal.principal_id)
    if min((c.level for c in ceilings), default=Level.L3) == Level.L2 and not approvers:
        ceilings.append(Ceiling(dimension="approval", level=Level.L1, reason=Reason.NO_ELIGIBLE_APPROVER))
    return ceilings, approvers


def evaluate(proposal: ActionProposal, policy: Policy, integrity: IntegrityReport,
             now: datetime | None = None) -> AutonomyDecision:
    now = now or datetime.now(timezone.utc)
    try:
        ceilings, approvers = _evaluate(proposal, policy, integrity, now)
    except Exception as e:  # fail closed
        ceilings, approvers = [Ceiling(dimension="policy", level=Level.L0, reason=Reason.EVALUATION_ERROR,
                                       detail=f"{type(e).__name__}: {e}")], []

    level = min((c.level for c in ceilings), default=Level.L3)
    # At L3 nothing limits the action; below L3 the binding reasons are the ceilings at that level.
    binding = [] if level == Level.L3 else list(dict.fromkeys(c.reason for c in ceilings if c.level == level))
    return AutonomyDecision(
        evaluation_id="ev_" + uuid.uuid4().hex[:12],
        level=level, level_label=level.label,
        reasons=binding or [Reason.WITHIN_POLICY],
        ceilings=ceilings,
        requires_approval=level == Level.L2,
        eligible_approvers=approvers if level == Level.L2 else [],
        policy_version=policy.version_id,
        packet_id=proposal.context_packet.packet_id,
        integrity_ok=integrity.ok, integrity_errors=list(integrity.errors),
        claimed_confidence=proposal.claimed_confidence,
        evaluated_at=now,
    )
