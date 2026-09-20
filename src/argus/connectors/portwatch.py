"""IMF PortWatch daily chokepoint transit counts (Suez, Panama, Hormuz, ...)
via the public ArcGIS feature service (no key). Data lags ~7 days.

Signal: a chokepoint's recent 7-day transit average entering disruption
(low) or surge (high) territory versus its own prior 30-day baseline —
crossing-based, so a long blockage doesn't re-fire daily.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from ..core import http
from ..core.base import Connector, Record, crossing_findings

QUERY_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
    "Daily_Chokepoints_Data/FeatureServer/0/query"
)


HEADLINE_CHOKEPOINTS = [
    "Suez Canal", "Panama Canal", "Strait of Hormuz",
    "Bab el-Mandeb Strait", "Strait of Malacca", "Bosporus Strait",
]


def build_records(rows: list[dict], headline: list[str] | None = None) -> list[Record]:
    """rows: attribute dicts with date/portid/portname/n_total, newest first.
    Headline chokepoints get a pulse series; the rest are delta-only."""
    headline = HEADLINE_CHOKEPOINTS if headline is None else headline
    by_port: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
    for a in rows:
        if a.get("date") and a.get("n_total") is not None:
            by_port[a["portid"]].append((a["date"], float(a["n_total"]), a.get("portname", "?")))

    records = []
    for portid, series in by_port.items():
        series.sort(reverse=True)  # newest first
        recent = [v for _, v, _ in series[:7]]
        baseline = [v for _, v, _ in series[7:37]]
        if len(recent) < 5 or len(baseline) < 15:
            continue
        recent_avg = sum(recent) / len(recent)
        base_avg = sum(baseline) / len(baseline)
        ratio = recent_avg / base_avg if base_avg else 1.0
        latest_date, _, portname = series[0]
        is_headline = portname in headline
        records.append(
            Record(
                uid=f"portwatch:{portid}",
                source="portwatch",
                category="trade-chokepoints",
                ts=dt.datetime.fromisoformat(latest_date).replace(tzinfo=dt.timezone.utc),
                title=f"{portname} — {recent_avg:.0f} transits/day (7d) vs {base_avg:.0f} (prior 30d)",
                url="https://portwatch.imf.org/",
                entities=[portname],
                metrics={"transits_7d": recent_avg, "baseline_30d": base_avg, "ratio": ratio},
                series=[v for _, v, _ in reversed(series)] if is_headline else [],
                series_name=f"{portname} transits/day" if is_headline else "",
            )
        )
    return records


class PortWatch(Connector):
    name = "portwatch"
    category = "trade-chokepoints"
    license_note = "IMF PortWatch open data (with UN Global Platform); cite IMF."
    report_new = False

    def fetch(self) -> list[Record]:
        since = (dt.date.today() - dt.timedelta(days=50)).isoformat()
        params = {
            "where": f"date >= DATE '{since}'",
            "outFields": "date,portid,portname,n_total",
            "orderByFields": "date DESC",
            "resultRecordCount": 3000,
            "f": "json",
        }
        data = http.get(QUERY_URL, params=params, min_interval=2.0).json()
        rows = [f["attributes"] for f in data.get("features", [])]
        return build_records(rows, self.cfg.get("headline"))

    def metric_findings(self, records, state, first_run):
        low = float(self.cfg.get("disruption_ratio", 0.7))
        high = float(self.cfg.get("surge_ratio", 1.4))
        findings = []
        for r in records:
            findings += crossing_findings(
                r,
                state,
                key="ratio",
                value=r.metrics["ratio"],
                alert_below=low,
                reason_fmt="transit disruption: 7d/30d ratio {prev:.2f} -> {value:.2f}",
                importance=4,
            )
            findings += crossing_findings(
                r,
                state,
                key="ratio_high",
                value=r.metrics["ratio"],
                alert_above=high,
                reason_fmt="transit surge: 7d/30d ratio {prev:.2f} -> {value:.2f}",
                importance=3,
            )
        return findings
