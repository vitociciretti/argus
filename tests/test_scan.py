import datetime as dt

from argus.connectors.polymarket import Polymarket
from argus.core.base import Connector, Record
from argus.core.state import StateStore


def rec(uid: str, source: str, **metrics) -> Record:
    return Record(
        uid=uid, source=source, category="test",
        ts=dt.datetime.now(dt.timezone.utc), title=uid, metrics=metrics,
    )


class Fake(Connector):
    name = "fake"
    category = "test"

    def __init__(self, records):
        super().__init__({})
        self.records = records

    def fetch(self):
        return self.records


def test_first_run_seeds_quietly(tmp_path):
    state = StateStore(tmp_path / "s.db")
    result = Fake([rec("a", "fake"), rec("b", "fake")]).scan(state)
    assert result.findings == []
    assert result.first_run
    assert result.n_records == 2
    assert state.is_seeded("fake")


def test_second_run_reports_only_new(tmp_path):
    state = StateStore(tmp_path / "s.db")
    Fake([rec("a", "fake")]).scan(state)
    result = Fake([rec("a", "fake"), rec("b", "fake")]).scan(state)
    assert not result.first_run
    assert len(result.findings) == 1
    assert result.findings[0].record.uid == "b"
    assert result.findings[0].reason == "new"
    # third run, nothing new
    assert Fake([rec("a", "fake"), rec("b", "fake")]).scan(state).findings == []


def market(uid: str, prob: float, vol: float = 50_000) -> Record:
    return rec(uid, "polymarket", probability=prob, volume_24h=vol)


def test_polymarket_flags_moves_not_levels(tmp_path):
    state = StateStore(tmp_path / "s.db")
    pm = Polymarket({"move_threshold": 0.05})

    # first pass: baseline only, no findings
    assert pm.metric_findings([market("polymarket:1", 0.60)], state, first_run=True) == []

    # small move: quiet; big move: flagged
    assert pm.metric_findings([market("polymarket:1", 0.62)], state, first_run=False) == []
    found = pm.metric_findings([market("polymarket:1", 0.70)], state, first_run=False)
    assert len(found) == 1
    assert "62%" in found[0].reason and "70%" in found[0].reason


def test_polymarket_ignores_thin_markets(tmp_path):
    state = StateStore(tmp_path / "s.db")
    pm = Polymarket({"move_threshold": 0.05, "min_volume_24h": 10_000})
    pm.metric_findings([market("polymarket:2", 0.30, vol=500)], state, first_run=True)
    found = pm.metric_findings([market("polymarket:2", 0.90, vol=500)], state, first_run=False)
    assert found == []
