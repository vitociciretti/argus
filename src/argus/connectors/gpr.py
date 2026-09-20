"""Caldara & Iacoviello daily Geopolitical Risk Index (GPR).

The published .xls already carries 7- and 30-day moving averages. Signal is
the MA7/MA30 ratio *entering* the spike zone, plus outright level alerts —
crossing-based so a sustained crisis doesn't re-fire every day.
"""
from __future__ import annotations

import datetime as dt
import io

import pandas as pd

from ..core import http
from ..core.base import Connector, Record, crossing_findings

XLS_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"


def parse_gpr(content: bytes) -> tuple[Record, int]:
    df = pd.read_excel(io.BytesIO(content))
    df = df.dropna(subset=["GPRD"])
    last = df.iloc[-1]
    ts = dt.datetime.combine(
        pd.Timestamp(last["date"]).date(), dt.time(0), tzinfo=dt.timezone.utc
    )
    ratio = float(last["GPRD_MA7"]) / float(last["GPRD_MA30"])
    record = Record(
        uid="gpr:daily",
        source="gpr",
        category="geopolitical-risk",
        ts=ts,
        title=f"Geopolitical Risk Index — GPRD {last['GPRD']:.0f} "
        f"(MA7 {last['GPRD_MA7']:.0f} / MA30 {last['GPRD_MA30']:.0f})",
        url="https://www.matteoiacoviello.com/gpr.htm",
        metrics={
            "gprd": float(last["GPRD"]),
            "ma7": float(last["GPRD_MA7"]),
            "ma30": float(last["GPRD_MA30"]),
            "ratio": ratio,
        },
        series=[float(v) for v in df["GPRD"].tail(90)],
        series_name="GPR (geopolitical risk)",
    )
    return record, len(df)


class Gpr(Connector):
    name = "gpr"
    category = "geopolitical-risk"
    cadence = "daily"
    license_note = "Free academic data (Caldara & Iacoviello); cite the authors."
    report_new = False

    def fetch(self) -> list[Record]:
        resp = http.get(XLS_URL, min_interval=5.0)
        record, self._n_rows = parse_gpr(resp.content)
        return [record]

    def metric_findings(self, records, state, first_run):
        r = records[0]
        findings = crossing_findings(
            r,
            state,
            key="ratio",
            value=r.metrics["ratio"],
            alert_above=float(self.cfg.get("spike_ratio", 1.4)),
            reason_fmt="GPR momentum spike: MA7/MA30 ratio {prev:.2f} -> {value:.2f}",
            importance=4,
        )
        findings += crossing_findings(
            r,
            state,
            key="gprd",
            value=r.metrics["gprd"],
            alert_above=float(self.cfg.get("level_alert", 250.0)),
            reason_fmt="GPR level alert: daily index {prev:.0f} -> {value:.0f}",
            importance=4,
        )
        return findings
