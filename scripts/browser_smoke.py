"""Browser smoke test against a running app (real Chromium, real websockets).

    streamlit run streamlit_app.py --server.port 8517 &
    python scripts/browser_smoke.py --url http://localhost:8517 [--shots DIR]

Checks every page renders, walks Scenario C end to end in one browser context,
and confirms a second, independent context sees none of that activity.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

PAGES = ["Introduction", "1 · Explore Context", "2 · Test Agent Autonomy", "3 · Audit & Accountability"]


def nav(page: Page, label: str) -> None:
    page.get_by_test_id("stSidebar").get_by_text(label, exact=True).click()
    page.wait_for_timeout(600)


def click(page: Page, name: str) -> None:
    page.get_by_role("button", name=name, exact=True).first.click()
    page.wait_for_timeout(700)


def choose_approver(page: Page, label_part: str) -> None:
    page.get_by_test_id("stSelectbox").first.click()
    page.get_by_role("option").filter(has_text=label_part).first.click()
    page.wait_for_timeout(500)


def no_exceptions(page: Page) -> None:
    assert page.get_by_test_id("stException").count() == 0, "Streamlit exception on page"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8501")
    ap.add_argument("--shots", default=None)
    args = ap.parse_args()
    shots = Path(args.shots) if args.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        a = browser.new_context(viewport={"width": 1400, "height": 1000}).new_page()
        a.goto(args.url)
        expect(a.get_by_text("From Context to Trusted Action").first).to_be_visible(timeout=30000)

        for label in PAGES:
            nav(a, label)
            no_exceptions(a)
            if shots:
                a.screenshot(path=str(shots / f"page-{PAGES.index(label)}.png"), full_page=True)
        print("ok  all four pages render")

        nav(a, PAGES[2])
        click(a, "C · Decision update")
        click(a, "Evaluate proposal")
        expect(a.get_by_text("Approval required").first).to_be_visible()
        click(a, "Execute (simulated)")
        expect(a.get_by_text("APPROVAL_REQUIRED").first).to_be_visible()
        choose_approver(a, "Sam Reyes")
        click(a, "Approve")
        expect(a.get_by_text("APPROVER_NOT_AUTHORIZED").first).to_be_visible()
        choose_approver(a, "the proposing agent")
        click(a, "Approve")
        expect(a.get_by_text("APPROVER_NOT_HUMAN").first).to_be_visible()
        choose_approver(a, "Ana Ortiz")
        click(a, "Approve")
        click(a, "Execute (simulated)")
        expect(a.get_by_text("Simulated execution completed").first).to_be_visible()
        if shots:
            a.screenshot(path=str(shots / "scenario-c-executed.png"), full_page=True)
        print("ok  scenario C: refused x3, approved by Ana Ortiz, executed (simulated)")

        click(a, "D · Customer promise")
        click(a, "Evaluate proposal")
        expect(a.get_by_text("PROHIBITED").first).to_be_visible()
        click(a, "E · Tampered context")
        click(a, "Evaluate proposal")
        expect(a.get_by_text("SOURCE_MISMATCH: FP-002.status", exact=False).first).to_be_visible()
        if shots:
            a.screenshot(path=str(shots / "scenario-e-tampered.png"), full_page=True)
        print("ok  scenario D blocked (PROHIBITED), scenario E blocked (integrity)")

        nav(a, PAGES[3])
        expect(a.get_by_text("Hash chain intact").first).to_be_visible()
        if shots:
            a.screenshot(path=str(shots / "audit.png"), full_page=True)
        first_events = a.get_by_text("Hash chain intact").first.inner_text()
        print(f"ok  audit page for session 1: {first_events}")

        b = browser.new_context(viewport={"width": 1400, "height": 1000}).new_page()
        b.goto(args.url)
        expect(b.get_by_text("From Context to Trusted Action").first).to_be_visible(timeout=30000)
        nav(b, PAGES[3])
        expect(b.get_by_text("Hash chain intact · 0 entries").first).to_be_visible()
        expect(b.get_by_text("No activity yet").first).to_be_visible()
        print("ok  session 2 sees an empty audit log")

        nav(a, PAGES[3])
        assert a.get_by_text("Hash chain intact").first.inner_text() == first_events
        print("ok  session 1 unchanged after session 2 connected")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
