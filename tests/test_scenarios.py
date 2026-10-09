"""Acceptance criteria 2–9: the six scenarios, evaluated by the real Trust Layer."""
import pytest
from trust_layer.schemas import Level
from trust_layer.service import TrustError

EXPECTED = {
    "A": (Level.L3, "WITHIN_POLICY"),
    "B": (Level.L1, "EVIDENCE_WEAK"),
    "C": (Level.L2, "AUTHORITY_PREPARE_ONLY"),
    "D": (Level.L0, "PROHIBITED"),
    "E": (Level.L0, "INTEGRITY_FAILURE"),
    "F": (Level.L1, "SUPERSEDED_EVIDENCE"),
}


@pytest.mark.parametrize("key", list(EXPECTED))
def test_expected_level_and_reason(session, key):
    row = session.evaluate(key)
    level, reason = EXPECTED[key]
    assert row["decision"].level == level
    assert reason in [r.value for r in row["decision"].reasons]
    assert row["decision"].confidence_used is False


@pytest.mark.parametrize("confidence", [0.0, 0.5, 0.96, 1.0])
def test_d_stays_blocked_at_any_confidence(session, confidence):
    row = session.evaluate("D", claimed_confidence=confidence)
    d = row["decision"]
    assert d.level == Level.L0 and d.reasons[0].value == "PROHIBITED"
    # The agent holds an execute grant and cites HIGH evidence; neither lifts the prohibition.
    assert any(c.reason.value == "EXECUTE_GRANTED" for c in d.ceilings)
    p = session.scenarios["D"]["proposal"]
    assert p.context_packet.finding(p.relies_on[0]).strength == "HIGH"
    with pytest.raises(TrustError) as e:
        session.execute(row["evaluation_id"], "agent.sales-assist")
    assert e.value.code == "BLOCKED"
    with pytest.raises(TrustError):
        session.approve(row["evaluation_id"], "human.sam-reyes")


@pytest.mark.parametrize("key", list(EXPECTED))
def test_confidence_never_changes_the_level(session, key):
    levels = {session.evaluate(key, claimed_confidence=c)["decision"].level for c in (0.0, 0.3, 0.7, 1.0)}
    assert len(levels) == 1


def test_e_detects_tampering(session):
    row = session.evaluate("E")
    errs = row["decision"].integrity_errors
    assert row["decision"].integrity_ok is False
    assert any("SOURCE_MISMATCH: FP-002.status" in x for x in errs)
    assert any(x.startswith("CONTENT_MISMATCH") for x in errs)
    with pytest.raises(TrustError) as e:
        session.execute(row["evaluation_id"], "agent.decision-analyst")
    assert e.value.code == "BLOCKED"


def test_c_full_approval_flow(session):
    ev = session.evaluate("C")["evaluation_id"]
    with pytest.raises(TrustError) as e:
        session.execute(ev, "agent.decision-analyst")
    assert e.value.code == "APPROVAL_REQUIRED"
    with pytest.raises(TrustError) as e:
        session.approve(ev, "human.sam-reyes")
    assert e.value.code == "APPROVER_NOT_AUTHORIZED"
    with pytest.raises(TrustError) as e:  # the proposing agent approving itself
        session.approve(ev, "agent.decision-analyst")
    assert e.value.code == "APPROVER_NOT_HUMAN"
    with pytest.raises(TrustError) as e:
        session.approve(ev, "human.nobody")
    assert e.value.code == "UNKNOWN_APPROVER"
    assert session.get(ev)["state"] == "PENDING_APPROVAL"

    assert session.approve(ev, "human.ana-ortiz")["state"] == "APPROVED"
    done = session.execute(ev, "agent.decision-analyst")
    assert done["state"] == "EXECUTED"
    assert done["outcome"]["simulated"] is True
    assert "DISABLED" in done["outcome"]["effect"]["write_back"]


def test_c_human_self_approval_refused(shared):
    """The SELF_APPROVAL rule, exercised in the real service. With the shipped
    policy only agents can propose C, so the human-proposer case needs a policy
    variant built in memory (the policy file is untouched)."""
    from demo.engine import DemoSession

    grants = dict(shared.policy.grants)
    grants[("human.ana-ortiz", "reservoir.record_decision")] = frozenset({"prepare", "approve"})
    grants[("human.sam-reyes", "reservoir.record_decision")] = frozenset({"approve"})
    variant = shared.policy.__class__(**{**shared.policy.__dict__, "grants": grants})
    s = DemoSession(shared.__class__(policy=variant, adapter=shared.adapter))
    p = s.scenarios["C"]["proposal"].model_copy(update={"proposer_id": "human.ana-ortiz"})
    ev = s.service.submit(p)["evaluation_id"]
    with pytest.raises(TrustError) as e:
        s.approve(ev, "human.ana-ortiz")
    assert e.value.code == "SELF_APPROVAL"


def test_a_executes_autonomously(session):
    row = session.evaluate("A")
    assert row["state"] == "EXECUTED"
    assert row["outcome"]["simulated"] is True
    assert row["approval"] is None


@pytest.mark.parametrize("key", ["B", "F"])
def test_recommendations_refuse_execution(session, key):
    ev = session.evaluate(key)["evaluation_id"]
    with pytest.raises(TrustError) as e:
        session.execute(ev, "agent.decision-analyst")
    assert e.value.code == "RECOMMENDATION_CANNOT_EXECUTE"
    assert session.get(ev)["outcome"] is None


def test_every_step_is_audited(session):
    for k in "ABDEF":
        session.evaluate(k)
    ev = session.evaluate("C")["evaluation_id"]
    for attempt in (lambda: session.execute(ev, "agent.decision-analyst"),
                    lambda: session.approve(ev, "human.sam-reyes"),
                    lambda: session.approve(ev, "agent.decision-analyst")):
        with pytest.raises(TrustError):
            attempt()
    session.approve(ev, "human.ana-ortiz")
    session.execute(ev, "agent.decision-analyst")
    b = session.latest["B"]
    with pytest.raises(TrustError):
        session.execute(b, "agent.decision-analyst")

    events = [(x["event_type"], x["evaluation_id"]) for x in session.audit_entries()]
    types = [t for t, _ in events]
    assert types.count("EVALUATED") == 6
    assert types.count("APPROVAL_DENIED") == 2
    assert types.count("APPROVED") == 1
    assert types.count("EXECUTED_SIMULATED") == 2  # A autonomously, C after approval
    assert types.count("EXECUTION_REFUSED") == 2  # C before approval, B
    evaluated = [x for x in session.audit_entries() if x["event_type"] == "EVALUATED"]
    assert all(x["payload"]["evidence"]["packet_id"].startswith("cp_") for x in evaluated)
    assert all(x["payload"]["decision"]["reasons"] for x in evaluated)
    assert session.audit_chain().ok
