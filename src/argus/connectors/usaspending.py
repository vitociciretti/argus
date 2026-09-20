"""Large new US federal contract transactions via the USAspending API (no key).

Contract awards predate earnings visibility for defense/govtech names. Signal
is any transaction above the floor in the lookback window that we haven't
seen yet.
"""
from __future__ import annotations

import datetime as dt

from ..core import http
from ..core.base import Connector, Finding, Record

API_URL = "https://api.usaspending.gov/api/v2/search/spending_by_transaction/"


def parse_transaction(row: dict) -> Record | None:
    amount = float(row.get("Transaction Amount") or 0.0)
    recipient = (row.get("Recipient Name") or "").strip()
    if not recipient:
        return None
    action_date = row.get("Action Date") or ""
    try:
        ts = dt.datetime.fromisoformat(action_date).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        ts = dt.datetime.now(dt.timezone.utc)
    gid = row.get("generated_internal_id") or row.get("internal_id") or row.get("Award ID")
    return Record(
        uid=f"usaspending:{gid}:{action_date}",
        source="usaspending",
        category="gov-spending",
        ts=ts,
        title=f"{recipient} — ${amount / 1e6:,.0f}M ({row.get('Awarding Agency', '?')})",
        url="https://www.usaspending.gov/search",
        entities=[recipient],
        metrics={"amount": amount},
        raw={"award_id": row.get("Award ID")},
    )


class UsaSpending(Connector):
    name = "usaspending"
    category = "gov-spending"
    license_note = "US government work, public domain; official free API."
    new_importance = 3

    def fetch(self) -> list[Record]:
        today = dt.date.today()
        lookback = int(self.cfg.get("lookback_days", 7))
        payload = {
            "filters": {
                "time_period": [
                    {
                        "start_date": (today - dt.timedelta(days=lookback)).isoformat(),
                        "end_date": today.isoformat(),
                    }
                ],
                "award_type_codes": ["A", "B", "C", "D"],
            },
            "fields": [
                "Transaction Amount",
                "Awarding Agency",
                "Recipient Name",
                "Action Date",
                "Award ID",
                "generated_internal_id",
            ],
            "sort": "Transaction Amount",
            "order": "desc",
            "limit": int(self.cfg.get("limit", 60)),
        }
        data = http.post_json(API_URL, payload).json()
        min_amount = float(self.cfg.get("min_amount", 50e6))
        return [
            r
            for row in data.get("results", [])
            if (r := parse_transaction(row)) is not None and r.metrics["amount"] >= min_amount
        ]

    def finding_for_new(self, record: Record) -> Finding:
        huge = record.metrics.get("amount", 0) >= float(self.cfg.get("huge_amount", 250e6))
        return Finding(record, "new large contract transaction", 4 if huge else 3)
