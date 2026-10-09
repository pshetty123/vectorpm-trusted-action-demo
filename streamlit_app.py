"""VectorPM: From Context to Trusted Action.

A presentation layer over two tested prototypes:
  * VectorPM Reservoir (evidence, provenance, freshness, evidence strength)
  * Trust & Control Layer (policy, integrity, autonomy evaluation, approval, audit)

Streamlit renders; the vendored prototype code decides. Each browser session
gets a private, in-memory Trust Layer instance. Everything is fictional and
every execution is simulated.

    streamlit run streamlit_app.py
"""
from __future__ import annotations

import json
from html import escape as e

import streamlit as st

from demo import context_brief as cb
from demo import presentation as pr
from demo import ui
from demo.engine import SCENARIO_KEYS, DemoSession, VendorIntegrityError, load_shared

st.set_page_config(page_title="VectorPM · From Context to Trusted Action", page_icon="🧭",
                   layout="wide", initial_sidebar_state="expanded")
ui.inject_css()

PAGES = ["Introduction", "1 · Explore Context", "2 · Test Agent Autonomy", "3 · Audit & Accountability"]


# ------------------------------------------------------------------ bootstrap
@st.cache_resource(show_spinner=False)
def shared_resources():
    return load_shared()


try:
    SHARED = shared_resources()
except VendorIntegrityError as exc:
    st.error(f"The demo stopped: vendored prototype code or data does not match the tested copy. ({exc})")
    st.stop()
except Exception as exc:  # fail closed: no partial or invented results
    st.error(f"The demo could not load its Reservoir or Trust Layer components, so it will not show results. "
             f"({type(exc).__name__}: {exc})")
    st.stop()

from demo import reservoir_view as rv  # noqa: E402  (needs the vendored import path set up above)


def session() -> DemoSession:
    if "demo" not in st.session_state:
        st.session_state.demo = DemoSession(SHARED)
    return st.session_state.demo


def reset_session() -> None:
    for k in list(st.session_state.keys()):
        if k != "page":
            del st.session_state[k]


def go(page: str) -> None:
    st.session_state.page = page


try:
    S = session()
except Exception as exc:
    st.error(f"Could not start your private demo session. No results are shown. ({type(exc).__name__}: {exc})")
    st.stop()
POLICY = SHARED.policy

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    ui.html('<div class="vp-brand">Vector<span>PM</span></div>'
            '<div class="vp-muted">From Context to Trusted Action</div>')
    st.write("")
    st.radio("Navigate", PAGES, key="page", label_visibility="collapsed")
    st.divider()
    n_events = len(S.audit_entries())
    ui.html(f'<div class="vp-muted">Your private session<br><b>{len(S.latest)}</b> scenarios evaluated · '
            f'<b>{n_events}</b> audit events</div>')
    st.button("Reset my session", on_click=reset_session, use_container_width=True,
              help="Clears your approvals, executions and audit history. Other visitors are unaffected.")
    st.divider()
    ui.html('<div class="vp-muted">Fictional data only. FlowPilot is a made-up company. Approver identities '
            'are simulated. Nothing is sent, written or executed for real.</div>')


# ------------------------------------------------------------------ page: introduction
def page_intro() -> None:
    ui.page_header("Build With Me · AI Product Edition", "From Context to Trusted Action",
                   "AI agents are increasingly capable of doing product work. Capability is not the hard part. "
                   "The hard part is knowing whether an agent has the right context, and whether it should be "
                   "allowed to act on it. This demo walks through that question in three steps.")
    ui.html("""
<div class="vp-flow">
  <div class="step"><div class="q">Can AI do the work?</div><h4>Agentic AI PM Team</h4>
    <p>Agents draft notes, analyse decisions, triage feedback and propose roadmap changes. Each proposal states
    what it wants to do, what it relies on, and how confident it claims to be.</p></div>
  <div class="arrow">→</div>
  <div class="step"><div class="q">Does it have the right context?</div><h4>VectorPM Reservoir</h4>
    <p>Institutional memory with provenance: which source said what, when, whether it is still current, how
    strong the evidence is, what contradicts it and what is missing.</p></div>
  <div class="arrow">→</div>
  <div class="step"><div class="q">Should it be allowed to act?</div><h4>Trust &amp; Control Layer</h4>
    <p>A deterministic policy engine sets autonomy per action from authority, risk, evidence and context
    integrity. Never from the agent's confidence. Every step is audited.</p></div>
</div>""")

    st.subheader("Four autonomy levels")
    cols = st.columns(4)
    for col, code in zip(cols, ("L0", "L1", "L2", "L3")):
        lv = pr.LEVELS[code]
        with col:
            ui.html(f'<div class="vp-level {lv["css"]}"><span class="code">{code}</span>'
                    f'<span class="name">{e(lv["name"])}</span><p>{e(lv["summary"])}</p>'
                    f'<p class="vp-muted">Can execute: {e(lv["can_execute"])}</p></div>')
    ui.callout("<b>How the level is chosen.</b> Every policy dimension that applies sets a ceiling: authority, "
               "risk, evidence strength, contradictions, unverified assumptions, freshness, context integrity. "
               "The final level is the lowest ceiling. An agent saying it is 96% sure changes nothing.", "teal")

    st.subheader("How to explore (5–7 minutes)")
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.card("1 · Explore Context", "<p>Browse the fictional FlowPilot evidence: sources, freshness, evidence "
                "strength, contradictions, gaps and past decisions.</p>")
    with c2:
        ui.card("2 · Test Agent Autonomy", "<p>Run six agent proposals through the real policy engine. Try to "
                "execute, approve and override, and watch what gets refused.</p>")
    with c3:
        ui.card("3 · Audit & Accountability", "<p>See every evaluation, approval attempt, refusal and simulated "
                "execution from your session, in a hash-chained log.</p>")
    st.button("Start with Explore Context →", type="primary", on_click=go, args=(PAGES[1],))
    ui.footer()


# ------------------------------------------------------------------ page: explore context
def _source_chips(ids, kind: str = "") -> str:
    return "".join(ui.chip(i, kind) for i in ids) or '<span class="vp-muted">none</span>'


def _strength(value: str) -> str:
    return ui.badge(value, pr.STRENGTH_CSS.get(value, "muted"), "Reservoir evidence-strength rating for this finding")


def _citations(f) -> str:
    sup = [x.source_id for x in f.evidence.supporting]
    con = [x.source_id for x in f.evidence.contradictory]
    hist = [x.source_id for x in f.evidence.historical]
    return (f'<p>Supporting: {_source_chips(sup)}</p>'
            + (f'<p>Contradicting: {_source_chips(con, "bad")}</p>' if con else "")
            + (f'<p>Historical: {_source_chips(hist)}</p>' if hist else ""))


def _excerpts(f) -> None:
    for kind, items in (("Supporting", f.evidence.supporting), ("Contradicting", f.evidence.contradictory),
                        ("Historical", f.evidence.historical)):
        for x in items:
            ui.html(f'<p><b>{e(kind)}</b> · {ui.chip(x.source_id)} {e(x.title)} · {e(x.date.isoformat())} '
                    f'{ui.badge(x.status.value, pr.STATUS_CSS.get(x.status.value, "muted"))}</p>')
            st.caption(x.excerpt)


def _finding_block(f, title: str | None = None) -> None:
    """Readable finding card: a short headline up front, the stored statement
    verbatim in an expander, then the source excerpts."""
    parts = cb.split_challenge(f.statement)
    head = f'<p>{_strength(f.strength.value)}{ui.chip(f.id)}</p>'
    if title:
        head = f'<h4>{e(title)}</h4>' + head
    origin = (f'<p class="vp-muted">Challenger tested {e(cb.challenge_target_label(parts.target))}</p>'
              if parts else "")
    ui.html(f'<div class="vp-card">{head}{origin}<p class="vp-strong">{e(cb.headline(f))}</p>'
            f'{_citations(f)}</div>')
    with st.expander(f"Original {'Challenger' if parts else 'analyst'} finding · {f.id}"):
        ui.html(f'<p class="vp-verbatim">{e(f.statement)}</p>')
    with st.expander(f"Source excerpts · {f.id}"):
        _excerpts(f)


def _assumption_block(review, n: int) -> None:
    a = cb.assumption(review, n)
    cited = [x.source_id for x in a.evidence.supporting + a.evidence.contradictory + a.evidence.historical]
    status = a.evidence_status
    ui.html(f'<div class="vp-card"><p>{ui.badge(cb.ASSUMPTION_LABEL.get(status, status), pr.ASSUMPTION_CSS.get(status, "muted"), status)}'
            f'{ui.chip(f"assumption_{n}")}{ui.badge(status, "muted")}</p>'
            f'<p class="vp-muted">Assumes:</p><p class="vp-strong">{e(a.assumption)}</p>'
            f'<p>Cited sources: {_source_chips(cited) if cited else "<span class=vp-muted>none cited</span>"}</p></div>')


def _decision_brief(review, findings: dict) -> None:
    items = ""
    for it in cb.BRIEF:
        refs = "".join(_strength(findings[fid].strength.value) + ui.chip(fid) for fid in it.finding_ids)
        refs += "".join(ui.badge(cb.assumption(review, n).evidence_status,
                                 pr.ASSUMPTION_CSS.get(cb.assumption(review, n).evidence_status, "muted"))
                        + ui.chip(f"assumption_{n}") for n in it.assumption_numbers)
        refs += "".join(ui.chip(f"gap {g + 1}", "warn") for g in it.gap_indexes)
        if it.source_ids:
            refs += '<span class="vp-muted"> · sources </span>' + _source_chips(it.source_ids)
        items += (f'<div class="vp-brief-row"><div class="vp-brief-label">{e(it.label)}</div>'
                  f'<div><div>{e(it.text)}</div><div class="vp-brief-refs">Based on {refs}</div></div></div>')
    ui.html(f'<div class="vp-brief"><div class="vp-eyebrow">Decision brief</div>'
            f'<h3>{e(review.proposed_decision)}</h3><p class="vp-brief-headline">{e(cb.BRIEF_HEADLINE)}</p>'
            f'{items}<p class="vp-muted vp-brief-note">Summary written for this demo. Every claim links to the '
            f'stored review below; strengths are the Reservoir\'s own ratings, not new scores.</p></div>')


def page_context() -> None:
    ui.page_header("Section 1 · VectorPM Reservoir", "Explore Context",
                   "Before an agent acts, it needs more than relevant text. It needs to know which sources are "
                   "current, how strong the evidence is, what contradicts it and what nobody knows yet. This is "
                   "the fictional FlowPilot Reservoir that every agent proposal in Section 2 draws on.")

    sources = rv.list_sources()
    by_id = {s.source_id: s for s in sources}
    review = rv.load_review()
    packet = S.shared.adapter.packet_from_review(rv.PRIMARY_REVIEW_ID)
    fr = packet.body.freshness
    findings = cb.all_findings(review)
    try:
        cb.validate_brief(review)
    except KeyError as exc:  # never show a summary the data doesn't back
        st.error(f"The decision brief doesn't match the stored review, so it is not shown. ({exc})")
        st.stop()

    _decision_brief(review, findings)

    # --- the two questions, kept apart
    st.markdown("### Two different questions")
    ui.html('<p class="vp-muted">Evidence that a problem exists is not evidence that a particular solution will '
            'fix it. Strength badges rate how well each finding is supported, not whether the idea is good.</p>')
    left, right = st.columns(2)
    with left:
        ui.html('<div class="vp-q">Does the onboarding problem exist?</div>')
        for fid in cb.PROBLEM_SIDE["findings"]:
            _finding_block(findings[fid], "Most important finding" if fid == cb.LEAD_FINDING else None)
        for n in cb.PROBLEM_SIDE["assumptions"]:
            _assumption_block(review, n)
    with right:
        ui.html('<div class="vp-q">Would an AI assistant solve it?</div>')
        for fid in cb.SOLUTION_SIDE["findings"]:
            _finding_block(findings[fid], "Most important challenge" if fid == cb.LEAD_CHALLENGE else
                           "Closest evidence in favour")
        for n in cb.SOLUTION_SIDE["assumptions"]:
            _assumption_block(review, n)

    gap = review.missing_context[cb.LEAD_UNKNOWN_INDEX]
    ui.html(f'<div class="vp-card vp-unknown"><h4>Most important unknown</h4>'
            f'<p class="vp-strong">{e(gap)}</p></div>')

    ui.callout("<b>Decision records are context, not approvals.</b> The Reservoir stores past decisions such as "
               "DEC-014 as historical records. They explain what was decided and why, but nobody's sign-off is "
               "authenticated in them. The Trust Layer marks every prior decision <i>unverified</i> and never "
               "treats it as permission to act.", "warn")

    tab_review, tab_sources, tab_lab = st.tabs(["Full decision review", "Source library", "Evidence-strength lab"])

    # --- full decision review: everything not already shown above
    with tab_review:
        ui.html(f'<div class="vp-muted">Stored review <span class="vp-chip">{e(review.review_id)}</span> · '
                f'created {e(review.created_at.date().isoformat())} · overall evidence strength '
                f'{_strength(review.overall_evidence_strength.value)}</div>')

        upfront = cb.shown_up_front(review)
        st.markdown("#### Further challenges and strategic context")
        for sec in ("what_we_know", "what_challenges", "strategic_context"):
            for f in getattr(review, sec):
                if f.id not in upfront:
                    _finding_block(f)

        shown = set(cb.PROBLEM_SIDE["assumptions"]) | set(cb.SOLUTION_SIDE["assumptions"])
        rest = [n for n in range(1, len(review.assumptions) + 1) if n not in shown]
        if rest:
            st.markdown("#### Other assumptions")
            for n in rest:
                _assumption_block(review, n)

        st.markdown("#### Decision history")
        for d in review.previous_decisions:
            cited = [x.source_id for x in d.evidence.supporting + d.evidence.historical]
            rationale = f'<p>{e(d.rationale_summary)}</p>' if cb.show_rationale(d) else ""
            ui.html(f'<div class="vp-card"><p>{ui.chip(d.decision_id)}{ui.badge(d.date.isoformat(), "muted")}'
                    f'{ui.badge("Context only · not an approval", "warn")}</p>'
                    f'<p class="vp-strong">{e(d.decision)}</p>{rationale}'
                    f'<p>Source: {_source_chips(cited)}</p></div>')

        if review.what_changed:
            with st.expander(f"What changed since earlier decisions ({len(review.what_changed)})"):
                for c in review.what_changed:
                    cited = [x.source_id for x in c.evidence.supporting + c.evidence.contradictory
                             + c.evidence.historical]
                    ui.html(f'<p>{e(c.change)}</p><p>{_source_chips(cited)}</p>')

        st.markdown("#### Missing information")
        ui.html('<p class="vp-muted">Gaps the Reservoir found and refused to fill in. An agent relying on any of '
                'these is relying on something nobody has evidence for.</p>')
        for i, g in enumerate(review.missing_context[:cb.TOP_GAPS], 1):
            ui.html(f'<p>{ui.chip(f"gap {i}", "warn")} {e(g)}</p>')
        if len(review.missing_context) > cb.TOP_GAPS:
            with st.expander(f"{len(review.missing_context) - cb.TOP_GAPS} more gaps (some overlap; listed as "
                             f"the review recorded them)"):
                for i, g in enumerate(review.missing_context[cb.TOP_GAPS:], cb.TOP_GAPS + 1):
                    ui.html(f'<p>{ui.chip(f"gap {i}", "warn")} {e(g)}</p>')

        st.markdown("#### Context freshness")
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Assessed as of", fr.as_of.isoformat())
        f2.metric("Newest source", f"{fr.newest_source_age_days} days old")
        f3.metric("Oldest source", f"{fr.oldest_source_age_days} days old")
        f4.metric("Sources in this packet", len(packet.body.sources))
        ui.html(f'<p class="vp-muted">Superseded sources in this packet: {_source_chips(fr.superseded_ids, "bad")} '
                f'· Stale: {_source_chips(fr.stale_ids, "warn")}</p>')

    # --- source library
    with tab_sources:
        m = st.columns(5)
        counts = {k: sum(1 for s in sources if s.status == k) for k in ("current", "historical", "stale", "superseded")}
        m[0].metric("Sources", len(sources))
        m[1].metric("Current", counts["current"])
        m[2].metric("Historical", counts["historical"])
        m[3].metric("Stale", counts["stale"])
        m[4].metric("Superseded", counts["superseded"])
        statuses = st.multiselect("Show status", ["current", "historical", "stale", "superseded"],
                                  default=["current", "historical", "stale", "superseded"])
        for s in sources:
            if s.status not in statuses:
                continue
            sup = f' · superseded by {ui.chip(s.superseded_by)}' if s.superseded_by else ""
            ui.html(f'<div class="vp-card"><p>{ui.chip(s.source_id)}'
                    f'{ui.badge(s.status, pr.STATUS_CSS.get(s.status, "muted"), pr.STATUS_HELP.get(s.status))}'
                    f'{ui.badge(pr.SOURCE_TYPE_LABEL.get(s.source_type, s.source_type), "muted")}</p>'
                    f'<p class="vp-strong">{e(s.title)}</p>'
                    f'<p>{e(s.created_at.isoformat())} · {s.age_days} days old · '
                    f'reference <span class="vp-chip">{e(s.source_reference)}</span>{sup}</p></div>')
            with st.expander(f"Read {s.source_id}"):
                if s.status in ("stale", "superseded"):
                    st.warning(pr.STATUS_HELP[s.status])
                st.markdown(s.content)

    # --- evidence-strength lab
    with tab_lab:
        ui.html('<p class="vp-lede">Evidence strength is computed by a deterministic rule, not by asking a model '
                'how confident it feels. Pick supporting sources and a challenger verdict, and the Reservoir\'s '
                'own scoring function rates them.</p>')
        c1, c2 = st.columns([3, 2])
        with c1:
            chosen = st.multiselect("Supporting sources", [s.source_id for s in sources], default=["FP-009"],
                                    format_func=lambda i: f"{i} · {by_id[i].title[:60]}")
        with c2:
            verdict = st.selectbox("Challenger verdict", ["(none)"] + rv.challenger_verdicts())
        try:
            strength = rv.compute_strength(chosen, None if verdict == "(none)" else verdict)
            ui.html("Result: " + ui.badge(strength, pr.STRENGTH_CSS.get(strength, "muted")))
        except Exception as exc:
            st.error(f"The strength function failed, so no rating is shown. ({exc})")
        with st.expander("How the score works"):
            st.markdown(
                "- **Source count** 0 / 1 / 2 / 3+ sources → 0 / 1 / 2 / 3\n"
                "- **Type diversity** 1 / 2 / 3+ distinct source types → 0 / 1 / 2\n"
                "- **Freshness** freshest non-stale source ≤90 / ≤180 / older days → 2 / 1 / 0\n"
                "- **Challenger** CONTRADICTED −2 · WEAK_EVIDENCE −1\n"
                "- **Stakeholder-only cap** if every source is stakeholder opinion (e.g. the sales debrief "
                "FP-009), the result is capped at LOW: opinion is not customer evidence.\n\n"
                "Total ≤0 or no sources → INSUFFICIENT · 1–2 → LOW · 3–4 → MEDIUM · 5+ → HIGH "
                "(MEDIUM if challenged).")
        ui.callout("Try it: <b>FP-009</b> alone is LOW (stakeholder opinion only). Add <b>FP-007</b> and "
                   "<b>FP-003</b> and it rises. Set the verdict to CONTRADICTED and watch it fall.", "teal")

    st.button("Next: test agent autonomy →", type="primary", on_click=go, args=(PAGES[2],))
    ui.footer()


# ------------------------------------------------------------------ page: test autonomy
def _flash(key: str, kind: str, text: str) -> None:
    st.session_state.setdefault("flash", {})[key] = (kind, text)


def _run(key: str, fn, success: str | None = None) -> None:
    """Call the Trust Layer and record the visible outcome. Refusals are expected
    and shown as such; any other failure is shown as an error, never as a result."""
    from trust_layer.service import TrustError
    try:
        fn()
        if success:
            _flash(key, "success", success)
    except TrustError as exc:
        _flash(key, "refused", f"Refused · {exc.code}. {pr.REFUSAL_TEXT.get(exc.code, str(exc))}")
    except Exception as exc:
        _flash(key, "error", f"A component failed, so no result is shown. ({type(exc).__name__}: {exc})")


def cb_evaluate(key: str) -> None:
    conf = st.session_state.get(f"conf_{key}")
    st.session_state.get("flash", {}).pop(key, None)
    _run(key, lambda: S.evaluate(key, None if conf is None else conf / 100))


def cb_execute(key: str) -> None:
    row = S.current(key)
    _run(key, lambda: S.execute(row["evaluation_id"], requested_by=row["proposal"].proposer_id),
         "Simulated execution completed. Nothing outside this page was touched.")


def cb_decide(key: str, approve: bool) -> None:
    row = S.current(key)
    who = st.session_state.get(f"approver_{key}")
    fn = S.approve if approve else S.reject
    _run(key, lambda: fn(row["evaluation_id"], who, note="demo"),
         f"{pr.principal_label(POLICY, who)} {'approved' if approve else 'rejected'} the action.")


def select_scenario(key: str) -> None:
    st.session_state.scenario = key


def _render_proposal(sc: dict, key: str) -> None:
    p = sc["proposal"]
    copy = pr.SCENARIO_COPY[key]
    st.markdown(f"### {key} · {copy['headline']}")
    ui.html(f'<p class="vp-muted">{e(sc["why"])}</p>')
    ui.callout(f"<b>Try this.</b> {e(copy['try'])}", "teal")

    c1, c2 = st.columns(2)
    with c1:
        ui.card("Proposed action",
                f'<p class="vp-strong">{e(p.summary)}</p>'
                f'<p>Agent: <b>{e(pr.principal_label(POLICY, p.proposer_id))}</b></p>'
                f'<p>Action: {e(pr.ACTION_LABEL.get(p.action_type, p.action_type))} {ui.chip(p.action_type)}</p>'
                f'<p>Target: {e(p.target)}</p>')
    with c2:
        spec = POLICY.action(p.action_type)
        risk = ""
        if spec:
            risk = (ui.badge(spec.scope, "warn" if spec.scope == "external" else "muted")
                    + ui.badge("reversible" if spec.reversible else "irreversible", "muted" if spec.reversible else "warn")
                    + ui.badge(f"{spec.risk} risk", "muted" if spec.risk == "low" else "warn")
                    + (ui.badge("customer-facing", "bad") if spec.customer_facing else ""))
        perms = sorted(POLICY.permissions(p.proposer_id, p.action_type)) or ["none"]
        prohibited = POLICY.prohibition_for(p.proposer_id, p.action_type)
        ui.card("Authority and risk profile (from policy)",
                f'<p>Registry: {risk or ui.badge("not registered", "bad")}</p>'
                f'<p>Agent grants: {"".join(ui.chip(x) for x in perms)}</p>'
                + (f'<p>{ui.badge("Explicit prohibition", "bad")} {e(prohibited.reason)}</p>' if prohibited else ""))

    st.slider("Agent's reported confidence (%)", 0, 100, int(round(p.claimed_confidence * 100)), key=f"conf_{key}",
              help="Recorded in the audit log. The policy engine never reads it.")

    # Context packet and evidence the agent relies on.
    pk = p.context_packet
    st.markdown("#### Context the agent relies on")
    ui.html(f'<p class="vp-muted">Context packet {ui.chip(pk.packet_id[:18] + "…")} · origin '
            f'{e(pk.body.origin.get("kind", "?"))} · {len(pk.body.sources)} source{"s" if len(pk.body.sources) != 1 else ""} · '
            f'as of {e(pk.body.freshness.as_of.isoformat())}</p>')
    limitations = []
    for ref in p.relies_on:
        f, a = pk.finding(ref), pk.assumption(ref)
        if f:
            src_badges = ""
            for sid in f.supporting_ids:
                s = pk.source(sid)
                st_ = s.status if s else "missing"
                src_badges += ui.chip(sid, "bad" if st_ == "superseded" else "warn" if st_ == "stale" else "")
                if st_ in ("stale", "superseded"):
                    limitations.append(f"{sid} is {st_}" + (f" (replaced by {s.superseded_by})" if s and s.superseded_by else ""))
            if f.contradictory_ids:
                limitations.append(f"{f.finding_id} is contradicted by {', '.join(f.contradictory_ids)}")
            if f.strength in ("LOW", "INSUFFICIENT"):
                limitations.append(f"{f.finding_id} evidence is {f.strength}")
            ui.html(f'<div class="vp-card"><p>{ui.chip(f.finding_id)}'
                    f'{ui.badge(f.strength, pr.STRENGTH_CSS.get(f.strength, "muted"))}</p>'
                    f'<p class="vp-strong">{e(f.statement)}</p><p>Supporting: {src_badges}</p>'
                    + (f'<p>Contradicting: {_source_chips(f.contradictory_ids, "bad")}</p>' if f.contradictory_ids else "")
                    + "</div>")
        elif a:
            if a.evidence_status != "SUPPORTED":
                limitations.append(f"{a.assumption_id} is {a.evidence_status}")
            ui.html(f'<div class="vp-card"><p>{ui.chip(a.assumption_id)}'
                    f'{ui.badge(a.evidence_status, pr.ASSUMPTION_CSS.get(a.evidence_status, "muted"))}</p>'
                    f'<p class="vp-strong">Assumption: {e(a.assumption)}</p></div>')
        else:
            limitations.append(f"{ref} is not in the context packet")
    if not p.relies_on:
        ui.html('<p class="vp-muted">This proposal cites no evidence.</p>')
    if limitations:
        ui.html("<p><b>Evidence limitations visible in the packet:</b></p>"
                + "".join(f"<p class='vp-muted'>• {e(x)}</p>" for x in limitations))
    if key == "E":
        ui.callout("<b>What the packet claims vs. what the Reservoir holds.</b> This packet says FP-002 is "
                   "<i>current</i> and rates the finding HIGH. Its hash is self-consistent, so a naive check "
                   "passes. Press Evaluate to see what happens when the Trust Layer re-derives it.", "warn")
    with st.expander("Technical detail: raw proposal"):
        st.json(json.loads(p.model_dump_json()), expanded=False)


def _render_decision(row: dict, key: str) -> None:
    d = row["decision"]
    code = pr.level_key(d.level)
    lv = pr.LEVELS[code]
    st.markdown("#### Trust Layer decision")
    ui.level_banner(code, lv["name"], " · ".join(pr.reason_text(r) for r in d.reasons))
    ui.html("Binding reason codes: " + "".join(ui.badge(r.value, "muted") for r in d.reasons)
            + f'<br><span class="vp-muted">Reported confidence {d.claimed_confidence:.0%} · used by policy: '
              f'<b>{"yes" if d.confidence_used else "no"}</b> · policy {e(d.policy_version)}</span>')
    st.write("")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("##### Authority, policy and risk checks")
        rows_html = ""
        for r in pr.dimension_rows(d):
            if r["level"] is None:
                items = f'<div class="item">{ui.lvl(None)} {e(r["ok_text"])}</div>'
            else:
                items = "".join(f'<div class="item">{ui.lvl(il)} <b>{e(code_)}</b> · {e(text)}'
                                + (f'<div class="detail">{e(detail)}</div>' if detail else "") + "</div>"
                                for code_, text, detail, il in r["items"])
            rows_html += (f'<div class="vp-check"><div><div class="dim">{e(r["label"])}</div>'
                          f'<div class="q">{e(r["question"])}</div></div><div>{items}</div></div>')
        ui.html(f'<div class="vp-card">{rows_html}</div>')
        ui.html('<p class="vp-muted">The level is the lowest ceiling across all checks. Items at the final level '
                'are the binding reasons.</p>')
    with c2:
        st.markdown("##### Status")
        ui.card(pr.STATE_LABEL.get(row["state"], row["state"]), f'<p>{e(pr.next_action(row, POLICY))}</p>')
        if not d.integrity_ok:
            st.markdown("##### Integrity failures")
            for err in d.integrity_errors:
                ui.html(f'<p class="vp-muted">• {e(err)}</p>')
        if row["approval"]:
            ap = row["approval"]
            ui.card("Approval", f'<p>{e(ap["decision"].title())} by {e(pr.principal_label(POLICY, ap["approver_id"]))}</p>'
                                f'<p>{e(ap["at"][:19].replace("T", " "))} UTC</p>')
        if row["outcome"]:
            eff = row["outcome"]["effect"]
            body = "".join(f'<p><b>{e(k.replace("_", " "))}:</b> {e(str(v))}</p>' for k, v in eff.items())
            ui.card("Simulated outcome", body + f'<p class="vp-muted">{e(row["outcome"]["note"])}</p>')


def _render_actions(row: dict, key: str) -> None:
    st.markdown("#### Try to act")
    state = row["state"]
    proposer = row["proposal"].proposer_id
    c1, c2 = st.columns([1, 2])
    with c1:
        st.button("Execute (simulated)", key=f"exec_{key}", on_click=cb_execute, args=(key,),
                  type="primary" if state in ("READY", "APPROVED") else "secondary", use_container_width=True,
                  help="Asks the Trust Layer to run the simulated executor. Refusals are audited too.")
    with c2:
        if state == "PENDING_APPROVAL":
            options = ["human.ana-ortiz", "human.sam-reyes", proposer]
            st.selectbox("Approve as (simulated identity)", options, key=f"approver_{key}",
                         format_func=lambda pid: pr.principal_label(POLICY, pid)
                         + ("  (the proposing agent)" if pid == proposer else ""))
            a1, a2 = st.columns(2)
            a1.button("Approve", key=f"approve_{key}", on_click=cb_decide, args=(key, True), use_container_width=True)
            a2.button("Reject", key=f"reject_{key}", on_click=cb_decide, args=(key, False), use_container_width=True)
        elif state == "BLOCKED":
            ui.html('<p class="vp-muted">No approval path exists for a blocked action. Not even a human approver '
                    'can unlock it here.</p>')
        elif state in ("APPROVED", "REJECTED", "EXECUTED") and row["approval"]:
            ui.html('<p class="vp-muted">The approval decision is recorded. It cannot be changed or repeated; '
                    'evaluate again to start a new proposal.</p>')
        elif state == "RECOMMENDATION":
            ui.html('<p class="vp-muted">Recommendations have no approval path to execution: a human takes the '
                    'action outside the agent.</p>')

    flash = st.session_state.get("flash", {}).get(key)
    if flash:
        kind, text = flash
        {"success": st.success, "refused": st.warning, "error": st.error}[kind](text)


def page_autonomy() -> None:
    ui.page_header("Section 2 · Trust & Control Layer", "Test Agent Autonomy",
                   "Six agent proposals, each evaluated by the real Trust Layer policy engine against the same "
                   "Reservoir context you just explored. Evaluate them, try to execute them, try to approve them "
                   "as the wrong person, and see what the Trust Layer allows.")
    st.session_state.setdefault("scenario", "A")
    cols = st.columns(6)
    for col, k in zip(cols, SCENARIO_KEYS):
        done = S.current(k)
        tag = f" · {pr.level_key(done['decision'].level)}" if done else ""
        col.button(f"{k} · {pr.SCENARIO_COPY[k]['short']}{tag}", key=f"pick_{k}", on_click=select_scenario,
                   args=(k,), type="primary" if st.session_state.scenario == k else "secondary",
                   use_container_width=True)
    key = st.session_state.scenario
    sc = S.scenarios[key]
    st.divider()
    _render_proposal(sc, key)

    st.button("Evaluate proposal", key=f"eval_{key}", type="primary", on_click=cb_evaluate, args=(key,))
    row = S.current(key)
    if row is None:
        flash = st.session_state.get("flash", {}).get(key)
        if flash:
            {"success": st.success, "refused": st.warning, "error": st.error}[flash[0]](flash[1])
        ui.html('<p class="vp-muted">Not evaluated yet in your session.</p>')
    else:
        _render_decision(row, key)
        _render_actions(row, key)
    st.button("Next: audit & accountability →", on_click=go, args=(PAGES[3],))
    ui.footer()


# ------------------------------------------------------------------ page: audit
def page_audit() -> None:
    ui.page_header("Section 3 · Accountability", "Audit & Accountability",
                   "Autonomy is only trustworthy if every decision can be reconstructed later: what the agent "
                   "proposed, what evidence it cited, which rule decided, who approved, and what ran. This is "
                   "your session's log. Nobody else can see it, and it disappears when you leave.")
    entries = S.audit_entries()
    chain = S.audit_chain()
    evals = [x for x in entries if x["event_type"] == "EVALUATED"]
    m = st.columns(6)
    m[0].metric("Evaluations", len(evals))
    m[1].metric("Blocked (L0)", sum(1 for x in evals if x["payload"]["decision"]["level"] == "L0"))
    m[2].metric("Approvals", sum(1 for x in entries if x["event_type"] in ("APPROVED", "REJECTED")))
    m[3].metric("Approval refusals", sum(1 for x in entries if x["event_type"] == "APPROVAL_DENIED"))
    m[4].metric("Simulated executions", sum(1 for x in entries if x["event_type"] == "EXECUTED_SIMULATED"))
    m[5].metric("Execution refusals", sum(1 for x in entries if x["event_type"] == "EXECUTION_REFUSED"))

    if chain.ok:
        ui.html(ui.badge(f"Hash chain intact · {chain.entries} entries", "ok")
                + '<span class="vp-muted"> Each entry\'s hash covers the previous one, so an edited or missing '
                  'entry breaks the chain.</span>')
    else:
        st.error(f"Audit chain verification failed at entry {chain.first_bad_seq}: {chain.detail}")

    if not entries:
        ui.callout("No activity yet. Evaluate a scenario in Section 2 and come back.", "teal")
    else:
        kinds = st.multiselect("Event types", list(pr.EVENT_LABEL), default=list(pr.EVENT_LABEL),
                               format_func=lambda k: pr.EVENT_LABEL[k][0])
        for x in reversed(entries):
            if x["event_type"] not in kinds:
                continue
            label, css = pr.EVENT_LABEL.get(x["event_type"], (x["event_type"], "muted"))
            refs = ""
            if x["event_type"] == "EVALUATED":
                ev = x["payload"]["evidence"]
                ids = [r["id"] for r in ev["relies_on"]]
                refs = (f'<div class="meta">context {e(ev["packet_id"][:18])}… · relies on '
                        f'{e(", ".join(ids) or "nothing")} · integrity {"ok" if ev["integrity_ok"] else "FAILED"}</div>')
            ui.html(f'<div class="vp-event"><div class="meta">#{x["seq"]} · {e(x["recorded_at"][11:19])} UTC · '
                    f'{e(x["evaluation_id"] or "")} · hash {e(x["entry_hash"][:10])}…</div>'
                    f'<div class="body">{ui.badge(label, css)} {e(pr.describe_event(x, POLICY))}</div>{refs}</div>')
        with st.expander("Technical detail: raw audit entries"):
            st.json(entries, expanded=False)
        st.download_button("Download my session audit (JSON)", json.dumps(entries, indent=2, default=str),
                           file_name="vectorpm-demo-audit.json", mime="application/json")

    st.markdown("#### Why this matters")
    c1, c2 = st.columns(2)
    with c1:
        ui.card("What this demo shows", "<p>Every evaluation, approval attempt, refusal and simulated execution is "
                "an append-only, hash-chained entry recording the action, the cited evidence, the context packet, "
                "the policy version and the binding reason codes. Refusals are first-class events, not silent "
                "failures.</p>")
    with c2:
        ui.card("What production would also need", "<p>Authenticated identities (here they are simulated and "
                "selectable), durable tamper-evident storage with the chain head anchored externally, retention "
                "and access controls, clock integrity, and independent review. This session log lives in memory "
                "and is discarded when you leave.</p>")
    ui.footer()


{PAGES[0]: page_intro, PAGES[1]: page_context, PAGES[2]: page_autonomy, PAGES[3]: page_audit}[
    st.session_state.get("page", PAGES[0])]()
