"""Read-only views of the fictional FlowPilot Reservoir for the Explore Context page.

Uses the Reservoir's own repository (`source_repo`), schemas
(`DecisionReviewSynthesis`) and deterministic `compute_evidence_strength`, via
the vendored copies. The fixture is opened with SQLite `mode=ro`, so a write
raises instead of succeeding. Call only after `engine.load_shared()`, which
puts the vendored Reservoir modules on the import path.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from demo.engine import FIXTURE_DB

PRIMARY_REVIEW_ID = "REV-0d430e0d"  # the review the Trust Layer scenarios are built on


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{FIXTURE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@dataclass(frozen=True)
class SourceView:
    source_id: str
    title: str
    source_type: str
    status: str
    created_at: date
    age_days: int
    superseded_by: str | None
    source_reference: str
    author_role: str | None
    segment: str | None
    decision_owner: str | None
    content: str


def list_sources(as_of: date | None = None) -> list[SourceView]:
    from app.storage import source_repo

    as_of = as_of or date.today()
    conn = _conn()
    try:
        sources = source_repo.list_sources(conn)
    finally:
        conn.close()
    return [SourceView(
        source_id=s.source_id, title=s.title, source_type=s.source_type.value, status=s.status.value,
        created_at=s.created_at, age_days=(as_of - s.created_at).days, superseded_by=s.superseded_by,
        source_reference=s.source_reference, author_role=s.author_role, segment=s.segment,
        decision_owner=s.decision_owner, content=s.content,
    ) for s in sorted(sources, key=lambda s: s.source_id)]


def load_review(review_id: str = PRIMARY_REVIEW_ID):
    """The stored Decision Review synthesis, parsed by the Reservoir's own schema."""
    from app.schemas.synthesis import DecisionReviewSynthesis

    conn = _conn()
    try:
        row = conn.execute("SELECT synthesis_json FROM reviews WHERE review_id = ?", (review_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise KeyError(f"review {review_id} not found in the Reservoir fixture")
    return DecisionReviewSynthesis.model_validate_json(row["synthesis_json"])


def compute_strength(source_ids: list[str], challenger_verdict: str | None, as_of: date | None = None) -> str:
    """Run the Reservoir's deterministic evidence-strength function on chosen sources."""
    from app.schemas.challenger import ChallengerVerdict
    from app.storage import source_repo
    from app.synthesis.evidence_strength import compute_evidence_strength

    conn = _conn()
    try:
        by_id = {s.source_id: s for s in source_repo.list_sources(conn)}
    finally:
        conn.close()
    unknown = set(source_ids) - by_id.keys()
    if unknown:
        raise KeyError(f"not in the Reservoir corpus: {sorted(unknown)}")
    verdict = ChallengerVerdict(challenger_verdict) if challenger_verdict else None
    return compute_evidence_strength([by_id[s] for s in source_ids], verdict, as_of or date.today()).value


def challenger_verdicts() -> list[str]:
    from app.schemas.challenger import ChallengerVerdict
    return [v.value for v in ChallengerVerdict]
