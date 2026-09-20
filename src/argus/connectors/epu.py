"""Baker-Bloom-Davis daily US Economic Policy Uncertainty index.

Signal is the latest reading entering the alert zone relative to its own
trailing 30-day mean (the raw daily series is noisy), plus a level alert.
"""
from __future__ import annotations

import csv
import datetime as dt
import io

from ..core import http
from ..core.base import Connector, Record, crossing_findings

CSV_URL = "https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv"


def parse_epu(text: str) -> tuple[Record, int]:
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            rows.append(
                (
                    dt.date(int(row["year"]), int(row["month"]), int(row["day"])),
                    float(row["daily_policy_index"]),
                )
            )
        except (KeyError, ValueError):
            continue
    date, value = rows[-1]
    trailing = [v for _, v in rows[-31:-1]]
    mean30 = sum(trailing) / len(trailing)
    ratio = value / mean30 if mean30 else 1.0
    record = Record(
        uid="epu:daily",
        source="epu",
        category="policy-uncertainty",
        ts=dt.datetime.combine(date, dt.time(0), tzinfo=dt.timezone.utc),
        title=f"US Economic Policy Uncertainty — {value:.0f} (30d mean {mean30:.0f})",
        url="https://www.policyuncertainty.com/",
        metrics={"epu": value, "mean30": mean30, "ratio": ratio},
        series=[v for _, v in rows[-90:]],
        series_name="EPU (US policy uncertainty)",
    )
    return record, len(rows)


class Epu(Connector):
    name = "epu"
    category = "policy-uncertainty"
    license_note = "Free academic data (Baker, Bloom & Davis); cite the authors."
    report_new = False

    def fetch(self) -> list[Record]:
        resp = http.get(CSV_URL, min_interval=5.0)
        record, _ = parse_epu(resp.text)
        return [record]

    def metric_findings(self, records, state, first_run):
        r = records[0]
        findings = crossing_findings(
            r,
            state,
            key="ratio",
            value=r.metrics["ratio"],
            alert_above=float(self.cfg.get("spike_ratio", 2.0)),
            reason_fmt="EPU spike: {value:.1f}x its 30-day mean (was {prev:.1f}x)",
            importance=3,
        )
        findings += crossing_findings(
            r,
            state,
            key="epu",
            value=r.metrics["epu"],
            alert_above=float(self.cfg.get("level_alert", 500.0)),
            reason_fmt="EPU level alert: daily index {prev:.0f} -> {value:.0f}",
            importance=4,
        )
        return findings
