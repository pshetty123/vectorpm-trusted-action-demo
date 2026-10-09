import sys
from pathlib import Path

import pytest

DEMO_ROOT = Path(__file__).resolve().parents[1]
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

from demo.engine import DemoSession, _ensure_import_path, load_shared, verify_vendor  # noqa: E402

verify_vendor()        # same fail-closed check the app runs, then expose the vendored packages
_ensure_import_path()


@pytest.fixture(scope="session")
def shared():
    return load_shared()


@pytest.fixture
def session(shared):
    """A fresh, private demo session, exactly as one browser visitor gets."""
    return DemoSession(shared)
