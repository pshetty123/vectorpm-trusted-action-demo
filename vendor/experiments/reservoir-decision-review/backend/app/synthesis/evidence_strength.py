"""
Deterministic evidence-strength heuristic. No LLM involved — the spec
explicitly forbids LLM-invented confidence percentages (section 15).

    source_count_score    0/1/2/3+ sources                          -> 0/1/2/3
    type_diversity_score  1/2/3+ distinct source_types among them    -> 0/1/2
    freshness_score       freshest supporter <=90d/<=180d/older      -> 2/1/0
                           (a stale-status supporter never counts as fresh)
    contradiction_penalty CONTRADICTED/WEAK_EVIDENCE/SUPPORTED       -> -2/-1/0

    stakeholder_only_flag  True if every supporting source has
                            source_type == stakeholder_signal         -> hard-caps LOW
                            (this is the literal encoding of "sales wants X
                            is a stakeholder signal, not customer evidence")

    total = source_count_score + type_diversity_score + freshness_score + contradiction_penalty

    INSUFFICIENT  if 0 supporting sources, OR verdict == INSUFFICIENT_CONTEXT, OR total <= 0
    LOW           if total in [1,2], OR stakeholder_only_flag (overrides total upward cases)
    MEDIUM        if total in [3,4]
    HIGH          if total >= 5 AND verdict not in {CONTRADICTED, WEAK_EVIDENCE}
"""
from datetime import date

from app.schemas.challenger import ChallengerVerdict
from app.schemas.context_source import ContextSource, SourceType
from app.schemas.synthesis import EvidenceStrength


def _source_count_score(n: int) -> int:
    return min(n, 3)


def _type_diversity_score(sources: list[ContextSource]) -> int:
    n_types = len({s.source_type for s in sources})
    return min(max(n_types - 1, 0), 2)


def _freshness_score(sources: list[ContextSource], today: date) -> int:
    fresh_candidates = [s for s in sources if s.status != "stale"]
    if not fresh_candidates:
        return 0
    freshest_age = min((today - s.created_at).days for s in fresh_candidates)
    if freshest_age <= 90:
        return 2
    if freshest_age <= 180:
        return 1
    return 0


def _contradiction_penalty(verdict: ChallengerVerdict | None) -> int:
    if verdict == ChallengerVerdict.CONTRADICTED:
        return -2
    if verdict == ChallengerVerdict.WEAK_EVIDENCE:
        return -1
    return 0


def compute_evidence_strength(
    supporting_sources: list[ContextSource],
    challenger_verdict: ChallengerVerdict | None,
    today: date,
) -> EvidenceStrength:
    if not supporting_sources or challenger_verdict == ChallengerVerdict.INSUFFICIENT_CONTEXT:
        return EvidenceStrength.INSUFFICIENT

    stakeholder_only = all(s.source_type == SourceType.STAKEHOLDER_SIGNAL for s in supporting_sources)

    total = (
        _source_count_score(len(supporting_sources))
        + _type_diversity_score(supporting_sources)
        + _freshness_score(supporting_sources, today)
        + _contradiction_penalty(challenger_verdict)
    )

    if total <= 0:
        return EvidenceStrength.INSUFFICIENT
    if stakeholder_only:
        return EvidenceStrength.LOW
    if total <= 2:
        return EvidenceStrength.LOW
    if total <= 4:
        return EvidenceStrength.MEDIUM
    if challenger_verdict in (ChallengerVerdict.CONTRADICTED, ChallengerVerdict.WEAK_EVIDENCE):
        return EvidenceStrength.MEDIUM
    return EvidenceStrength.HIGH
