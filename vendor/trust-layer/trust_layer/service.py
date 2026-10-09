"""Orchestration: proposal -> integrity -> evaluation -> (approval) -> simulated
execution, with every step audited.

State machine per evaluation:
    BLOCKED (L0) | RECOMMENDATION (L1)            terminal; execution always refused
    PENDING_APPROVAL (L2) -> APPROVED -> EXECUTED
                          -> REJECTED
    READY (L3) -> EXECUTED                        executed immediately on submit

The evaluation row and its audit entry are written in one transaction, so a
decision is never returned without its audit record.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from trust_layer.adapters.vectorpm import ReservoirAdapter
from trust_layer.audit import AuditLog
from trust_layer.evaluator import evaluate
from trust_layer.integrity import IntegrityReport, check_packet
from trust_layer.policy import Policy
from trust_layer.schemas import ActionProposal, AutonomyDecision, ContextPacket, Level
from trust_layer.simulator import simulate

SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluations (
    evaluation_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    state TEXT NOT NULL,
    proposal_json TEXT NOT NULL,
    decision_json TEXT NOT NULL,
    approval_json TEXT,
    outcome_json TEXT
);
"""

INITIAL_STATE = {Level.L0: "BLOCKED", Level.L1: "RECOMMENDATION", Level.L2: "PENDING_APPROVAL", Level.L3: "READY"}


class TrustError(Exception):
    """Refused request. `code` is a stable reason string for the API and tests."""

    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code, self.status = code, status


class TrustService:
    def __init__(self, policy: Policy, adapter: ReservoirAdapter, db_path: Path | str):
        self.policy, self.adapter = policy, adapter
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.executescript(SCHEMA)
        self.audit = AuditLog(self.conn)

    # ---------------------------------------------------------------- context
    def packet_from_review(self, review_id: str) -> ContextPacket:
        return self.adapter.packet_from_review(review_id)

    def check_integrity(self, packet: ContextPacket) -> IntegrityReport:
        try:
            rederived = self.adapter.rederive(packet)
        except Exception as e:  # unknown review/source: unverifiable, fails closed
            rederived = e
        corpus = self.adapter.corpus_index()
        return check_packet(packet, corpus, set(self.adapter.review_ids()),
                            self.adapter.corpus_fingerprint(corpus), rederived)

    # ---------------------------------------------------------------- evaluate
    def submit(self, proposal: ActionProposal) -> dict:
        integrity = self.check_integrity(proposal.context_packet)
        decision = evaluate(proposal, self.policy, integrity)
        state = INITIAL_STATE[decision.level]

        with self.conn:  # one transaction: evaluation + its audit entry
            self.conn.execute(
                "INSERT INTO evaluations (evaluation_id, created_at, state, proposal_json, decision_json)"
                " VALUES (?, ?, ?, ?, ?)",
                (decision.evaluation_id, decision.evaluated_at.isoformat(), state,
                 proposal.model_dump_json(), decision.model_dump_json()),
            )
            self.audit.append("EVALUATED", self._evaluated_payload(proposal, decision),
                              evaluation_id=decision.evaluation_id, actor=proposal.proposer_id, commit=False)

        if decision.level == Level.L3:
            try:
                self.execute(decision.evaluation_id, requested_by=proposal.proposer_id)
            except TrustError:
                pass  # refusal is already audited; the caller sees state READY
        return self.get(decision.evaluation_id)

    def _evaluated_payload(self, p: ActionProposal, d: AutonomyDecision) -> dict:
        relied = []
        for ref in p.relies_on:
            f, a = p.context_packet.finding(ref), p.context_packet.assumption(ref)
            if f:
                relied.append({"id": ref, "kind": "finding", "strength": f.strength,
                               "supporting": list(f.supporting_ids), "contradictory": list(f.contradictory_ids)})
            elif a:
                relied.append({"id": ref, "kind": "assumption", "evidence_status": a.evidence_status,
                               "sources": list(a.source_ids)})
            else:
                relied.append({"id": ref, "kind": "missing"})
        return {
            "action": {"proposer_id": p.proposer_id, "action_type": p.action_type, "target": p.target,
                       "summary": p.summary, "parameters": p.parameters,
                       "claimed_confidence": p.claimed_confidence},
            "evidence": {"packet_id": p.context_packet.packet_id, "origin": p.context_packet.body.origin,
                         "relies_on": relied, "integrity_ok": d.integrity_ok,
                         "integrity_errors": d.integrity_errors},
            "policy": {"version": d.policy_version},
            "decision": {"level": d.level.name, "label": d.level_label,
                         "reasons": [r.value for r in d.reasons],
                         "ceilings": [c.model_dump(mode="json") for c in d.ceilings],
                         "requires_approval": d.requires_approval,
                         "eligible_approvers": d.eligible_approvers,
                         "confidence_used": d.confidence_used},
        }

    # ---------------------------------------------------------------- approval
    def _authorize_approver(self, row: dict, approver_id: str) -> None:
        proposal = row["proposal"]
        if row["state"] != "PENDING_APPROVAL":
            raise TrustError("NOT_PENDING_APPROVAL", f"evaluation is {row['state']}, not awaiting approval")
        principal = self.policy.principal(approver_id)
        if principal is None:
            raise TrustError("UNKNOWN_APPROVER", f"{approver_id} is not a known identity", 403)
        if principal.kind != "human":
            raise TrustError("APPROVER_NOT_HUMAN", "only humans can approve", 403)
        if approver_id == proposal.proposer_id:
            raise TrustError("SELF_APPROVAL", "a proposer cannot approve its own action", 403)
        if "approve" not in self.policy.permissions(approver_id, proposal.action_type):
            raise TrustError("APPROVER_NOT_AUTHORIZED",
                             f"{approver_id} lacks approve permission for {proposal.action_type}", 403)
        if row["decision"].policy_version != self.policy.version_id:
            raise TrustError("POLICY_CHANGED", "policy changed since evaluation; re-evaluate")

    def _decide(self, evaluation_id: str, approver_id: str, note: str, approve: bool) -> dict:
        row = self.get(evaluation_id)
        try:
            self._authorize_approver(row, approver_id)
        except TrustError as e:
            self.audit.append("APPROVAL_DENIED",
                              {"attempted": "approve" if approve else "reject", "approver_id": approver_id,
                               "code": e.code, "message": str(e)},
                              evaluation_id=evaluation_id, actor=approver_id)
            raise
        approval = {"decision": "approved" if approve else "rejected", "approver_id": approver_id,
                    "note": note, "at": datetime.now(timezone.utc).isoformat(),
                    "policy_version": self.policy.version_id}
        with self.conn:
            self.conn.execute("UPDATE evaluations SET state = ?, approval_json = ? WHERE evaluation_id = ?",
                              ("APPROVED" if approve else "REJECTED", json.dumps(approval), evaluation_id))
            self.audit.append("APPROVED" if approve else "REJECTED", {"approval": approval},
                              evaluation_id=evaluation_id, actor=approver_id, commit=False)
        return self.get(evaluation_id)

    def approve(self, evaluation_id: str, approver_id: str, note: str = "") -> dict:
        return self._decide(evaluation_id, approver_id, note, approve=True)

    def reject(self, evaluation_id: str, approver_id: str, note: str = "") -> dict:
        return self._decide(evaluation_id, approver_id, note, approve=False)

    # ---------------------------------------------------------------- execution
    REFUSALS = {
        "BLOCKED": ("BLOCKED", "L0: the action is blocked and can never execute"),
        "RECOMMENDATION": ("RECOMMENDATION_CANNOT_EXECUTE", "L1: recommendations cannot execute; a human takes the action"),
        "PENDING_APPROVAL": ("APPROVAL_REQUIRED", "L2: an authorized human must approve before execution"),
        "REJECTED": ("REJECTED", "the approver rejected this action"),
        "EXECUTED": ("ALREADY_EXECUTED", "this action was already executed"),
    }

    def execute(self, evaluation_id: str, requested_by: str) -> dict:
        row = self.get(evaluation_id)
        try:
            if row["state"] in self.REFUSALS:
                raise TrustError(*self.REFUSALS[row["state"]])
            if row["state"] not in ("READY", "APPROVED"):
                raise TrustError("INVALID_STATE", f"cannot execute from {row['state']}")
            if row["decision"].policy_version != self.policy.version_id:
                raise TrustError("POLICY_CHANGED", "policy changed since evaluation; re-evaluate")
            # Re-check context at time of use, not just time of evaluation.
            integrity = self.check_integrity(row["proposal"].context_packet)
            if not integrity.ok:
                raise TrustError("INTEGRITY_FAILURE", "; ".join(integrity.errors))
            outcome = simulate(row["proposal"])
        except TrustError as e:
            self.audit.append("EXECUTION_REFUSED", {"requested_by": requested_by, "state": row["state"],
                                                    "code": e.code, "message": str(e)},
                              evaluation_id=evaluation_id, actor=requested_by)
            raise
        except Exception as e:  # simulator failure: fail closed, still audited
            self.audit.append("EXECUTION_REFUSED", {"requested_by": requested_by, "state": row["state"],
                                                    "code": "EXECUTION_ERROR", "message": str(e)},
                              evaluation_id=evaluation_id, actor=requested_by)
            raise TrustError("EXECUTION_ERROR", str(e), 500) from e

        with self.conn:
            self.conn.execute("UPDATE evaluations SET state = 'EXECUTED', outcome_json = ? WHERE evaluation_id = ?",
                              (json.dumps(outcome), evaluation_id))
            self.audit.append("EXECUTED_SIMULATED", {"requested_by": requested_by, "outcome": outcome,
                                                     "approval": row["approval"]},
                              evaluation_id=evaluation_id, actor=requested_by, commit=False)
        return self.get(evaluation_id)

    # ---------------------------------------------------------------- reads
    def get(self, evaluation_id: str) -> dict:
        r = self.conn.execute(
            "SELECT evaluation_id, created_at, state, proposal_json, decision_json, approval_json, outcome_json"
            " FROM evaluations WHERE evaluation_id = ?", (evaluation_id,)).fetchone()
        if r is None:
            raise TrustError("NOT_FOUND", f"evaluation {evaluation_id} not found", 404)
        return {
            "evaluation_id": r[0], "created_at": r[1], "state": r[2],
            "proposal": ActionProposal.model_validate_json(r[3]),
            "decision": AutonomyDecision.model_validate_json(r[4]),
            "approval": json.loads(r[5]) if r[5] else None,
            "outcome": json.loads(r[6]) if r[6] else None,
        }

    def list(self) -> list[dict]:
        ids = [r[0] for r in self.conn.execute("SELECT evaluation_id FROM evaluations ORDER BY created_at DESC")]
        return [self.get(i) for i in ids]
