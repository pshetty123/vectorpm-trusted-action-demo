"""Simulated executor. Produces a description of what *would* happen and nothing
else: no network, no Reservoir write-back, no customer communication."""
from __future__ import annotations

from trust_layer.schemas import ActionProposal

NO_SIDE_EFFECTS = "Simulation only. No external system, customer or Reservoir record was touched."


def _feedback_classify(p: ActionProposal) -> dict:
    return {"would_tag": p.target, "theme": p.parameters.get("theme", "unspecified")}


def _add_internal_note(p: ActionProposal) -> dict:
    return {"would_attach_note_to": p.target, "note": p.parameters.get("note", p.summary)}


def _change_priority(p: ActionProposal) -> dict:
    return {"would_move": p.target, "to_position": p.parameters.get("to_position", "unspecified")}


def _record_decision(p: ActionProposal) -> dict:
    return {
        "would_record_decision": p.summary,
        "decision_status": p.parameters.get("decision_status", "unspecified"),
        "write_back": "DISABLED in this MVP: no DecisionRecord was written to the Reservoir.",
    }


def _commit_release_date(p: ActionProposal) -> dict:
    return {"would_promise": p.target, "date": p.parameters.get("release_date"),
            "customer_communication": "DISABLED: nothing was sent."}


SIMULATORS = {
    "feedback.classify": _feedback_classify,
    "review.add_internal_note": _add_internal_note,
    "roadmap.change_priority": _change_priority,
    "reservoir.record_decision": _record_decision,
    "customer.commit_release_date": _commit_release_date,
}


def simulate(proposal: ActionProposal) -> dict:
    fn = SIMULATORS.get(proposal.action_type)
    if fn is None:
        raise KeyError(f"no simulator for {proposal.action_type}")  # unknown actions never execute
    return {"action_type": proposal.action_type, "simulated": True, "effect": fn(proposal), "note": NO_SIDE_EFFECTS}
