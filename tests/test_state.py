import datetime as dt

from argus.core.base import Record
from argus.core.state import StateStore


def rec(uid: str, source: str = "test") -> Record:
    return Record(
        uid=uid, source=source, category="test",
        ts=dt.datetime.now(dt.timezone.utc), title=uid,
    )


def test_seen_roundtrip(tmp_path):
    state = StateStore(tmp_path / "state.db")
    assert state.known_uids("test") == set()
    state.add_seen([rec("a"), rec("b")])
    assert state.known_uids("test") == {"a", "b"}
    state.add_seen([rec("a")])  # idempotent
    assert state.known_uids("test") == {"a", "b"}


def test_seeding_flag(tmp_path):
    state = StateStore(tmp_path / "state.db")
    assert not state.is_seeded("x")
    state.mark_seeded("x")
    assert state.is_seeded("x")
    assert not state.is_seeded("y")


def test_metrics_upsert(tmp_path):
    state = StateStore(tmp_path / "state.db")
    assert state.get_metric("m1", "probability") is None
    state.set_metric("m1", "probability", 0.4)
    assert state.get_metric("m1", "probability") == 0.4
    state.set_metric("m1", "probability", 0.55)
    assert state.get_metric("m1", "probability") == 0.55
