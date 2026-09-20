"""UK disclosed net short positions (>=0.5%) from the FCA's daily workbook.

Signal: new (holder, issuer) pairs — a fund initiating a disclosable short —
and meaningful size changes on existing ones.
"""
from __future__ import annotations

import io

import pandas as pd

from ..core import http
from ..core.base import Connector, Finding, Record, utcnow

XLSX_URL = "https://www.fca.org.uk/publication/data/short-positions-daily-update.xlsx"


def _col(df: pd.DataFrame, needle: str) -> str:
    for c in df.columns:
        if needle.lower() in str(c).lower():
            return c
    raise KeyError(f"no column matching {needle!r} in {list(df.columns)}")


def parse_fca(content: bytes) -> list[Record]:
    """The workbook lists the full disclosure history per (holder, issuer).
    The latest row per pair is the current position — collapse to that."""
    df = pd.read_excel(io.BytesIO(content), sheet_name=0, engine="openpyxl")
    holder_c = _col(df, "holder")
    issuer_c = _col(df, "issuer")
    pct_c = _col(df, "net short position")
    isin_c = _col(df, "isin")
    date_c = _col(df, "position date")
    df = df.dropna(subset=[holder_c, isin_c])
    df = df.sort_values(date_c).groupby([holder_c, isin_c], as_index=False).last()
    records = []
    for _, row in df.iterrows():
        holder, issuer = str(row[holder_c]).strip(), str(row[issuer_c]).strip()
        if not holder or holder == "nan":
            continue
        try:
            pct = float(row[pct_c])
        except (TypeError, ValueError):
            continue
        uid = f"fca:{row[isin_c]}|{holder.lower()}"
        records.append(
            Record(
                uid=uid,
                source="fca_shorts",
                category="short-interest",
                ts=utcnow(),
                title=f"{holder} short {pct:.2f}% of {issuer}",
                url="https://www.fca.org.uk/markets/short-selling/notification-disclosure-net-short-positions",
                entities=[holder, issuer],
                metrics={"pct": pct},
                raw={"position_date": str(row[date_c])[:10]},
            )
        )
    return records


class FcaShorts(Connector):
    name = "fca_shorts"
    category = "short-interest"
    license_note = "FCA public disclosure data."

    def fetch(self) -> list[Record]:
        resp = http.get(XLSX_URL, min_interval=5.0)
        return parse_fca(resp.content)

    def finding_for_new(self, record: Record) -> Finding:
        pct = record.metrics.get("pct", 0)
        big = pct >= float(self.cfg.get("big_pct", 1.0))
        return Finding(record, "new disclosed short position", 3 if big else 2)

    def scan(self, state):  # closed positions (0%) aren't news as "new" pairs
        result = super().scan(state)
        result.findings = [
            f for f in result.findings
            if not (f.reason == "new disclosed short position" and f.record.metrics.get("pct", 0) < 0.5)
        ]
        return result

    def metric_findings(self, records, state, first_run):
        step = float(self.cfg.get("change_pp", 0.2))
        findings = []
        for r in records:
            pct = r.metrics["pct"]
            prev = state.get_metric(r.uid, "pct")
            state.set_metric(r.uid, "pct", pct)
            if prev is None or abs(pct - prev) < step:
                continue
            direction = "increased" if pct > prev else "reduced"
            findings.append(
                Finding(r, f"short {direction}: {prev:.2f}% -> {pct:.2f}%", 2,
                        extra={"from": prev / 100, "to": pct / 100})
            )
        return findings
