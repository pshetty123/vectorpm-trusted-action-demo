"""The refined Explore Context page must present the same evidence as the
stored review: every finding, strength, citation, excerpt, assumption,
decision, change and gap. Only layout and emphasis may differ."""
import html
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from demo import context_brief as cb

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def _plain(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


@pytest.fixture(scope="module")
def page():
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["page"] = "1 · Explore Context"
    at.run()
    assert not at.exception and not at.error
    return at


@pytest.fixture(scope="module")
def review(page):
    from demo import reservoir_view as rv
    return rv.load_review()


def _raw(at) -> str:
    return "\n".join(m.value for m in at.markdown) + "\n" + "\n".join(c.value for c in at.caption)


def _text(at) -> str:
    return _plain(_raw(at))


def _expander_text(at) -> str:
    return _plain("\n".join(m.value for ex in at.expander for m in ex.markdown)
                  + "\n".join(c.value for ex in at.expander for c in ex.caption))


def test_every_finding_is_fully_present_with_its_stored_strength(page, review):
    text, raw = _text(page), _raw(page)
    for f in cb.all_findings(review).values():
        assert _norm(f.statement) in text, f"{f.id}: original text missing"
        assert _norm(cb.headline(f)) in text, f"{f.id}: headline missing"
        # strength badge immediately followed by the finding's id chip
        assert re.search(rf">{f.strength.value}</span><span class=\"vp-chip \">{re.escape(f.id)}<", raw), f.id
        for x in f.evidence.supporting + f.evidence.contradictory + f.evidence.historical:
            assert x.source_id in text
            assert _norm(x.excerpt) in text, f"{f.id}: excerpt from {x.source_id} missing"


def test_detail_text_lives_in_expanders(page, review):
    inside = _expander_text(page)
    for f in cb.all_findings(review).values():
        assert _norm(f.statement) in inside, f"{f.id}: original text not in an expander"


def test_assumptions_keep_exact_text_status_and_citations(page, review):
    text = _text(page)
    for n, a in enumerate(review.assumptions, 1):
        assert _norm(a.assumption) in text
        assert f"assumption_{n}" in text and a.evidence_status in text
        for x in a.evidence.supporting + a.evidence.contradictory + a.evidence.historical:
            assert x.source_id in text
    assert "none cited" in text  # assumption_2 cites nothing, and the page says so


def test_decision_history_shown_once_each(page, review):
    text = _text(page)
    for d in review.previous_decisions:
        assert d.decision == d.rationale_summary  # the stored duplication this page works around
        assert text.count(_norm(d.decision)) == 1, d.decision_id
        assert d.decision_id in text
    assert "Context only · not an approval" in text


def test_missing_information_top_three_then_expandable(page, review):
    inside, everywhere = _expander_text(page), _text(page)
    gaps = [_norm(html.unescape(g)) for g in review.missing_context]
    for g in gaps:
        assert g in everywhere
    for g in gaps[:cb.TOP_GAPS]:
        assert g not in inside, "top gaps must be visible without expanding"
    for g in gaps[cb.TOP_GAPS:]:
        assert g in inside


def test_what_changed_and_freshness_still_presented(page, review):
    text = _text(page)
    for c in review.what_changed:
        assert _norm(c.change) in text
    assert "Context freshness" in text and "Sources in this packet" in [m.label for m in page.metric]


def test_decision_brief_is_backed_by_the_review(review):
    cb.validate_brief(review)
    corpus = " ".join([f.statement for f in cb.all_findings(review).values()]
                      + [a.assumption for a in review.assumptions] + review.missing_context
                      + [c.change for c in review.what_changed] + [d.decision for d in review.previous_decisions])
    available = cb.numbers_in(corpus)
    for item in cb.BRIEF:
        assert cb.numbers_in(item.text) <= available, f"{item.label}: number not found in the review"


def test_problem_and_solution_evidence_are_separated(page):
    text = _text(page)
    assert "Does the onboarding problem exist?" in text and "Would an AI assistant solve it?" in text
    q1 = text.index("Does the onboarding problem exist?")
    q2 = text.index("Would an AI assistant solve it?")
    problem_col, solution_col = text[q1:q2], text[q2:text.index("Most important unknown")]
    assert "problem_evidence" in problem_col and "solution_evidence" not in problem_col
    assert "solution_evidence" in solution_col and "problem_evidence" not in solution_col


def test_lead_items_come_first(page, review):
    text = _text(page)
    brief = text.index("Decision brief")
    finding = text.index("Most important finding")
    challenge = text.index("Most important challenge")
    unknown = text.index("Most important unknown")
    detail = text.index("Further challenges and strategic context")
    assert brief < finding < challenge < unknown < detail


def test_source_library_lab_and_navigation_kept(page):
    labels = [t.label for t in page.tabs]
    assert {"Full decision review", "Source library", "Evidence-strength lab"} <= set(labels)
    assert any(b.label == "Next: test agent autonomy →" for b in page.button)
    assert [m.value for m in page.metric if m.label == "Sources"] == ["14"]


def test_headlines_are_short_and_backed_by_their_finding(review):
    findings = cb.all_findings(review)
    assert set(cb.HEADLINES) <= set(findings)
    for fid, text in cb.HEADLINES.items():
        f = findings[fid]
        assert len(text) < len(f.statement), fid
        assert cb.numbers_in(text) <= cb.numbers_in(f.statement), f"{fid}: number not in the finding"
        cited = cb.cited_sources(review, (fid,))
        assert set(re.findall(r"FP-\d{3}", text)) <= cited | set(re.findall(r"FP-\d{3}", f.statement)), fid


def test_brief_sources_are_cited_by_its_findings(review):
    for item in cb.BRIEF:
        assert item.source_ids, item.label
        assert set(item.source_ids) <= cb.cited_sources(review, item.finding_ids, item.assumption_numbers)


def test_brief_shows_its_sources(page):
    text = _text(page)
    brief = text[text.index("Decision brief"):text.index("Two different questions")]
    for item in cb.BRIEF:
        assert _norm(item.text) in brief
        for sid in item.source_ids:
            assert sid in brief
