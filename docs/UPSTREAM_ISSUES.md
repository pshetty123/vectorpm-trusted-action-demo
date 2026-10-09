# Upstream issues found while building the demo

Issues in the prototype code that this demo works around in its presentation layer. The demo
vendors the prototypes unmodified, so these are fixed upstream, then re-vendored with
`scripts/sync_vendor.py`.

## 1. Previous-decision rationale duplicates the decision text

**Where:** VectorPM Reservoir, `experiments/reservoir-decision-review/backend/app/synthesis/synthesizer.py`,
where `PreviousDecisionSummary` is built:

```python
PreviousDecisionSummary(
    decision_id=pd.decision_id,
    date=decision_date,
    decision=pd.summary,
    rationale_summary=pd.summary,   # same field as `decision`
    ...
)
```

**Effect:** in every stored review in the fixture (`REV-0d430e0d`, `REV-1b5d590c`, `REV-ac8bccc0`,
`REV-cfe57fb8`), `decision` and `rationale_summary` are identical for both DEC-014 and DEC-009. Any
UI that shows both prints each description twice.

**Demo workaround (presentation only):** `demo/context_brief.py::show_rationale` shows the
rationale only when it differs from the decision. The stored records are unchanged.
`tests/test_context_page.py::test_decision_history_shown_once_each` asserts both that the stored
fields are still identical and that the page shows each description once. When the upstream fix
lands and is re-vendored, that test's first assertion will fail, as a reminder to drop the
workaround.

**Suggested upstream fix:** have the Decision Analyst output (or the decision record source) carry
a distinct rationale, and map it to `rationale_summary`. Alternatively, make the field optional
and leave it empty when no separate rationale exists. Regenerating the stored reviews would change
the fixture hash, so the Trust Layer's `fixtures/MANIFEST.json` and this demo's
`vendor/VENDORED.json` would both need refreshing.

## 2. Overlapping missing-information entries

**Where:** the same synthesis step merges the Decision Analyst's and the Evidence Challenger's
missing-context lists without de-duplication.

**Effect:** `REV-0d430e0d` lists 11 gaps, several restating the same unknown: the DEC-014
2026-09-30 review outcome (gaps 1, 8, 10), the enterprise vs. SMB segment breakdown (5, 9),
revenue attribution (3, 7), and isolated client-visible error data (2, 10).

**Demo handling:** all 11 are shown exactly as stored. The top three are visible and the rest
are in an expandable list labelled "some overlap". Merging them would mean rewording evidence, so
the demo doesn't.

**Suggested upstream fix:** de-duplicate semantically at synthesis time, or keep the two lists
separate and tag each gap with which agent raised it.
