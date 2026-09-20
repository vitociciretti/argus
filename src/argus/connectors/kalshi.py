"""Kalshi markets via the public events endpoint (read-only, no key).

CFTC-regulated, so its macro-event coverage (CPI prints, Fed decisions,
shutdowns) is deeper than Polymarket's. Events carry a category field, which
gives clean sports/entertainment filtering. Signal is probability moves.
"""
from __future__ import annotations

from ..core import http
from ..core.base import Connector, Record, probability_move_findings, utcnow

EVENTS_URL = "https://api.elections.kalshi.com/trade-api/v2/events"
EXCLUDED_CATEGORIES = {"Sports", "Entertainment", "Social"}


def parse_event_markets(event: dict) -> list[Record]:
    records = []
    for m in event.get("markets", []):
        if m.get("status") != "active":
            continue
        try:
            prob = float(m.get("last_price_dollars") or 0.0)
            volume = float(m.get("volume_24h_fp") or 0.0)
        except (TypeError, ValueError):
            continue
        sub = m.get("yes_sub_title") or ""
        title = event.get("title", "?") + (f" — {sub}" if sub else "")
        records.append(
            Record(
                uid=f"kalshi:{m['ticker']}",
                source="kalshi",
                category="prediction-markets",
                ts=utcnow(),
                title=title,
                url=f"https://kalshi.com/markets/{m.get('event_ticker', '')}",
                entities=[event.get("category", "")],
                metrics={"probability": prob, "volume_24h": volume},
                raw={"kalshi_category": event.get("category"), "close_time": m.get("close_time")},
            )
        )
    return records


class Kalshi(Connector):
    name = "kalshi"
    category = "prediction-markets"
    license_note = "Public read-only API, no key; CFTC-regulated exchange."
    report_new = False

    def fetch(self) -> list[Record]:
        excluded = set(self.cfg.get("exclude_categories", EXCLUDED_CATEGORIES))
        params = {"limit": 200, "status": "open", "with_nested_markets": "true"}
        data = http.get(EVENTS_URL, params=params).json()
        records = [
            r
            for event in data.get("events", [])
            if event.get("category") not in excluded
            for r in parse_event_markets(event)
        ]
        records.sort(key=lambda r: -r.metrics["volume_24h"])
        return records[: int(self.cfg.get("limit", 150))]

    def metric_findings(self, records, state, first_run):
        return probability_move_findings(
            records,
            state,
            threshold=float(self.cfg.get("move_threshold", 0.05)),
            min_volume=float(self.cfg.get("min_volume_24h", 500)),
        )
