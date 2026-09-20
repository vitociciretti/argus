import datetime as dt

from argus.connectors.gdelt import DEFAULT_QUERY, build_query
from argus.core.base import Finding, Record, ScanResult
from argus.report import apply_watchlist, render, watchlist_terms


def finding(title: str, importance: int = 2, entities=None, uid: str = "t:1") -> Finding:
    return Finding(
        Record(
            uid=uid, source="test", category="test",
            ts=dt.datetime.now(dt.timezone.utc), title=title,
            url="https://example.com", entities=entities or [],
        ),
        reason="new",
        importance=importance,
    )


def result(source, category, findings, n_records=10, first_run=False) -> ScanResult:
    return ScanResult(source, category, findings, n_records, first_run)


CFG = {"watchlist": {"tickers": ["NVDA"], "countries": ["Iran"], "terms": ["export controls"]}}


def test_watchlist_terms_flattened():
    assert watchlist_terms(CFG) == ["NVDA", "Iran", "export controls"]
    assert watchlist_terms({}) == []


def test_watchlist_boosts_and_tags():
    hit = finding("New export controls on chipmakers", importance=2)
    miss = finding("Something unrelated", importance=2)
    substring = finding("Iranian officials meet", importance=2)  # 'Iran' must not match 'Iranian'
    results = [result("s", "c", [hit, miss, substring])]
    apply_watchlist(results, watchlist_terms(CFG))
    assert hit.watchlist == ["export controls"]
    assert hit.importance == 3
    assert miss.watchlist == [] and miss.importance == 2
    assert substring.watchlist == []


def test_watchlist_matches_entities_and_caps_importance():
    f = finding("Designation", importance=5, entities=["IRAN SHIPPING LINES"])
    apply_watchlist([result("s", "c", [f])], ["Iran"])
    assert f.watchlist == ["Iran"]
    assert f.importance == 5  # capped


def test_render_sections():
    hit = finding("Export controls tightened", importance=3)
    hit.watchlist = ["export controls"]
    quiet = result("ofac_sdn", "sanctions", [], n_records=17000)
    busy = result("federal_register", "regulatory", [hit, finding("Minor rule", 3)])
    seeded = result("gdelt", "news-events", [], n_records=40, first_run=True)
    broken = result("polymarket", "prediction-markets", [], n_records=0)

    text = render([quiet, busy, seeded, broken], [("kalshi", RuntimeError("boom"))], "2026-09-20")

    assert "# argus daily report — 2026-09-20" in text
    assert "## Watchlist hits" in text
    assert "Export controls tightened" in text
    assert "_quiet — no changes_" in text
    assert "first run — baseline of 40 records seeded" in text
    assert "polymarket: WARNING — fetch returned 0 records" in text
    assert "kalshi: FAILED — boom" in text
    assert "5 sources scanned · 2 findings · 1 watchlist hits · 1 failures" in text


def test_render_caps_low_importance():
    low = [finding(f"noise {i}", importance=1, uid=f"t:{i}") for i in range(15)]
    text = render([result("gdelt", "news-events", low)], [], "2026-09-20")
    assert "noise 14" in text  # newest first
    assert "noise 0" not in text  # oldest cut by the cap
    assert "+5 more low-importance items not shown" in text


def test_gdelt_query_from_watchlist():
    assert build_query({}) == DEFAULT_QUERY
    assert build_query({"query": "custom"}) == "custom"
    q = build_query({"watchlist": {"countries": ["Iran"], "terms": ["export controls"]}})
    assert q == '(Iran OR "export controls") sourcelang:english'
