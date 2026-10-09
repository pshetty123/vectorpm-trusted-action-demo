# VectorPM: From Context to Trusted Action

A guided, 5–7 minute Streamlit demo of how AI agents move from evidence-backed reasoning to
risk-adjusted autonomy.

**Can AI do the work? → Does it have the right context? → Should it be allowed to act?**

```
Agentic AI PM Team  →  VectorPM Reservoir  →  Trust & Control Layer
   (proposes)            (context: provenance,     (decides L0–L3 from authority, risk,
                          freshness, strength)       evidence and context integrity)
```

Part of the *Build With Me: AI Product Edition* series. Everything is fictional (FlowPilot is a
made-up SaaS company) and every execution is simulated.

## Run it locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run streamlit_app.py
# → http://localhost:8501
```

Python 3.10 or newer (developed and tested on 3.14). No API keys, secrets, network access or
database setup needed.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest                       # unit, integration and headless-app tests

# Real-browser smoke test (Chromium via Playwright), against a running app:
.venv/bin/python -m playwright install chromium  # first time only
.venv/bin/streamlit run streamlit_app.py --server.port 8517 &
.venv/bin/python scripts/browser_smoke.py --url http://localhost:8517
```

## The three sections

1. **Explore Context**: the fictional FlowPilot Reservoir. Sources with status (current, historical,
   stale, superseded), a stored decision review with evidence strength, supporting and contradicting
   sources, assumptions, decision history, missing information and freshness. Also an evidence-strength
   lab that runs the Reservoir's own deterministic scoring function.
2. **Test Agent Autonomy**: six agent proposals evaluated by the real Trust Layer:

   | | Scenario | Result |
   |---|---|---|
   | A | Add a low-risk internal note | **L3** Autonomous, executes (simulated) |
   | B | Roadmap change on weak, contradicted evidence | **L1** Recommend, execution refused |
   | C | Record a consequential decision | **L2** Approval required: wrong approver, agent self-approval and early execution all refused; Ana Ortiz (simulated) approves, then it executes |
   | D | Promise a release date to a customer at 96% | **L0** `PROHIBITED`, even at 100% and with an execute grant and HIGH evidence |
   | E | Tampered context packet, re-sealed hash | **L0** `INTEGRITY_FAILURE` |
   | F | Same proposal as E with honest, superseded evidence | **L1** `SUPERSEDED_EVIDENCE` |

3. **Audit & Accountability**: the visitor's own hash-chained, append-only audit log: evaluations,
   policy decisions, approval attempts, refusals and simulated executions, with reason codes and
   context references.

## Architecture

Streamlit is only the presentation layer. Every level, reason code, approval check and
execution refusal comes from the original, tested prototype code.

```
streamlit_app.py           pages, widgets, layout
demo/engine.py             verifies vendor/ hashes, loads shared read-only policy + Reservoir
                           adapter, gives each session its own TrustService
demo/reservoir_view.py     read-only views of the Reservoir for Section 1
demo/presentation.py       plain-English labels for codes (display only, decides nothing)
demo/ui.py                 reusable UI components and theme CSS
vendor/                    byte-identical copies of the tested prototypes (see below)
scripts/sync_vendor.py     re-copies vendor/ from the monorepo and re-pins hashes
scripts/browser_smoke.py   Playwright smoke test
tests/                     integration, safety and headless-app tests
```

### Reused components (vendored, unmodified)

`vendor/` mirrors the monorepo layout so the Trust Layer adapter's own path defaults work without
edits. `vendor/VENDORED.json` pins a SHA-256 for every file. The app refuses to start if any file
differs, and a test checks the pins against the upstream prototypes when they're present.

| From | Files | Used for |
|---|---|---|
| Trust & Control Layer | `schemas`, `policy`, `integrity`, `evaluator`, `audit`, `simulator`, `service`, `scenarios`, `adapters/vectorpm` | Action Registry, Grant Store, prohibitions, context integrity, autonomy evaluation, approval rules, simulated execution, hash-chained audit, scenarios A–F |
| Trust & Control Layer | `policy/flowpilot_policy.v1.json`, `fixtures/flowpilot_reservoir.db` (+ manifest) | Fictional policy and read-only fictional Reservoir corpus |
| VectorPM Reservoir | `schemas/{context_source,synthesis,challenger,validators}`, `storage/{db,source_repo}`, `synthesis/evidence_strength` | Source provenance and status, review synthesis, deterministic evidence strength |

Not vendored: the Trust Layer's FastAPI server and static UI, and the Reservoir's LLM, retrieval,
ingestion and HTTP layers. The demo needs no LLM calls: the stored review is already in the fixture.

To refresh after changing a prototype (run inside the monorepo):

```bash
python scripts/sync_vendor.py          # copy + re-pin
python scripts/sync_vendor.py --check  # verify only
```

### Session isolation

Each browser session gets its own `TrustService` backed by an in-memory SQLite database
(`":memory:"`). Approvals, executions and audit history exist only in that session and are discarded
when it ends. Shared across sessions (read-only): the policy and the Reservoir adapter, which opens
the fixture with SQLite `mode=ro`. There is no shared writable store.

## Safety properties

- Fictional FlowPilot data only. Approver identities are labelled as simulated.
- No network clients, LLM SDKs or credentials anywhere in the package (enforced by a test).
- Execution is the Trust Layer's simulator: it describes what *would* happen and nothing else.
- Visitors cannot change policy. There is no policy-editing UI, and the policy file is hash-verified.
- Unknown actions, unknown agents and invalid or tampered context fail closed (L0).
- Agent confidence is recorded but never read by policy.
- If a component fails, the app shows an error and no result. It never substitutes a made-up one.

## Known limitations

- **Upstream data issues are worked around, not fixed.** See [docs/UPSTREAM_ISSUES.md](docs/UPSTREAM_ISSUES.md):
  duplicated decision rationale text, and overlapping missing-information entries.

- **Identity is simulated.** Visitors choose who they approve as. That's the point of the demo, and
  the main gap before any real use: production needs authenticated identities.
- **Audit is per session and in memory.** It shows the shape of accountability. It is not a durable,
  externally anchored audit store.
- **Evidence strengths for the stored review are frozen** at the time that review ran. Constructed
  packets (E, F) are scored on the day you run them, so freshness scores drift as the fictional
  sources age. The scenarios' levels don't depend on that drift today; see the deployment checklist.
- **Tiny fictional corpus** (14 sources). The rules are tested; their calibration on real data isn't.
- One Streamlit process shares the read-only policy and adapter objects across sessions. They're
  never mutated, but this isn't a multi-tenant security boundary.
