"""Editorial layer for the Explore Context page: what to show first, and how to
group it. Presentation only.

Rules this module follows:
  * Never invents a strength. Every badge comes from the stored review.
  * Never paraphrases evidence where the original is shown. Headlines are the
    finding's own first sentence, and Challenger findings are split at their
    own " — " separator, not rewritten.
  * The Decision Brief is the one place with summary copy. Every number in it
    must appear in the review text (tests enforce this), and every item cites
    the finding, assumption or gap it summarises, resolved against live data.
    If a cited id is missing, building the brief raises rather than showing
    an unsupported summary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# --------------------------------------------------------------- which item goes where
LEAD_FINDING = "problem_evidence"        # does the problem exist?
LEAD_CHALLENGE = "solution_evidence"     # would an AI assistant solve it?
LEAD_UNKNOWN_INDEX = 0                   # missing_context[0]: DEC-014 review outcome

PROBLEM_SIDE = {"findings": [LEAD_FINDING], "assumptions": [1]}
SOLUTION_SIDE = {"findings": [LEAD_CHALLENGE, "challenger_finding_4"], "assumptions": [2, 3]}
TOP_GAPS = 3

ASSUMPTION_LABEL = {
    "SUPPORTED": "Supported by the evidence",
    "WEAK": "Weakly supported",
    "CONTRADICTED": "Contradicted by the evidence",
    "INSUFFICIENT_CONTEXT": "Not enough evidence to judge",
}

CHALLENGE_TARGET_LABEL = {
    "previous_decisions": "a previous decision and how it is being used",
    "assumption": "an assumption",
    "what_we_know": "a finding",
    "strategic_context": "the strategic context",
}


@dataclass(frozen=True)
class BriefItem:
    label: str
    text: str
    finding_ids: tuple[str, ...] = ()     # strengths shown are these findings' stored strengths
    assumption_numbers: tuple[int, ...] = ()
    gap_indexes: tuple[int, ...] = ()
    source_ids: tuple[str, ...] = ()      # must be cited by the findings/assumptions above


# Reviewed claim by claim against REV-0d430e0d. Wording tracks the stored text:
#   problem      problem_evidence ("61% -> 44%", "heavily concentrated in Salesforce-connecting
#                workspaces", "real but not single-cause"); assumption_1 WEAK (connection decline
#                as primary driver)
#   fix          solution_evidence (FP-011: assistant "would not reduce the underlying OAuth handshake
#                failure rate that is driving the steepest cohort decline"; DEC-014 "rejected building
#                guided/assisted onboarding UI in favor of fixing root-cause connection reliability");
#                assumption_2 INSUFFICIENT_CONTEXT with no sources; gap 4 (no structured research on
#                whether an assistant would have changed outcomes)
#   qualifier    challenger_finding_3 ("backend uptime improvement (92%->99.2%)", client-visible error
#                "has NOT been isolated in instrumentation"); assumption_4; gaps 1-2 (DEC-014 review, isolated error data)
BRIEF_HEADLINE = "The problem is well evidenced. The proposed fix is not."
BRIEF = (
    BriefItem("The problem",
              "Onboarding completion fell from 61% to 44% across Q1–Q3 FY27, heavily concentrated in workspaces "
              "that connect Salesforce. The problem is real but not single-cause.",
              finding_ids=("problem_evidence",), assumption_numbers=(1,),
              source_ids=("FP-007", "FP-008", "FP-006")),
    BriefItem("The proposed fix",
              "No cited source shows that an AI assistant would solve it. Engineering says an assistant would not "
              "reduce the OAuth failures driving the steepest cohort decline, and DEC-014 rejected assisted "
              "onboarding in favour of fixing connection reliability.",
              finding_ids=("solution_evidence",), assumption_numbers=(2,), gap_indexes=(3,),
              source_ids=("FP-011", "FP-003", "FP-012")),
    BriefItem("Key qualification",
              "Backend connection success improved from 92% to 99.2%, but the error customers actually see has not "
              "been measured separately, and the outcome of DEC-014's scheduled 2026-09-30 review is not in the "
              "evidence.",
              finding_ids=("challenger_finding_3",), assumption_numbers=(4,), gap_indexes=(0, 1),
              source_ids=("FP-011", "FP-012")),
)

# Short display headlines. The full stored statement is always one click away,
# verbatim. Numbers and source ids in a headline must appear in that finding's
# own statement or citations (tests enforce this).
HEADLINES = {
    "problem_evidence": "Onboarding completion fell from 61% to 44%, concentrated in Salesforce-connecting "
                        "workspaces. The problem is real but not single-cause.",
    "solution_evidence": "The evidence argues against an AI assistant as the fix for the measured problem.",
    "challenger_finding_3": "Backend reliability improved (92% to 99.2%), but the customer-visible connection "
                            "error has not been measured separately.",
    "challenger_finding_4": "Competitive pressure rests on sales opinion: no deal was confirmed lost over it, and "
                            "no competitor has published efficacy data.",
    "strategic_alignment": "Current strategy (FP-001) scopes onboarding work to the enterprise KR2.2 metric. No "
                           "source ties an AI assistant to it.",
}


def headline(f) -> str:
    """Short headline if one was written for this finding, else its own first sentence."""
    return HEADLINES.get(f.id) or first_sentence(f.statement)


# --------------------------------------------------------------- text helpers (no rewriting)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def first_sentence(text: str) -> str:
    """The statement's own first sentence, verbatim."""
    return _SENTENCE_END.split(text.strip(), maxsplit=1)[0]


def rest_after_first_sentence(text: str) -> str:
    parts = _SENTENCE_END.split(text.strip(), maxsplit=1)
    return parts[1] if len(parts) > 1 else ""


@dataclass(frozen=True)
class ChallengeParts:
    target: str | None   # e.g. "assumption", as written by the Challenger
    claim: str           # the claim under test, verbatim
    assessment: str      # the Challenger's assessment, verbatim


def split_challenge(statement: str) -> ChallengeParts | None:
    """Challenger findings are written as '<target>: <claim> — <assessment>'.
    Split on that structure only; return None if it isn't present."""
    m = re.match(r"^([a-z_]+):\s+(.*?)\s+—\s+(.*)$", statement.strip(), re.S)
    if not m:
        return None
    return ChallengeParts(target=m.group(1), claim=m.group(2), assessment=m.group(3))


def challenge_target_label(target: str | None) -> str:
    return CHALLENGE_TARGET_LABEL.get(target or "", target or "a claim")


def show_rationale(decision) -> bool:
    """The Reservoir's synthesizer fills `decision` and `rationale_summary` from
    the same field, so in every stored review they're identical. Show the
    rationale only when it adds something."""
    return decision.rationale_summary.strip() != decision.decision.strip()


# --------------------------------------------------------------- lookups against live data
def all_findings(review) -> dict:
    return {f.id: f for sec in ("what_we_know", "what_challenges", "strategic_context")
            for f in getattr(review, sec)}


def finding_section(review, finding_id: str) -> str:
    for sec in ("what_we_know", "what_challenges", "strategic_context"):
        if any(f.id == finding_id for f in getattr(review, sec)):
            return sec
    raise KeyError(finding_id)


def assumption(review, number: int):
    """1-based, matching the Trust Layer's `assumption_<n>` ids."""
    if not 1 <= number <= len(review.assumptions):
        raise KeyError(f"assumption_{number}")
    return review.assumptions[number - 1]


def validate_brief(review) -> None:
    """Raise if the brief cites anything the review doesn't contain."""
    findings = all_findings(review)
    for item in BRIEF:
        for fid in item.finding_ids:
            if fid not in findings:
                raise KeyError(f"brief cites finding {fid}, which is not in review {review.review_id}")
        for n in item.assumption_numbers:
            assumption(review, n)
        for g in item.gap_indexes:
            if g >= len(review.missing_context):
                raise KeyError(f"brief cites missing-information gap {g}, which does not exist")
        cited = cited_sources(review, item.finding_ids, item.assumption_numbers)
        stray = set(item.source_ids) - cited
        if stray:
            raise KeyError(f"brief item {item.label!r} names {sorted(stray)}, which its findings don't cite")
    for fid in (LEAD_FINDING, LEAD_CHALLENGE, *SOLUTION_SIDE["findings"], *PROBLEM_SIDE["findings"]):
        if fid not in findings:
            raise KeyError(f"page layout expects finding {fid}, which is not in review {review.review_id}")


def cited_sources(review, finding_ids=(), assumption_numbers=()) -> set[str]:
    findings = all_findings(review)
    out: set[str] = set()
    for fid in finding_ids:
        ev = findings[fid].evidence
        out |= {x.source_id for x in ev.supporting + ev.contradictory + ev.historical}
    for n in assumption_numbers:
        ev = assumption(review, n).evidence
        out |= {x.source_id for x in ev.supporting + ev.contradictory + ev.historical}
    return out


def shown_up_front(review) -> set[str]:
    """Finding ids rendered in the two-question panel, so the detail tab can
    list the rest without repeating them."""
    return set(PROBLEM_SIDE["findings"]) | set(SOLUTION_SIDE["findings"])


def numbers_in(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", text))
