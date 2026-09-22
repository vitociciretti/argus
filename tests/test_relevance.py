import datetime as dt

from argus import synthesis
from argus.core.base import Finding, Record, ScanResult
from argus.relevance import (
    apply,
    build_clusters,
    normalize_entity,
    top_signals,
)


def finding(title, importance=2, entities=None, category="test", uid="t:1",
            metrics=None, extra=None, reason="new") -> Finding:
    return Finding(
        Record(
            uid=uid, source="s", category=category,
            ts=dt.datetime.now(dt.timezone.utc), title=title,
            url="https://example.com", entities=entities or [],
            metrics=metrics or {},
        ),
        reason=reason, importance=importance, extra=extra or {},
    )


def result(category, findings, first_run=False) -> ScanResult:
    return ScanResult("s", category, findings, len(findings), first_run)


def test_normalize_strips_legal_suffixes():
    assert normalize_entity("Kinetik Holdings Inc.") == normalize_entity("Kinetik Holdings")
    assert normalize_entity("The") == ""          # pure stopword
    assert normalize_entity("A.B") == ""          # nothing >= 4 chars
    assert "elliott" in normalize_entity("Elliott Investment Management L.P.")


def test_known_actor_boosts_importance():
    elliott = finding("SCHEDULE 13D/A: Elliott Investment Management L.P.", importance=3,
                      entities=["Elliott Investment Management L.P."])
    unknown = finding("SCHEDULE 13D/A: Foglia Stephanie Athena", importance=3,
                      entities=["Foglia Stephanie Athena"], uid="t:2")
    apply([result("ownership", [elliott, unknown])], {})
    assert elliott.importance == 4                 # known activist -> +1
    assert unknown.importance == 3                 # untouched
    assert elliott.extra["relevance"] > unknown.extra["relevance"]
    assert any("elliott" in w for w in elliott.extra["why"])


def test_magnitude_from_amount():
    # magnitude alone (0.20 for $149M) is below the 0.5 boost bar — it colours the
    # 'why' and the relevance score but does not, by itself, jump importance.
    mid = finding("WALSH FEDERAL LLC contract", importance=3, metrics={"amount": 149e6})
    apply([result("gov-spending", [mid])], {})
    assert mid.importance == 3
    assert mid.extra["relevance"] == 0.2
    assert any("$149M" in w for w in mid.extra["why"])
    # a billion-dollar transaction (0.40) plus a watchlist hit clears the bar.
    huge = finding("MEGA DEFENSE CORP", importance=3, metrics={"amount": 2.0e9},
                   extra={}, uid="t:big")
    huge.watchlist = ["defense"]
    apply([result("gov-spending", [huge])], {})
    assert huge.importance == 4


def test_probability_move_magnitude():
    f = finding("Some market", importance=3, extra={"from": 0.40, "to": 0.55})
    apply([result("prediction-markets", [f])], {})
    assert any("pp move" in w for w in f.extra["why"])


def test_confluence_needs_two_categories():
    a = finding("HealthStream Inc layoffs", entities=["HealthStream Inc"], category="labor", uid="a")
    b = finding("SCHEDULE 13D: HealthStream Inc", entities=["HealthStream Inc"],
                category="ownership", uid="b")
    solo = finding("Acme Corp docket", entities=["Acme Corp"], category="legal", uid="c")
    clusters = build_clusters([result("labor", [a]), result("ownership", [b]), result("legal", [solo])])
    assert len(clusters) == 1
    cl = next(iter(clusters.values()))
    assert set(cl.categories) == {"labor", "ownership"}


def test_confluence_boosts_and_is_returned():
    a = finding("HealthStream Inc layoffs", entities=["HealthStream Inc"], category="labor", uid="a")
    b = finding("SCHEDULE 13D: HealthStream Inc", entities=["HealthStream Inc"],
                category="ownership", uid="b")
    clusters = apply([result("labor", [a]), result("ownership", [b])], {})
    assert len(clusters) == 1
    assert a.importance == 3 and b.importance == 3  # 2 + confluence bump
    assert any("confluence" in w for w in a.extra["why"])


def test_first_run_excluded_from_confluence_and_top():
    a = finding("X Corp thing", entities=["X Corp"], category="labor", uid="a")
    b = finding("X Corp other", entities=["X Corp"], category="ownership", uid="b")
    clusters = apply([result("labor", [a], first_run=True), result("ownership", [b])], {})
    assert clusters == []
    assert top_signals([result("labor", [a], first_run=True)]) == []


def test_top_signals_ordered_and_capped():
    fs = [finding(f"f{i}", importance=(i % 5) + 1, uid=f"t:{i}") for i in range(20)]
    top = top_signals([result("c", fs)], n=5)
    assert len(top) == 5
    assert [f.importance for f in top] == sorted([f.importance for f in top], reverse=True)
    assert top[0].importance == 5


def test_synthesis_disabled_returns_none():
    assert synthesis.generate([], [], [], {}) is None
    assert synthesis.generate([], [], [], {"llm": {"enabled": False}}) is None


def test_synthesis_enabled_but_no_data_returns_none():
    assert synthesis.generate([], [], [], {"llm": {"enabled": True}}) is None
