"""Read-only VectorPM Reservoir context adapter.

The only module in the Trust Layer that imports Reservoir code. It reuses the
experiment's own schemas (ContextSource, DecisionReviewSynthesis), repository
(source_repo) and deterministic evidence-strength function, and translates them
into the Trust Layer's ContextPacket.

Read-only by construction: the database is opened with SQLite `mode=ro`, so any
write raises. It points at a copied fixture, never at the experiment's own DB.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from trust_layer.schemas import (
    ContextPacket, ContextPacketBody, Freshness, PacketAssumption, PacketDecision,
    PacketFinding, SourceRef, canonical_json, sha256_hex,
)

TRUST_LAYER_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = TRUST_LAYER_ROOT / "fixtures" / "flowpilot_reservoir.db"
DEFAULT_BACKEND = TRUST_LAYER_ROOT.parent / "experiments" / "reservoir-decision-review" / "backend"


def _import_reservoir(backend: Path):
    """Import the experiment's modules without writing bytecode into its tree."""
    sys.dont_write_bytecode = True
    if str(backend) not in sys.path:
        sys.path.append(str(backend))
    from app.schemas.context_source import ContextSource  # noqa: F401
    from app.schemas.synthesis import DecisionReviewSynthesis
    from app.schemas.challenger import ChallengerVerdict
    from app.storage import source_repo
    from app.synthesis.evidence_strength import compute_evidence_strength
    return DecisionReviewSynthesis, ChallengerVerdict, source_repo, compute_evidence_strength


@dataclass
class FindingSpec:
    """For packets built directly from corpus sources (not from a stored review).
    Strength is computed by the Reservoir's own deterministic function."""
    finding_id: str
    statement: str
    supporting_ids: list[str]
    contradictory_ids: list[str] = field(default_factory=list)
    challenger_verdict: Optional[str] = None  # SUPPORTED | WEAK_EVIDENCE | CONTRADICTED | INSUFFICIENT_CONTEXT
    section: str = "what_we_know"


class ReservoirAdapter:
    def __init__(self, db_path: Path | None = None, backend_path: Path | None = None):
        self.db_path = Path(db_path or os.environ.get("TRUST_LAYER_FIXTURE_DB", DEFAULT_FIXTURE))
        backend = Path(backend_path or os.environ.get("VECTORPM_RESERVOIR_BACKEND", DEFAULT_BACKEND))
        (self._Synthesis, self._Verdict, self._source_repo,
         self._compute_strength) = _import_reservoir(backend)

    # ---------------------------------------------------------------- read-only access
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _sources(self) -> dict:
        conn = self._conn()
        try:
            return {s.source_id: s for s in self._source_repo.list_sources(conn)}
        finally:
            conn.close()

    @staticmethod
    def _ref(s) -> SourceRef:
        return SourceRef(
            source_id=s.source_id, source_type=s.source_type.value, title=s.title,
            created_at=s.created_at, status=s.status.value, superseded_by=s.superseded_by,
            source_reference=s.source_reference, decision_owner=s.decision_owner,
            content_sha256=sha256_hex(s.content),
        )

    def corpus_index(self) -> dict[str, SourceRef]:
        """What integrity checks compare a packet's sources against."""
        return {sid: self._ref(s) for sid, s in self._sources().items()}

    def corpus_fingerprint(self, index: dict[str, SourceRef] | None = None) -> str:
        index = index or self.corpus_index()
        return sha256_hex(canonical_json({k: v.model_dump(mode="json") for k, v in sorted(index.items())}))

    def review_ids(self) -> list[str]:
        conn = self._conn()
        try:
            return [r["review_id"] for r in conn.execute("SELECT review_id FROM reviews ORDER BY created_at")]
        finally:
            conn.close()

    def list_reviews(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute("SELECT review_id, proposed_decision, created_at FROM reviews ORDER BY created_at")
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _load_review(self, review_id: str):
        conn = self._conn()
        try:
            row = conn.execute("SELECT synthesis_json FROM reviews WHERE review_id = ?", (review_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            raise KeyError(f"review {review_id} not found in Reservoir fixture")
        return self._Synthesis.model_validate_json(row["synthesis_json"])

    # ---------------------------------------------------------------- packet builders
    def _seal(self, *, query: str, origin: dict, cited: set[str], findings, assumptions,
              decisions, missing, as_of: date | None) -> ContextPacket:
        index = self.corpus_index()
        unknown = cited - index.keys()
        if unknown:
            raise KeyError(f"cited source(s) not in Reservoir corpus: {sorted(unknown)}")
        as_of = as_of or date.today()
        refs = tuple(index[sid] for sid in sorted(cited))
        ages = [(as_of - r.created_at).days for r in refs] or [0]
        body = ContextPacketBody(
            generated_at=datetime.now(timezone.utc),
            origin=origin,
            corpus_fingerprint=self.corpus_fingerprint(index),
            query=query,
            sources=refs,
            findings=tuple(findings),
            assumptions=tuple(assumptions),
            decisions=tuple(decisions),
            missing_information=tuple(missing),
            freshness=Freshness(
                as_of=as_of,
                stale_ids=tuple(r.source_id for r in refs if r.status == "stale"),
                superseded_ids=tuple(r.source_id for r in refs if r.status == "superseded"),
                oldest_source_age_days=max(ages),
                newest_source_age_days=min(ages),
            ),
        )
        return ContextPacket.seal(body)

    def packet_from_review(self, review_id: str, as_of: date | None = None) -> ContextPacket:
        """Packet from a stored Decision Review — the Reservoir's own synthesis,
        unmodified. Strengths are the ones the experiment computed and saved."""
        r = self._load_review(review_id)
        ids = lambda ev: tuple(e.source_id for e in ev)  # noqa: E731

        findings, cited = [], set()
        for section in ("what_we_know", "what_challenges", "strategic_context"):
            for f in getattr(r, section):
                pf = PacketFinding(
                    finding_id=f.id, section=section, statement=f.statement, strength=f.strength.value,
                    supporting_ids=ids(f.evidence.supporting), contradictory_ids=ids(f.evidence.contradictory),
                    historical_ids=ids(f.evidence.historical),
                )
                findings.append(pf)
                cited |= set(pf.supporting_ids + pf.contradictory_ids + pf.historical_ids)

        assumptions = []
        for i, a in enumerate(r.assumptions, 1):
            src = ids(a.evidence.supporting) + ids(a.evidence.contradictory) + ids(a.evidence.historical)
            assumptions.append(PacketAssumption(assumption_id=f"assumption_{i}", assumption=a.assumption,
                                                evidence_status=a.evidence_status, source_ids=src))
            cited |= set(src)

        decisions = []
        for d in r.previous_decisions:
            src = ids(d.evidence.supporting) + ids(d.evidence.historical)
            decisions.append(PacketDecision(decision_id=d.decision_id, summary=d.decision, source_ids=src))
            cited |= set(src)

        return self._seal(
            query=r.proposed_decision, origin={"kind": "review", "review_id": r.review_id},
            cited=cited, findings=findings, assumptions=assumptions, decisions=decisions,
            missing=r.missing_context, as_of=as_of,
        )

    def build_packet(self, query: str, specs: list[FindingSpec], as_of: date | None = None) -> ContextPacket:
        """Packet from explicit corpus citations. Every cited source must exist in
        the corpus; strength comes from the Reservoir's compute_evidence_strength."""
        sources = self._sources()
        as_of = as_of or date.today()
        findings, cited = [], set()
        for spec in specs:
            missing = set(spec.supporting_ids + spec.contradictory_ids) - sources.keys()
            if missing:
                raise KeyError(f"cited source(s) not in Reservoir corpus: {sorted(missing)}")
            verdict = self._Verdict(spec.challenger_verdict) if spec.challenger_verdict else None
            strength = self._compute_strength([sources[s] for s in spec.supporting_ids], verdict, as_of)
            findings.append(PacketFinding(
                finding_id=spec.finding_id, section=spec.section, statement=spec.statement,
                strength=strength.value, supporting_ids=tuple(spec.supporting_ids),
                contradictory_ids=tuple(spec.contradictory_ids),
                challenger_verdict=spec.challenger_verdict,
            ))
            cited |= set(spec.supporting_ids + spec.contradictory_ids)
        return self._seal(query=query, origin={"kind": "constructed"}, cited=cited, findings=findings,
                          assumptions=[], decisions=[], missing=[], as_of=as_of)

    # ---------------------------------------------------------------- integrity support
    def rederive(self, packet: ContextPacket) -> ContextPacketBody:
        """Rebuild the packet body from the Reservoir using the packet's own
        origin and as_of date. Integrity checks compare the two, so a re-sealed
        packet with altered evidence (strength, citations, statuses) is caught."""
        origin, as_of = packet.body.origin, packet.body.freshness.as_of
        if origin.get("kind") == "review":
            return self.packet_from_review(origin["review_id"], as_of=as_of).body
        if origin.get("kind") == "constructed":
            specs = [FindingSpec(f.finding_id, f.statement, list(f.supporting_ids), list(f.contradictory_ids),
                                 f.challenger_verdict, f.section) for f in packet.body.findings]
            return self.build_packet(packet.body.query, specs, as_of=as_of).body
        raise KeyError(f"unknown packet origin {origin!r}")
