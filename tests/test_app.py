"""Headless Streamlit tests: the real app script, driven through its widgets."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")
PAGES = ["Introduction", "1 · Explore Context", "2 · Test Agent Autonomy", "3 · Audit & Accountability"]


def _app(page: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["page"] = page
    return at.run()


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_errors(page):
    at = _app(page)
    assert not at.exception
    assert not at.error


def _text(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown) + "\n".join(
        w.value for kind in ("warning", "success", "error") for w in getattr(at, kind))


def test_scenario_c_through_the_ui():
    at = _app(PAGES[2])
    at.button(key="pick_C").click().run()
    at.button(key="eval_C").click().run()
    assert "Approval required" in _text(at)

    at.button(key="exec_C").click().run()
    assert "APPROVAL_REQUIRED" in _text(at)

    at.selectbox(key="approver_C").select("human.sam-reyes").run()
    at.button(key="approve_C").click().run()
    assert "APPROVER_NOT_AUTHORIZED" in _text(at)

    at.selectbox(key="approver_C").select("agent.decision-analyst").run()
    at.button(key="approve_C").click().run()
    assert "APPROVER_NOT_HUMAN" in _text(at)

    at.selectbox(key="approver_C").select("human.ana-ortiz").run()
    at.button(key="approve_C").click().run()
    at.button(key="exec_C").click().run()
    assert "Simulated execution completed" in _text(at)
    assert at.session_state["demo"].current("C")["state"] == "EXECUTED"
    assert not at.exception


def test_scenario_d_at_100_percent_through_the_ui():
    at = _app(PAGES[2])
    at.button(key="pick_D").click().run()
    at.slider(key="conf_D").set_value(100).run()
    at.button(key="eval_D").click().run()
    row = at.session_state["demo"].current("D")
    assert row["decision"].level.name == "L0" and row["decision"].claimed_confidence == 1.0
    at.button(key="exec_D").click().run()
    assert "Refused · BLOCKED" in _text(at)


def test_two_browser_sessions_are_isolated():
    first, second = _app(PAGES[2]), _app(PAGES[2])
    first.button(key="pick_C").click().run()
    first.button(key="eval_C").click().run()
    first.selectbox(key="approver_C").select("human.ana-ortiz").run()
    first.button(key="approve_C").click().run()
    first.button(key="exec_C").click().run()

    second.run()
    assert second.session_state["demo"].audit_entries() == []
    assert second.session_state["demo"].current("C") is None
    assert len(first.session_state["demo"].audit_entries()) == 3

    # second visitor's activity stays out of the first visitor's audit page
    second.button(key="pick_A").click().run()
    second.button(key="eval_A").click().run()
    first.session_state["page"] = PAGES[3]
    first.run()
    assert len(first.session_state["demo"].audit_entries()) == 3
    assert not first.exception


def test_audit_page_shows_session_activity():
    at = _app(PAGES[2])
    at.button(key="pick_B").click().run()
    at.button(key="eval_B").click().run()
    at.button(key="exec_B").click().run()
    at.session_state["page"] = PAGES[3]
    at.run()
    text = _text(at)
    assert "RECOMMENDATION_CANNOT_EXECUTE" in text
    assert "Hash chain intact · 2 entries" in text


def test_reset_clears_only_this_session():
    at = _app(PAGES[2])
    at.button(key="eval_A").click().run()
    assert at.session_state["demo"].audit_entries()
    at.sidebar.button[0].click().run()
    assert at.session_state["demo"].audit_entries() == []
