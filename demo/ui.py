"""Reusable Streamlit UI components. Every dynamic string is HTML-escaped before
it is placed inside custom markup."""
from __future__ import annotations

from html import escape as e

import streamlit as st

CSS = """
<style>
:root {
  --navy: #0B1220; --charcoal: #141A26; --panel: #182033; --line: #26314A;
  --text: #E6EAF2; --muted: #9AA6BD; --teal: #2DD4BF; --indigo: #818CF8;
  --ok: #34D399; --info: #60A5FA; --warn: #FBBF24; --bad: #F87171;
  --l0: #F87171; --l1: #FBBF24; --l2: #818CF8; --l3: #2DD4BF;
}
.block-container { padding-top: 3.6rem; max-width: 1180px; }
h1, h2, h3 { letter-spacing: -0.01em; }
.vp-eyebrow { color: var(--teal); font-size: .78rem; font-weight: 600; letter-spacing: .12em;
  text-transform: uppercase; margin-bottom: .25rem; }
.vp-lede { color: var(--muted); font-size: 1.05rem; line-height: 1.55; max-width: 780px; }
.vp-card { background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
  padding: 1rem 1.1rem; margin-bottom: .75rem; }
.vp-card h4 { margin: 0 0 .35rem 0; font-size: 1rem; }
.vp-card p { margin: .2rem 0; color: var(--muted); font-size: .92rem; line-height: 1.5; }
.vp-card .vp-strong { color: var(--text); }
.vp-callout { border-left: 3px solid var(--indigo); background: rgba(129,140,248,.08);
  padding: .8rem 1rem; border-radius: 0 10px 10px 0; margin: .6rem 0 1rem 0; font-size: .93rem; }
.vp-callout.teal { border-color: var(--teal); background: rgba(45,212,191,.07); }
.vp-callout.warn { border-color: var(--warn); background: rgba(251,191,36,.07); }
.vp-badge { display: inline-block; padding: .1rem .5rem; border-radius: 999px; font-size: .74rem;
  font-weight: 600; letter-spacing: .02em; border: 1px solid; margin: 0 .25rem .2rem 0; white-space: nowrap; }
.vp-badge.ok { color: var(--ok); border-color: rgba(52,211,153,.45); background: rgba(52,211,153,.08); }
.vp-badge.info { color: var(--info); border-color: rgba(96,165,250,.45); background: rgba(96,165,250,.08); }
.vp-badge.warn { color: var(--warn); border-color: rgba(251,191,36,.45); background: rgba(251,191,36,.08); }
.vp-badge.bad { color: var(--bad); border-color: rgba(248,113,113,.45); background: rgba(248,113,113,.08); }
.vp-badge.muted { color: var(--muted); border-color: var(--line); background: transparent; }
.vp-chip { display: inline-block; font-family: ui-monospace, Menlo, monospace; font-size: .76rem;
  padding: .05rem .4rem; border-radius: 6px; background: #0F172A; border: 1px solid var(--line);
  color: var(--text); margin: 0 .2rem .2rem 0; }
.vp-chip.bad { border-color: rgba(248,113,113,.5); }
.vp-chip.warn { border-color: rgba(251,191,36,.5); }
.vp-level { border-radius: 14px; padding: 1rem 1.2rem; border: 1px solid; margin-bottom: .8rem; }
.vp-level .code { font-size: 2rem; font-weight: 800; line-height: 1; }
.vp-level .name { font-size: 1.15rem; font-weight: 700; margin-left: .5rem; }
.vp-level p { margin: .5rem 0 0 0; color: var(--text); font-size: .93rem; }
.vp-level.l0 { border-color: var(--l0); background: rgba(248,113,113,.08); } .vp-level.l0 .code { color: var(--l0); }
.vp-level.l1 { border-color: var(--l1); background: rgba(251,191,36,.07); } .vp-level.l1 .code { color: var(--l1); }
.vp-level.l2 { border-color: var(--l2); background: rgba(129,140,248,.09); } .vp-level.l2 .code { color: var(--l2); }
.vp-level.l3 { border-color: var(--l3); background: rgba(45,212,191,.08); } .vp-level.l3 .code { color: var(--l3); }
.vp-lvl { display: inline-block; min-width: 2.1rem; text-align: center; font-weight: 800; font-size: .78rem;
  border-radius: 6px; padding: .05rem .35rem; margin-right: .35rem; color: #0B1220; }
.vp-lvl.l0 { background: var(--l0); } .vp-lvl.l1 { background: var(--l1); }
.vp-lvl.l2 { background: var(--l2); } .vp-lvl.l3 { background: var(--l3); }
.vp-lvl.none { background: transparent; color: var(--ok); border: 1px solid rgba(52,211,153,.45); }
.vp-flow { display: flex; gap: .6rem; align-items: stretch; flex-wrap: wrap; margin: .6rem 0 1rem 0; }
.vp-flow .step { flex: 1 1 210px; background: var(--panel); border: 1px solid var(--line);
  border-radius: 12px; padding: .9rem 1rem; }
.vp-flow .step .q { color: var(--teal); font-size: .78rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: .08em; }
.vp-flow .step h4 { margin: .25rem 0 .3rem 0; font-size: 1.02rem; }
.vp-flow .step p { margin: 0; color: var(--muted); font-size: .88rem; line-height: 1.45; }
.vp-flow .arrow { align-self: center; color: var(--indigo); font-size: 1.4rem; }
.vp-check { display: grid; grid-template-columns: 9.5rem 1fr; gap: .2rem .9rem; padding: .55rem 0;
  border-bottom: 1px solid var(--line); font-size: .9rem; }
.vp-check:last-child { border-bottom: none; }
.vp-check .dim { font-weight: 600; }
.vp-check .q { color: var(--muted); font-size: .8rem; }
.vp-check .item { margin: .15rem 0; }
.vp-check .detail { color: var(--muted); font-size: .82rem; }
.vp-event { border-left: 2px solid var(--line); padding: .15rem 0 .7rem .9rem; margin-left: .3rem; }
.vp-event .meta { color: var(--muted); font-size: .78rem; font-family: ui-monospace, Menlo, monospace; }
.vp-event .body { font-size: .92rem; margin-top: .15rem; }
.vp-muted { color: var(--muted); font-size: .88rem; }
.vp-brief { background: linear-gradient(135deg, rgba(45,212,191,.08), rgba(129,140,248,.08));
  border: 1px solid var(--line); border-radius: 14px; padding: 1.1rem 1.3rem; margin: .4rem 0 1.4rem 0; }
.vp-brief h3 { margin: .1rem 0 .2rem 0; font-size: 1.25rem; }
.vp-brief-headline { font-size: 1.05rem; font-weight: 700; color: var(--teal); margin: 0 0 .7rem 0; }
.vp-brief-row { display: grid; grid-template-columns: 9.5rem 1fr; gap: .2rem 1rem; padding: .6rem 0;
  border-top: 1px solid var(--line); font-size: .95rem; line-height: 1.5; }
.vp-brief-label { font-weight: 700; color: var(--text); }
.vp-brief-refs { margin-top: .3rem; color: var(--muted); font-size: .8rem; }
.vp-brief-note { margin: .6rem 0 0 0; font-size: .78rem; }
@media (max-width: 640px) { .vp-brief-row { grid-template-columns: 1fr; } }
.vp-q { color: var(--teal); font-size: .8rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
  margin: .2rem 0 .6rem 0; }
.vp-verbatim { font-size: .92rem; line-height: 1.55; }
.vp-unknown { border-color: rgba(251,191,36,.5); }
.vp-unknown h4 { color: var(--warn); }
.vp-footer { color: var(--muted); font-size: .8rem; margin-top: 2.5rem; border-top: 1px solid var(--line);
  padding-top: .8rem; }
section[data-testid="stSidebar"] .vp-brand { font-weight: 800; font-size: 1.15rem; }
section[data-testid="stSidebar"] .vp-brand span { color: var(--teal); }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def badge(text: str, kind: str = "muted", title: str | None = None) -> str:
    t = f' title="{e(title)}"' if title else ""
    return f'<span class="vp-badge {e(kind)}"{t}>{e(text)}</span>'


def chip(text: str, kind: str = "") -> str:
    return f'<span class="vp-chip {e(kind)}">{e(text)}</span>'


def lvl(code: str | None) -> str:
    if code is None:
        return '<span class="vp-lvl none">OK</span>'
    return f'<span class="vp-lvl {e(code.lower())}">{e(code)}</span>'


def page_header(eyebrow: str, title: str, lede: str) -> None:
    html(f'<div class="vp-eyebrow">{e(eyebrow)}</div>')
    st.title(title)
    html(f'<p class="vp-lede">{e(lede)}</p>')


def callout(text: str, kind: str = "") -> None:
    """`text` may contain <b>/<i> markup; callers pass only static copy."""
    html(f'<div class="vp-callout {e(kind)}">{text}</div>')


def card(title: str, body_html: str) -> None:
    html(f'<div class="vp-card"><h4>{e(title)}</h4>{body_html}</div>')


def level_banner(code: str, name: str, body: str) -> None:
    html(f'<div class="vp-level {e(code.lower())}"><span class="code">{e(code)}</span>'
         f'<span class="name">{e(name)}</span><p>{e(body)}</p></div>')


def footer() -> None:
    html('<div class="vp-footer">VectorPM · From Context to Trusted Action — a <i>Build With Me: AI Product '
         'Edition</i> demo. FlowPilot, its customers and every person named here are fictional. All execution '
         'is simulated; nothing leaves this page.</div>')
