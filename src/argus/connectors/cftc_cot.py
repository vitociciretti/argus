"""CFTC Commitments of Traders (legacy futures-only) via the CFTC's public
Socrata API. Weekly. Signal: week-over-week swings in net non-commercial
positioning as a share of open interest, on watched markets.
"""
from __future__ import annotations

import datetime as dt

from ..core import http
from ..core.base import Connector, Finding, Record

API_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
DEFAULT_MARKETS = [
    "GOLD", "SILVER", "COPPER", "WTI", "CRUDE OIL", "NATURAL GAS",
    "E-MINI S&P 500", "NASDAQ", "10-YEAR", "2-YEAR", "EURO FX", "JAPANESE YEN",
    "U.S. DOLLAR INDEX", "VIX",
]


def parse_report(rows: list[dict], keywords: list[str]) -> list[Record]:
    needles = [k.upper() for k in keywords]
    records = []
    for row in rows:
        name = row.get("market_and_exchange_names", "")
        if not any(n in name.upper() for n in needles):
            continue
        try:
            oi = float(row["open_interest_all"])
            net = float(row["noncomm_positions_long_all"]) - float(
                row["noncomm_positions_short_all"]
            )
        except (KeyError, TypeError, ValueError):
            continue
        if oi <= 0:
            continue
        net_pct = net / oi
        date = (row.get("report_date_as_yyyy_mm_dd") or "")[:10]
        try:
            ts = dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        records.append(
            Record(
                uid=f"cot:{row.get('cftc_contract_market_code', name).strip()}",
                source="cftc_cot",
                category="positioning",
                ts=ts,
                title=f"{name} — net spec {net_pct:+.0%} of OI",
                url="https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
                entities=[name.split(" - ")[0]],
                metrics={"net_pct_oi": net_pct, "open_interest": oi},
            )
        )
    return records


class CftcCot(Connector):
    name = "cftc_cot"
    category = "positioning"
    cadence = "weekly"
    license_note = "US government work, public domain; official Socrata API."
    report_new = False

    def fetch(self) -> list[Record]:
        params = {
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": 1500,  # roughly one full weekly report
        }
        rows = http.get(API_URL, params=params).json()
        latest = max((r.get("report_date_as_yyyy_mm_dd", "") for r in rows), default="")
        rows = [r for r in rows if r.get("report_date_as_yyyy_mm_dd") == latest]
        return parse_report(rows, self.cfg.get("markets", DEFAULT_MARKETS))

    def metric_findings(self, records, state, first_run):
        swing = float(self.cfg.get("swing_pp", 0.05))  # 5pp of OI in a week
        findings = []
        for r in records:
            net = r.metrics["net_pct_oi"]
            prev = state.get_metric(r.uid, "net_pct_oi")
            state.set_metric(r.uid, "net_pct_oi", net)
            if prev is None or abs(net - prev) < swing:
                continue
            findings.append(
                Finding(
                    r,
                    f"net spec positioning {prev:+.0%} -> {net:+.0%} of OI",
                    3,
                    extra={"from": (prev + 1) / 2, "to": (net + 1) / 2},  # map [-1,1] to bar
                )
            )
        return findings
