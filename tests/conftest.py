import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from schedule_agent.store import DraftStore, World  # noqa: E402
from schedule_agent.tools import FaultPlan, ToolBox  # noqa: E402

DATE, CH = "2026-11-12", "feed"


def item(mid, t, flex="flexible"):
    return {"material_id": mid, "channel": CH, "date": DATE, "preferred_time": t, "time_flexibility": flex}


@pytest.fixture
def store(tmp_path):
    return DraftStore(tmp_path / "state")


@pytest.fixture
def make_toolbox(store):
    def _make(items, faults=None, overrides=None):
        req = {"request_id": "REQ-T", "items": items}
        return ToolBox(World(schedule_overrides=overrides), store, req, FaultPlan(spec=faults or {}))
    return _make
