"""Copy the tested prototype code into vendor/, byte for byte, and pin hashes.

Run from inside the VectorPM monorepo, where both prototypes live as siblings:

    python scripts/sync_vendor.py            # copy + rewrite vendor/VENDORED.json
    python scripts/sync_vendor.py --check    # verify vendor/ still matches upstream

The vendor tree mirrors the monorepo layout so the Trust Layer adapter's own
relative path defaults resolve without any edits:

    vendor/trust-layer/trust_layer/...                     (Trust & Control Layer)
    vendor/trust-layer/policy/flowpilot_policy.v1.json
    vendor/trust-layer/fixtures/flowpilot_reservoir.db     (fictional FlowPilot corpus)
    vendor/experiments/reservoir-decision-review/backend/app/...   (Reservoir modules)

Nothing is edited after copying. The demo's tests fail if a vendored file's
hash differs from VENDORED.json, so a local edit can't slip through silently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

DEMO_ROOT = Path(__file__).resolve().parents[1]
MONOREPO = DEMO_ROOT.parent
VENDOR = DEMO_ROOT / "vendor"

# Only what the Trust Layer's service/scenarios/adapter import at runtime.
# Deliberately excluded: trust_layer/api.py + static/ (FastAPI server, not needed),
# the Reservoir's LLM, retrieval, ingestion and HTTP layers, and every database
# other than the read-only fixture.
FILES = [
    "trust-layer/trust_layer/__init__.py",
    "trust-layer/trust_layer/schemas.py",
    "trust-layer/trust_layer/policy.py",
    "trust-layer/trust_layer/integrity.py",
    "trust-layer/trust_layer/evaluator.py",
    "trust-layer/trust_layer/audit.py",
    "trust-layer/trust_layer/simulator.py",
    "trust-layer/trust_layer/service.py",
    "trust-layer/trust_layer/scenarios.py",
    "trust-layer/trust_layer/adapters/__init__.py",
    "trust-layer/trust_layer/adapters/vectorpm.py",
    "trust-layer/policy/flowpilot_policy.v1.json",
    "trust-layer/fixtures/flowpilot_reservoir.db",
    "trust-layer/fixtures/MANIFEST.json",
    "experiments/reservoir-decision-review/backend/app/__init__.py",
    "experiments/reservoir-decision-review/backend/app/schemas/__init__.py",
    "experiments/reservoir-decision-review/backend/app/schemas/context_source.py",
    "experiments/reservoir-decision-review/backend/app/schemas/synthesis.py",
    "experiments/reservoir-decision-review/backend/app/schemas/challenger.py",
    "experiments/reservoir-decision-review/backend/app/schemas/validators.py",
    "experiments/reservoir-decision-review/backend/app/storage/__init__.py",
    "experiments/reservoir-decision-review/backend/app/storage/db.py",
    "experiments/reservoir-decision-review/backend/app/storage/source_repo.py",
    "experiments/reservoir-decision-review/backend/app/synthesis/__init__.py",
    "experiments/reservoir-decision-review/backend/app/synthesis/evidence_strength.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify only; copy nothing")
    args = ap.parse_args()

    missing = [f for f in FILES if not (MONOREPO / f).is_file()]
    if missing:
        print("upstream files not found (run inside the VectorPM monorepo):", *missing, sep="\n  ")
        return 1

    if args.check:
        drift = [f for f in FILES if not (VENDOR / f).is_file() or sha256(VENDOR / f) != sha256(MONOREPO / f)]
        print("vendor/ matches upstream" if not drift else "drift:\n  " + "\n  ".join(drift))
        return 1 if drift else 0

    manifest = {}
    for rel in FILES:
        src, dst = MONOREPO / rel, VENDOR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)  # contents only; upstream is only ever read
        manifest[rel] = sha256(dst)
    (VENDOR / "VENDORED.json").write_text(json.dumps({
        "note": "Byte-identical copies of the tested prototypes. Do not edit; re-run scripts/sync_vendor.py.",
        "files": manifest,
    }, indent=2) + "\n")
    print(f"vendored {len(manifest)} files into {VENDOR.relative_to(DEMO_ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
