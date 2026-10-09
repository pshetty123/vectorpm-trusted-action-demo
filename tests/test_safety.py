"""Public-demo safety: isolation, fail-closed behaviour, read-only data,
no external effects, no absolute paths, untouched vendored code."""
import hashlib
import json
import re
import shutil
import sqlite3
from pathlib import Path

import pytest
from trust_layer.schemas import ContextPacket, Level

from demo.engine import (
    DEMO_ROOT, FIXTURE_DB, POLICY_PATH, VENDOR, DemoSession, VendorIntegrityError, verify_vendor,
)

MONOREPO = DEMO_ROOT.parent


# ---------------------------------------------------------------- session isolation (criterion 10)
def test_sessions_do_not_share_state(shared):
    a, b = DemoSession(shared), DemoSession(shared)
    ev = a.evaluate("C")["evaluation_id"]
    a.approve(ev, "human.ana-ortiz")
    a.execute(ev, "agent.decision-analyst")

    assert b.audit_entries() == []
    assert b.current("C") is None
    with pytest.raises(Exception):
        b.get(ev)  # b cannot see a's evaluation
    with pytest.raises(Exception):
        b.approve(ev, "human.ana-ortiz")  # nor act on it
    assert a.get(ev)["state"] == "EXECUTED"
    assert len(a.audit_entries()) == 3

    # b's activity doesn't appear in a's log either
    b.evaluate("A")
    assert len(a.audit_entries()) == 3
    assert a.service.conn is not b.service.conn


def test_session_state_is_in_memory_only(session):
    path = session.service.conn.execute("PRAGMA database_list").fetchone()[2]
    assert path == ""  # in-memory: no file on disk to share or persist


# ---------------------------------------------------------------- fail closed
def test_unknown_action_fails_closed(session):
    p = session.scenarios["A"]["proposal"].model_copy(update={"action_type": "email.blast_all_customers"})
    row = session.service.submit(p)
    assert row["decision"].level == Level.L0
    assert "UNKNOWN_ACTION_TYPE" in [r.value for r in row["decision"].reasons]


def test_unknown_agent_fails_closed(session):
    p = session.scenarios["A"]["proposal"].model_copy(update={"proposer_id": "agent.rogue"})
    assert session.service.submit(p)["decision"].level == Level.L0


def test_hand_edited_packet_fails_closed(session):
    p = session.scenarios["A"]["proposal"]
    body = json.loads(p.context_packet.model_dump_json())
    body["body"]["findings"][0]["strength"] = "HIGH" if body["body"]["findings"][0]["strength"] != "HIGH" else "LOW"
    forged = p.model_copy(update={"context_packet": ContextPacket.model_validate(body)})
    row = session.service.submit(forged)
    assert row["decision"].level == Level.L0
    assert any("PACKET_HASH_MISMATCH" in x for x in row["decision"].integrity_errors)


# ---------------------------------------------------------------- read-only data + unchanged policy
def test_fixture_is_opened_read_only(shared):
    conn = sqlite3.connect(f"file:{FIXTURE_DB}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM sources")
    conn.close()


def test_running_scenarios_changes_no_files(shared):
    before = verify_vendor()
    s = DemoSession(shared)
    for k in "ABCDEF":
        s.evaluate(k)
    assert verify_vendor() == before
    assert shared.policy.file_sha256 == hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()


def test_tampered_vendor_copy_is_rejected(tmp_path):
    copy = tmp_path / "vendor"
    shutil.copytree(VENDOR, copy)
    policy = copy / "trust-layer/policy/flowpilot_policy.v1.json"
    policy.write_text(policy.read_text().replace('"prohibitions": [', '"prohibitions": [ ', 1))
    with pytest.raises(VendorIntegrityError, match="modified"):
        verify_vendor(copy)


@pytest.mark.skipif(not (MONOREPO / "trust-layer" / "trust_layer").is_dir(),
                    reason="upstream prototypes not present (standalone checkout)")
def test_vendor_matches_upstream_prototypes():
    pinned = json.loads((VENDOR / "VENDORED.json").read_text())["files"]
    for rel, digest in pinned.items():
        assert hashlib.sha256((MONOREPO / rel).read_bytes()).hexdigest() == digest, rel


# ---------------------------------------------------------------- no external effects (criterion 12)
NETWORK = re.compile(r"^\s*(?:import|from)\s+(requests|httpx|urllib|socket|smtplib|http\.client|aiohttp|"
                     r"anthropic|openai|boto3|slack_sdk)\b", re.M)


def _python_files():
    for base in (DEMO_ROOT / "demo", VENDOR, ):
        yield from base.rglob("*.py")
    yield DEMO_ROOT / "streamlit_app.py"


def test_no_network_or_llm_clients_imported():
    hits = [str(p.relative_to(DEMO_ROOT)) for p in _python_files() if NETWORK.search(p.read_text())]
    assert hits == []


def test_every_simulated_outcome_declares_no_side_effects(session):
    from trust_layer.simulator import NO_SIDE_EFFECTS
    row = session.evaluate("A")
    assert row["outcome"]["note"] == NO_SIDE_EFFECTS


# ---------------------------------------------------------------- portability (criteria 13, 14)
def test_no_absolute_local_paths_in_package():
    # Built from fragments so this file doesn't match its own pattern.
    pat = re.compile("|".join(["/" + "Users/", "/" + "home/[a-z]", "[A-Z]:" + r"\\"]))
    texts = [p for p in DEMO_ROOT.rglob("*")
             if p.is_file() and ".venv" not in p.parts and "__pycache__" not in p.parts
             and p.suffix in {".py", ".md", ".txt", ".toml", ".json", ".cfg", ".ini"}]
    assert [str(p.relative_to(DEMO_ROOT)) for p in texts if pat.search(p.read_text())] == []


def test_requirements_cover_runtime_imports():
    reqs = (DEMO_ROOT / "requirements.txt").read_text().lower()
    for pkg in ("streamlit", "pydantic"):
        assert pkg in reqs


def test_streamlit_config_hides_error_details_from_visitors():
    import tomllib
    cfg = tomllib.loads((DEMO_ROOT / ".streamlit" / "config.toml").read_text())
    assert cfg["client"]["showErrorDetails"] == "none"  # `false` is deprecated and means "stacktrace"
    assert cfg["client"]["toolbarMode"] == "viewer"
    assert cfg["server"]["enableXsrfProtection"] is True
    assert cfg["browser"]["gatherUsageStats"] is False
    assert not (DEMO_ROOT / ".streamlit" / "secrets.toml").exists()
