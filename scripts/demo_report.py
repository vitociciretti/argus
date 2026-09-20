"""Render a demo HTML report with rich synthetic data — every visual state the
renderer supports (watchlist cards, both bar directions, quiet/seeded/warning/
failed sources). Run: python scripts/demo_report.py"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from argus.core.base import Finding, Record, ScanResult  # noqa: E402
from argus.html_report import render_html  # noqa: E402

NOW = dt.datetime.now(dt.timezone.utc)


def rec(uid, source, category, title, url="https://example.com", entities=None):
    return Record(uid=uid, source=source, category=category, ts=NOW,
                  title=title, url=url, entities=entities or [])


ofac_hit = Finding(
    rec("ofac:99001", "ofac_sdn", "sanctions",
        "DERYA SHIPPING AND TRADING CORP [entity] - IRAN-EO13902",
        "https://sanctionssearch.ofac.treas.gov/", ["DERYA SHIPPING"]),
    reason="new designation", importance=5, watchlist=["Iran"])

fedreg_hit = Finding(
    rec("fedreg:2026-18123", "federal_register", "regulatory",
        "Additions to the Entity List: Export Controls on Advanced Computing Items to China",
        "https://www.federalregister.gov/d/2026-18123"),
    reason="new (Rule)", importance=4, watchlist=["export controls", "China"])

pm_hit = Finding(
    rec("polymarket:665374", "polymarket", "prediction-markets",
        "Will the U.S. invade Iran before 2027?",
        "https://polymarket.com/market/will-the-us-invade-iran-before-2027"),
    reason="probability 18% -> 31% (+13pp)", importance=5,
    watchlist=["Iran"], extra={"from": 0.18, "to": 0.31})

pm_up = Finding(
    rec("polymarket:1", "polymarket", "prediction-markets",
        "Fed cuts rates at the October FOMC meeting?",
        "https://polymarket.com/market/fed-cut-october"),
    reason="probability 62% -> 78% (+16pp)", importance=4, extra={"from": 0.62, "to": 0.78})

pm_down = Finding(
    rec("polymarket:2", "polymarket", "prediction-markets",
        "US government shutdown before November?",
        "https://polymarket.com/market/shutdown-november"),
    reason="probability 44% -> 26% (-18pp)", importance=4, extra={"from": 0.44, "to": 0.26})

pm_small = Finding(
    rec("polymarket:3", "polymarket", "prediction-markets",
        "Will AfD win the most seats in Mecklenburg-Vorpommern?",
        "https://polymarket.com/market/afd-mv"),
    reason="probability 53% -> 60% (+7pp)", importance=3, extra={"from": 0.53, "to": 0.60})

fedreg_items = [
    Finding(rec(f"fedreg:2026-1800{i}", "federal_register", "regulatory", title,
                "https://www.federalregister.gov/"),
            reason=f"new ({kind})", importance=3)
    for i, (title, kind) in enumerate([
        ("Margin and Capital Requirements for Covered Swap Entities; Correction", "Rule"),
        ("Form PF Reporting Requirements for Large Hedge Fund Advisers", "Proposed Rule"),
    ])
]

gdelt_items = [
    Finding(rec(f"gdelt:{i:04x}", "gdelt", "news-events", title, "https://news.example.com"),
            reason="new", importance=1)
    for i, title in enumerate([
        "Tanker rates spike as Strait of Hormuz transits slow",
        "EU weighs 19th sanctions package targeting shadow fleet",
        "Chipmakers brace for expanded export controls",
        "Uranium spot price hits 18-month high on supply concerns",
        "Russia's central bank holds rates amid ruble pressure",
        "Taiwan strait incursions rise for third straight week",
        "LNG flows rerouted after pipeline maintenance extended",
        "Copper inventories at LME warehouses fall to decade low",
        "New tariffs on EV imports enter into force",
        "Gulf states discuss joint naval escorts for tankers",
        "OPEC+ compliance slips as quotas loosen",
        "Sovereign wealth funds rotate into gold",
    ])
]

results = [
    ScanResult("ofac_sdn", "sanctions", [ofac_hit], 19402, False),
    ScanResult("federal_register", "regulatory", [fedreg_hit] + fedreg_items, 50, False),
    ScanResult("polymarket", "prediction-markets", [pm_hit, pm_up, pm_down, pm_small], 47, False),
    ScanResult("gdelt", "news-events", gdelt_items, 40, False),
    ScanResult("kalshi", "prediction-markets", [], 0, False),          # 0-record warning
    ScanResult("warn_notices", "labor", [], 120, True),                # first-run seeding
]
failures = [("courtlistener", RuntimeError("HTTP 503 from api.courtlistener.com"))]

out = pathlib.Path(__file__).resolve().parents[1] / "data" / "reports" / "demo.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(render_html(results, failures, dt.date.today().isoformat()))
print(out)
