"""New rules and proposed rules from financial regulators, via the Federal
Register's official free API. New documents are the signal."""
from __future__ import annotations

import datetime as dt

from ..core import http
from ..core.base import Connector, Record

API_URL = "https://www.federalregister.gov/api/v1/documents.json"

DEFAULT_AGENCIES = [
    "securities-and-exchange-commission",
    "commodity-futures-trading-commission",
    "treasury-department",
    "federal-reserve-system",
    "foreign-assets-control-office",
]
DEFAULT_TYPES = ["RULE", "PRORULE"]


def parse_document(doc: dict) -> Record:
    agencies = [a.get("name", "") for a in doc.get("agencies", []) if isinstance(a, dict)]
    ts = dt.datetime.fromisoformat(doc["publication_date"]).replace(tzinfo=dt.timezone.utc)
    return Record(
        uid=f"fedreg:{doc['document_number']}",
        source="federal_register",
        category="regulatory",
        ts=ts,
        title=doc.get("title", ""),
        url=doc.get("html_url", ""),
        entities=agencies,
        raw={"type": doc.get("type")},
    )


class FederalRegister(Connector):
    name = "federal_register"
    category = "regulatory"
    license_note = "US government work, public domain; official free API."
    new_importance = 3

    def fetch(self) -> list[Record]:
        params: list[tuple[str, str]] = [("per_page", "50"), ("order", "newest")]
        for agency in self.cfg.get("agencies", DEFAULT_AGENCIES):
            params.append(("conditions[agencies][]", agency))
        for doc_type in self.cfg.get("types", DEFAULT_TYPES):
            params.append(("conditions[type][]", doc_type))
        data = http.get(API_URL, params=params).json()
        return [parse_document(d) for d in data.get("results", [])]
