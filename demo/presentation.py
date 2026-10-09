"""Plain-English presentation of Trust Layer outputs. Display only: nothing here
changes a level, a reason or an outcome. Labels for unknown codes fall back to
the raw code rather than inventing a description."""
from __future__ import annotations

LEVELS = {
    "L0": {"name": "Blocked", "css": "l0", "can_execute": "Never",
           "summary": "Prohibited, unauthorized, unknown, or invalid context."},
    "L1": {"name": "Recommend", "css": "l1", "can_execute": "Never; a human takes the action",
           "summary": "The agent may recommend. A human decides and acts."},
    "L2": {"name": "Approval required", "css": "l2", "can_execute": "Only after authorized human approval",
           "summary": "The agent prepares it. An authorized human must approve first."},
    "L3": {"name": "Autonomous", "css": "l3", "can_execute": "Yes, within grants and policy",
           "summary": "Granted, internal, reversible, low-risk and adequately evidenced."},
}

STATUS_CSS = {"current": "ok", "historical": "info", "stale": "warn", "superseded": "bad"}
STATUS_HELP = {
    "current": "Current: reflects the present state of the business.",
    "historical": "Historical: an accurate record of the past. Useful as precedent, not as a current fact.",
    "stale": "Stale: old enough that it may no longer be true. Caps autonomy when relied on.",
    "superseded": "Superseded: replaced by a newer source. Caps autonomy when relied on.",
}
STRENGTH_CSS = {"HIGH": "ok", "MEDIUM": "info", "LOW": "warn", "INSUFFICIENT": "bad"}
ASSUMPTION_CSS = {"SUPPORTED": "ok", "WEAK": "warn", "CONTRADICTED": "bad", "INSUFFICIENT_CONTEXT": "bad"}

SOURCE_TYPE_LABEL = {
    "strategy": "Strategy", "okr": "OKR", "customer_interview": "Customer interview",
    "analytics": "Analytics", "support_theme": "Support themes", "stakeholder_signal": "Stakeholder opinion",
    "competitive_research": "Competitive research", "engineering_note": "Engineering note",
    "decision_record": "Decision record", "roadmap": "Roadmap",
}

ACTION_LABEL = {
    "feedback.classify": "Classify customer feedback",
    "review.add_internal_note": "Add an internal note to a decision review",
    "roadmap.change_priority": "Change roadmap priority",
    "reservoir.record_decision": "Record a decision in institutional memory",
    "customer.commit_release_date": "Promise a release date to a customer",
}

DIMENSIONS = [
    ("identity", "Identity", "Is the proposing agent a known identity?"),
    ("policy", "Action registry", "Is this action type registered? Unknown actions fail closed."),
    ("integrity", "Context integrity", "Does the context packet match what the Reservoir actually holds?"),
    ("authority", "Authority", "Prohibitions first, then the agent's grants: recommend, prepare or execute."),
    ("risk", "Risk", "Registry risk profile: external, customer-facing, irreversible, consequential."),
    ("evidence", "Evidence", "Strength, contradictions and assumptions behind the evidence the agent relies on."),
    ("context", "Freshness", "Does the evidence rest on superseded or stale sources, or an expired packet?"),
    ("approval", "Approval path", "If approval is needed, is there another human who can give it?"),
]

EVENT_LABEL = {
    "EVALUATED": ("Proposal evaluated", "info"),
    "APPROVED": ("Approved", "ok"),
    "REJECTED": ("Rejected by approver", "warn"),
    "APPROVAL_DENIED": ("Approval attempt refused", "bad"),
    "EXECUTED_SIMULATED": ("Simulated execution", "ok"),
    "EXECUTION_REFUSED": ("Execution refused", "bad"),
}

REFUSAL_TEXT = {
    "BLOCKED": "Blocked actions can never execute.",
    "RECOMMENDATION_CANNOT_EXECUTE": "This is a recommendation. The agent cannot execute it; a human takes the action.",
    "APPROVAL_REQUIRED": "An authorized human must approve before this can execute.",
    "REJECTED": "The approver rejected this action.",
    "ALREADY_EXECUTED": "This action was already executed (simulated).",
    "SELF_APPROVAL": "A proposer cannot approve its own action.",
    "APPROVER_NOT_HUMAN": "Only humans can approve. An agent cannot approve, including its own proposal.",
    "APPROVER_NOT_AUTHORIZED": "This person does not hold approve permission for this action type.",
    "UNKNOWN_APPROVER": "This identity is not in the policy.",
    "NOT_PENDING_APPROVAL": "This evaluation is not awaiting approval.",
    "INTEGRITY_FAILURE": "Context failed integrity re-checks at time of use.",
    "POLICY_CHANGED": "Policy changed since evaluation; re-evaluate.",
    "EXECUTION_ERROR": "The simulator failed, so nothing executed (fail closed).",
}

STATE_LABEL = {
    "BLOCKED": "Blocked", "RECOMMENDATION": "Recommendation only", "PENDING_APPROVAL": "Awaiting approval",
    "APPROVED": "Approved, ready to execute", "REJECTED": "Rejected", "READY": "Ready",
    "EXECUTED": "Executed (simulated)",
}

# Scenario framing for the UI. The proposals themselves come unchanged from
# trust_layer.scenarios; only the headline copy lives here.
SCENARIO_COPY = {
    "A": {"short": "Internal note", "headline": "Autonomous internal action",
          "try": "Evaluate it. It executes immediately (simulated), because nothing in policy limits it."},
    "B": {"short": "Roadmap change", "headline": "Evidence-limited roadmap change",
          "try": "Evaluate, then press Execute. The Trust Layer refuses: the agent can only recommend."},
    "C": {"short": "Decision update", "headline": "Consequential internal decision",
          "try": "Evaluate. Try Execute first (refused), then approve as Sam Reyes (refused), as the agent "
                 "itself (refused), then as Ana Ortiz, then Execute."},
    "D": {"short": "Customer promise", "headline": "Unauthorized customer commitment",
          "try": "Push the confidence slider to 100% and evaluate. The agent holds an execute grant and cites "
                 "HIGH evidence. It is still blocked."},
    "E": {"short": "Tampered context", "headline": "Tampered context",
          "try": "Someone relabelled a superseded strategy as current and re-sealed the packet hash. "
                 "Evaluate and see the Trust Layer re-derive the evidence from the Reservoir."},
    "F": {"short": "Superseded strategy", "headline": "Superseded strategy",
          "try": "The same proposal as E with honest context. Superseded evidence caps autonomy at Recommend."},
}


def level_key(level) -> str:
    return getattr(level, "name", str(level))


def principal_label(policy, principal_id: str | None) -> str:
    if not principal_id:
        return "unknown"
    p = policy.principal(principal_id)
    if p is None:
        return principal_id
    return p.display_name + (" · simulated identity" if p.kind == "human" else "")


def reason_text(reason) -> str:
    from trust_layer.schemas import REASON_TEXT, Reason
    try:
        return REASON_TEXT[Reason(getattr(reason, "value", reason))]
    except (ValueError, KeyError):
        return str(reason)


def dimension_rows(decision) -> list[dict]:
    """One row per policy dimension: the tightest ceiling it imposed, if any."""
    rows = []
    for dim, label, question in DIMENSIONS:
        cs = [c for c in decision.ceilings if c.dimension == dim]
        if dim == "integrity" and not cs and decision.integrity_ok:
            rows.append({"label": label, "question": question, "level": None, "items": [],
                         "ok_text": "Passed. The packet was re-derived from the Reservoir and matched."})
            continue
        if not cs:
            rows.append({"label": label, "question": question, "level": None, "items": [],
                         "ok_text": "No limit applied."})
            continue
        worst = min(c.level for c in cs)
        rows.append({"label": label, "question": question, "level": level_key(worst),
                     "items": [(c.reason.value, reason_text(c.reason), c.detail, level_key(c.level)) for c in cs]})
    return rows


def next_action(row: dict, policy) -> str:
    state, d = row["state"], row["decision"]
    if state == "BLOCKED":
        return "None. This action can never execute. If it should happen, a human does it through the proper process."
    if state == "RECOMMENDATION":
        return "Recommend only. A human reviews the recommendation and decides. Agent execution is refused."
    if state == "PENDING_APPROVAL":
        names = ", ".join(principal_label(policy, a) for a in d.eligible_approvers) or "nobody"
        return f"Wait for approval from an authorized human: {names}. Execution before approval is refused."
    if state == "APPROVED":
        return f"Approved by {principal_label(policy, row['approval']['approver_id'])}. Simulated execution is permitted."
    if state == "REJECTED":
        return "Rejected by the approver. The action cannot execute."
    if state == "READY":
        return "Execute autonomously (simulated)."
    if state == "EXECUTED":
        return "Done. The simulated execution is recorded in the audit log."
    return state


def describe_event(entry: dict, policy) -> str:
    p, t = entry["payload"], entry["event_type"]
    if t == "EVALUATED":
        a, d = p["action"], p["decision"]
        return (f"{principal_label(policy, a['proposer_id'])} proposed “{ACTION_LABEL.get(a['action_type'], a['action_type'])}” "
                f"on {a['target']}. Result: {d['level']} {d['label']} ({', '.join(d['reasons'])}). "
                f"Reported confidence {a['claimed_confidence']:.0%}, not used by policy.")
    if t in ("APPROVED", "REJECTED"):
        ap = p["approval"]
        return f"{principal_label(policy, ap['approver_id'])} {ap['decision']} the action."
    if t == "APPROVAL_DENIED":
        return (f"{principal_label(policy, p['approver_id'])} tried to {p['attempted']}. Refused: {p['code']}. "
                f"{REFUSAL_TEXT.get(p['code'], p['message'])}")
    if t == "EXECUTED_SIMULATED":
        return f"Simulated execution requested by {principal_label(policy, p['requested_by'])}. {p['outcome']['note']}"
    if t == "EXECUTION_REFUSED":
        return (f"Execution requested by {principal_label(policy, p['requested_by'])} was refused: {p['code']}. "
                f"{REFUSAL_TEXT.get(p['code'], p['message'])}")
    return t
