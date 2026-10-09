# Deployment readiness checklist

Target: Streamlit Community Cloud, from a standalone public GitHub repository containing only this
folder. **Not deployed yet. Publishing waits for owner approval after local testing.**

## Before creating the repository

- [ ] Copy this folder out of the monorepo, or `git init` inside it. Don't push the monorepo.
- [ ] Remove local-only artefacts: `.venv/`, `__pycache__/`, `.pytest_cache/` (all git-ignored).
- [ ] Run `python scripts/sync_vendor.py --check` from inside the monorepo **before** copying out, to
      confirm `vendor/` still matches the tested prototypes.
- [ ] `git status` shows only: `streamlit_app.py`, `demo/`, `vendor/`, `scripts/`, `tests/`, `docs/`,
      `.github/workflows/tests.yml`, `.streamlit/config.toml`, `requirements*.txt`, `pytest.ini`,
      `README.md`, `DEPLOYMENT_CHECKLIST.md`, `.gitignore`.
- [ ] The only database in the repo is `vendor/trust-layer/fixtures/flowpilot_reservoir.db`
      (fictional, about 400 KB, hash-pinned).
- [ ] No `.env`, `secrets.toml`, keys or tokens. The app needs none. (A scan of the fixture for key
      patterns, emails and local paths found nothing at packaging time.)

## Verify locally (all must pass)

- [ ] `python -m pytest` passes: 59 tests (58 in a standalone checkout; the upstream-hash check skips).
- [ ] `scripts/browser_smoke.py` passes against `streamlit run streamlit_app.py`.
- [ ] Manual walkthrough of all three sections in a fresh browser; reset session works.
- [ ] Second browser profile or incognito window shows an empty audit log.

## Streamlit Community Cloud settings

- [ ] Main file: `streamlit_app.py`.
- [ ] Python version: 3.12 or newer (developed on 3.14; set it under *Advanced settings*).
- [ ] Secrets: leave empty.
- [ ] Dependencies: `requirements.txt` (pinned `streamlit`, `pydantic`). `requirements-dev.txt` is
      for local tests only.
- [ ] `.streamlit/config.toml` sets the theme, `showErrorDetails = "none"` (visitors never see
      tracebacks; the old boolean `false` would have shown them), the viewer-only toolbar, and pinned
      XSRF/CORS defaults. A test guards these.
- [ ] CI: `.github/workflows/tests.yml` runs pytest on Python 3.12 and 3.13 on every push.

## After deploying

- [ ] Open the public URL in two browsers and confirm sessions are isolated.
- [ ] Walk scenarios A–F and check the levels: L3, L1, L2, L0, L0, L1.
- [ ] Confirm the app shows the vendor-integrity error, not results, if a vendored file is altered.
      Test this locally on a copy, never on the deployed repo.

## Open decisions for the owner

- [ ] **License.** None is included. A public repo without one is "all rights reserved" by default.
- [ ] **Repository name and visibility** on GitHub.
- [ ] **Decision brief wording** (`demo/context_brief.py`). It's the only editorial summary on the
      page. Every claim is cited and tested against the stored review, but it's worth a final read.

## Ongoing risks

| Risk | Impact | Mitigation |
|---|---|---|
| Fictional sources age past freshness thresholds | Strength of constructed packets (E, F) can drop over time; levels currently unaffected (E fails integrity, F is capped by superseded evidence) | Re-run `pytest` periodically; tests fail if a level changes |
| A session left open for more than 7 days | Its scenario packets exceed `max_packet_age_hours` and cap at L1 (`CONTEXT_EXPIRED`) | "Reset my session" rebuilds packets. This is correct fail-safe behaviour |
| Upstream prototypes change | Demo silently diverges from them | `sync_vendor.py --check` and the upstream-hash test |
| Simulated identities mistaken for real auth | Misleading takeaway | Labelled "simulated identity" throughout; called out in Section 3 and the README |
| Many concurrent visitors | Memory per session (small in-memory SQLite) | Streamlit Cloud resource limits; sessions are discarded on disconnect |
