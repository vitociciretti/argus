"""US drug recalls from openFDA enforcement reports (keyless tier). Class I
recalls (serious harm risk) are the market-moving ones."""
from __future__ import annotations

import datetime as dt

from ..core import http
from ..core.base import Connector, Finding, Record

API_URL = "https://api.fda.gov/drug/enforcement.json"


def parse_recalls(payload: dict) -> list[Record]:
    records = []
    for r in payload.get("results", []):
        recall_no = r.get("recall_number")
        if not recall_no:
            continue
        try:
            ts = dt.datetime.strptime(r.get("report_date", ""), "%Y%m%d").replace(
                tzinfo=dt.timezone.utc
            )
        except ValueError:
            ts = dt.datetime.now(dt.timezone.utc)
        firm = (r.get("recalling_firm") or "?").strip()
        classification = r.get("classification", "?")
        product = (r.get("product_description") or "?")[:110]
        records.append(
            Record(
                uid=f"fda:{recall_no}",
                source="openfda_recalls",
                category="biotech",
                ts=ts,
                title=f"{firm}: {product} ({classification})",
                url="https://www.accessdata.fda.gov/scripts/ires/index.cfm",
                entities=[firm],
                raw={"classification": classification, "reason": (r.get("reason_for_recall") or "")[:200]},
            )
        )
    return records


class OpenFdaRecalls(Connector):
    name = "openfda_recalls"
    category = "biotech"
    license_note = "openFDA public data; keyless tier is rate-limited."

    def fetch(self) -> list[Record]:
        params = {"sort": "report_date:desc", "limit": int(self.cfg.get("limit", 100))}
        payload = http.get(API_URL, params=params, min_interval=2.0).json()
        return parse_recalls(payload)

    def finding_for_new(self, record: Record) -> Finding:
        cls = record.raw.get("classification", "")
        importance = {"Class I": 4, "Class II": 2}.get(cls, 1)
        return Finding(record, f"new drug recall ({cls})", importance)
