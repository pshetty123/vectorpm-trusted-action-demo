"""Thin adapter between Streamlit and the vendored, tested prototype code.

Nothing here decides autonomy. Every level, reason code, approval check and
execution refusal comes from the Trust Layer's own `TrustService`, `evaluate`
and `check_packet`. This module only:

  1. verifies the vendored code and data are byte-identical to what was tested
     (fails closed if not),
  2. loads the shared, read-only pieces once (policy, Reservoir adapter), and
  3. gives each browser session its own TrustService backed by a private
     in-memory SQLite database, so approvals, executions and audit history
     can never leak between visitors or persist after the session ends.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEMO_ROOT = Path(__file__).resolve().parents[1]
VENDOR = DEMO_ROOT / "vendor"
TRUST_LAYER_ROOT = VENDOR / "trust-layer"
RESERVOIR_BACKEND = VENDOR / "experiments" / "reservoir-decision-review" / "backend"
FIXTURE_DB = TRUST_LAYER_ROOT / "fixtures" / "flowpilot_reservoir.db"
POLICY_PATH = TRUST_LAYER_ROOT / "policy" / "flowpilot_policy.v1.json"

SCENARIO_KEYS = ("A", "B", "C", "D", "E", "F")


class VendorIntegrityError(RuntimeError):
    """Vendored code or data differs from the pinned, tested copy."""


def verify_vendor(vendor: Path = VENDOR) -> dict[str, str]:
    """Check every vendored file against VENDORED.json. Raises on any mismatch."""
    manifest_path = vendor / "VENDORED.json"
    if not manifest_path.is_file():
        raise VendorIntegrityError("vendor/VENDORED.json is missing")
    pinned = json.loads(manifest_path.read_text())["files"]
    problems = []
    for rel, expected in pinned.items():
        p = vendor / rel
        if not p.is_file():
            problems.append(f"missing: {rel}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            problems.append(f"modified: {rel}")
    if problems:
        raise VendorIntegrityError("; ".join(problems))
    return pinned


def _ensure_import_path() -> None:
    sys.dont_write_bytecode = True  # keep vendor/ free of build artefacts
    if str(TRUST_LAYER_ROOT) not in sys.path:
        sys.path.insert(0, str(TRUST_LAYER_ROOT))


@dataclass(frozen=True)
class SharedResources:
    """Read-only objects shared by every session. Never mutated after load."""
    policy: object
    adapter: object


def load_shared() -> SharedResources:
    verify_vendor()
    _ensure_import_path()
    from trust_layer.adapters.vectorpm import ReservoirAdapter
    from trust_layer.policy import load_policy

    # Explicit paths, so environment variables on a host can't redirect the
    # adapter to a different database or Reservoir codebase.
    adapter = ReservoirAdapter(db_path=FIXTURE_DB, backend_path=RESERVOIR_BACKEND)
    return SharedResources(policy=load_policy(POLICY_PATH), adapter=adapter)


@dataclass
class DemoSession:
    """One visitor's private Trust Layer instance and scenario state."""
    shared: SharedResources
    service: object = field(init=False)
    scenarios: dict = field(init=False)
    latest: dict = field(default_factory=dict)  # scenario key -> evaluation_id

    def __post_init__(self) -> None:
        from trust_layer import scenarios as scenario_mod
        from trust_layer.service import TrustService

        # ":memory:" gives this session its own database that dies with it.
        self.service = TrustService(self.shared.policy, self.shared.adapter, ":memory:")
        built = scenario_mod.build(self.shared.adapter)
        self.scenarios = {k: built[k] for k in SCENARIO_KEYS}

    # -------------------------------------------------------------- actions
    def evaluate(self, key: str, claimed_confidence: float | None = None) -> dict:
        proposal = self.scenarios[key]["proposal"]
        if claimed_confidence is not None:
            proposal = proposal.model_copy(update={"claimed_confidence": float(claimed_confidence)})
        row = self.service.submit(proposal)
        self.latest[key] = row["evaluation_id"]
        return row

    def approve(self, evaluation_id: str, approver_id: str, note: str = "") -> dict:
        return self.service.approve(evaluation_id, approver_id, note)

    def reject(self, evaluation_id: str, approver_id: str, note: str = "") -> dict:
        return self.service.reject(evaluation_id, approver_id, note)

    def execute(self, evaluation_id: str, requested_by: str) -> dict:
        return self.service.execute(evaluation_id, requested_by)

    # -------------------------------------------------------------- reads
    def get(self, evaluation_id: str) -> dict:
        return self.service.get(evaluation_id)

    def current(self, key: str) -> dict | None:
        ev = self.latest.get(key)
        return self.service.get(ev) if ev else None

    def audit_entries(self) -> list[dict]:
        return self.service.audit.entries()

    def audit_chain(self):
        return self.service.audit.verify()
