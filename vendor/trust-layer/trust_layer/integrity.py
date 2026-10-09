"""Context packet integrity checks. Pure functions: the corpus index is passed in,
so the checks need no database and can be tested in isolation.

A packet passes only if every check passes. Anything else fails closed (L0)."""
from __future__ import annotations

from dataclasses import dataclass, field

from trust_layer.schemas import CONTRACT_VERSION, STRENGTH_ORDER, ContextPacket, ContextPacketBody, SourceRef

SOURCE_FIELDS_CHECKED = ("source_type", "title", "created_at", "status", "superseded_by",
                         "source_reference", "decision_owner", "content_sha256")


@dataclass
class IntegrityReport:
    ok: bool
    errors: list[str] = field(default_factory=list)


REDERIVED_FIELDS = ("query", "corpus_fingerprint", "sources", "findings", "assumptions",
                    "decisions", "missing_information", "freshness")


def check_packet(packet: ContextPacket, corpus: dict[str, SourceRef],
                 known_review_ids: set[str] | None = None,
                 corpus_fingerprint: str | None = None,
                 rederived: ContextPacketBody | Exception | None = None) -> IntegrityReport:
    """`rederived` is the body the Reservoir produces for this packet's origin
    (or the exception raised trying). Any difference means the packet's evidence
    is not what the Reservoir says, even if the attacker re-sealed the hash."""
    errors: list[str] = []
    body = packet.body

    if corpus_fingerprint is not None and body.corpus_fingerprint != corpus_fingerprint:
        errors.append("CORPUS_CHANGED: packet was built against a different Reservoir corpus")

    if isinstance(rederived, Exception):
        errors.append(f"UNVERIFIABLE_ORIGIN: {rederived}")
    elif rederived is not None:
        for f in REDERIVED_FIELDS:
            if getattr(body, f) != getattr(rederived, f):
                errors.append(f"CONTENT_MISMATCH: packet {f} differs from what the Reservoir produces")

    # 1. The packet is exactly what was sealed.
    if packet.packet_id != body.compute_id():
        errors.append("PACKET_HASH_MISMATCH: packet_id does not match packet contents")

    if body.contract_version != CONTRACT_VERSION:
        errors.append(f"CONTRACT_VERSION: expected {CONTRACT_VERSION}, got {body.contract_version}")

    # 2. Every source in the packet exists in the Reservoir and is unaltered.
    #    Catches a re-sealed packet whose labels were changed (e.g. superseded -> current).
    for s in body.sources:
        real = corpus.get(s.source_id)
        if real is None:
            errors.append(f"UNKNOWN_SOURCE: {s.source_id} is not in the Reservoir corpus")
            continue
        for f in SOURCE_FIELDS_CHECKED:
            if getattr(s, f) != getattr(real, f):
                errors.append(f"SOURCE_MISMATCH: {s.source_id}.{f} differs from the Reservoir")

    # 3. Every citation points at a source carried in the packet.
    in_packet = {s.source_id for s in body.sources}
    cited: list[tuple[str, str]] = []
    for f in body.findings:
        if f.strength not in STRENGTH_ORDER:
            errors.append(f"INVALID_STRENGTH: {f.finding_id} has strength {f.strength!r}")
        cited += [(f.finding_id, sid) for sid in f.supporting_ids + f.contradictory_ids + f.historical_ids]
    for a in body.assumptions:
        cited += [(a.assumption_id, sid) for sid in a.source_ids]
    for d in body.decisions:
        cited += [(d.decision_id, sid) for sid in d.source_ids]
    for owner, sid in cited:
        if sid not in in_packet:
            errors.append(f"INVALID_CITATION: {owner} cites {sid}, which is not in the packet")

    # 4. Freshness summary agrees with the sources it summarises.
    if set(body.freshness.superseded_ids) != {s.source_id for s in body.sources if s.status == "superseded"}:
        errors.append("FRESHNESS_MISMATCH: superseded_ids do not match source statuses")
    if set(body.freshness.stale_ids) != {s.source_id for s in body.sources if s.status == "stale"}:
        errors.append("FRESHNESS_MISMATCH: stale_ids do not match source statuses")

    # 5. A review-derived packet must come from a review that exists.
    if body.origin.get("kind") == "review" and known_review_ids is not None:
        if body.origin.get("review_id") not in known_review_ids:
            errors.append(f"UNKNOWN_ORIGIN: review {body.origin.get('review_id')} not in the Reservoir")

    return IntegrityReport(ok=not errors, errors=errors)
