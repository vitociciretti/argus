"""US dollar-liquidity plumbing: NY Fed overnight reverse repo (RRP) and the
Treasury General Account (TGA), both keyless official APIs.

Signals: threshold crossings (RRP drained / refilling, TGA below floor) and
large day-over-day moves — the drain/rebuild dynamics that move front-end
rates and risk assets.
"""
from __future__ import annotations

import datetime as dt

from ..core import http
from ..core.base import Connector, Finding, Record, crossing_findings

RRP_URL = "https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json"
TGA_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    "/v1/accounting/dts/operating_cash_balance"
)


def _move_finding(record: Record, state, key: str, value: float, alert: float,
                  label: str) -> list[Finding]:
    prev = state.get_metric(record.uid, key)
    state.set_metric(record.uid, key, value)
    if prev is None or abs(value - prev) < alert:
        return []
    return [Finding(record, f"{label}: ${prev:,.0f}bn -> ${value:,.0f}bn", 3)]


class NyFedRrp(Connector):
    name = "nyfed_rrp"
    category = "liquidity"
    license_note = "NY Fed public markets API."
    report_new = False

    def fetch(self) -> list[Record]:
        start = (dt.date.today() - dt.timedelta(days=15)).isoformat()
        data = http.get(RRP_URL, params={"startDate": start}).json()
        ops = data.get("repo", {}).get("operations", [])
        ops = [o for o in ops if o.get("operationType") == "Reverse Repo" and o.get("totalAmtAccepted") is not None]
        if not ops:
            raise RuntimeError("no RRP operations returned")
        latest = max(ops, key=lambda o: o["operationDate"])
        bn = float(latest["totalAmtAccepted"]) / 1e9
        ts = dt.datetime.fromisoformat(latest["operationDate"]).replace(tzinfo=dt.timezone.utc)
        return [
            Record(
                uid="rrp:daily",
                source="nyfed_rrp",
                category="liquidity",
                ts=ts,
                title=f"Fed overnight RRP — ${bn:,.0f}bn accepted",
                url="https://www.newyorkfed.org/markets/desk-operations/reverse-repo",
                metrics={"rrp_bn": bn},
            )
        ]

    def metric_findings(self, records, state, first_run):
        r = records[0]
        bn = r.metrics["rrp_bn"]
        findings = crossing_findings(
            r, state, "rrp_low", bn,
            alert_below=float(self.cfg.get("low_alert_bn", 25.0)),
            reason_fmt="RRP effectively drained: ${prev:,.0f}bn -> ${value:,.0f}bn",
            importance=4,
        )
        findings += crossing_findings(
            r, state, "rrp_high", bn,
            alert_above=float(self.cfg.get("high_alert_bn", 400.0)),
            reason_fmt="RRP refilling: ${prev:,.0f}bn -> ${value:,.0f}bn",
            importance=3,
        )
        findings += _move_finding(
            r, state, "rrp_bn", bn,
            alert=float(self.cfg.get("move_alert_bn", 100.0)),
            label="RRP day move",
        )
        return findings


class TreasuryTga(Connector):
    name = "treasury_tga"
    category = "liquidity"
    license_note = "US Treasury Fiscal Data API, public domain."
    report_new = False

    def fetch(self) -> list[Record]:
        params = {"sort": "-record_date", "page[size]": 4}
        data = http.get(TGA_URL, params=params).json()
        rows = [r for r in data.get("data", []) if "Opening Balance" in r.get("account_type", "")]
        if not rows:
            raise RuntimeError("no TGA opening-balance rows returned")
        latest = rows[0]
        bn = float(latest["open_today_bal"]) / 1000.0  # reported in $mn
        ts = dt.datetime.fromisoformat(latest["record_date"]).replace(tzinfo=dt.timezone.utc)
        return [
            Record(
                uid="tga:daily",
                source="treasury_tga",
                category="liquidity",
                ts=ts,
                title=f"Treasury General Account — ${bn:,.0f}bn",
                url="https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/",
                metrics={"tga_bn": bn},
            )
        ]

    def metric_findings(self, records, state, first_run):
        r = records[0]
        bn = r.metrics["tga_bn"]
        findings = crossing_findings(
            r, state, "tga_low", bn,
            alert_below=float(self.cfg.get("low_alert_bn", 300.0)),
            reason_fmt="TGA below floor: ${prev:,.0f}bn -> ${value:,.0f}bn",
            importance=4,
        )
        findings += _move_finding(
            r, state, "tga_bn", bn,
            alert=float(self.cfg.get("move_alert_bn", 75.0)),
            label="TGA day move",
        )
        return findings
