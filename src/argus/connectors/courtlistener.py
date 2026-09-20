"""New federal dockets matching watch queries, via CourtListener search
(free; anonymous works at low volume, optional api_token raises the limits).

Litigation early warning: securities fraud suits, cases naming watched
companies, etc. Queries are configurable; watchlist tickers/entities can be
folded in via config.
"""
from __future__ import annotations

import datetime as dt

from ..core import http
from ..core.base import Connector, Record

SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"
DEFAULT_QUERIES = ['"securities fraud"']


def parse_docket(row: dict, query: str) -> Record | None:
    docket_id = row.get("docket_id")
    if docket_id is None:
        return None
    filed = row.get("dateFiled") or ""
    try:
        ts = dt.datetime.fromisoformat(filed).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        ts = dt.datetime.now(dt.timezone.utc)
    return Record(
        uid=f"courtlistener:{docket_id}",
        source="courtlistener",
        category="legal",
        ts=ts,
        title=f"{row.get('caseName', '?')} ({row.get('court', '?')})",
        url="https://www.courtlistener.com" + (row.get("docket_absolute_url") or ""),
        entities=[p for p in (row.get("party") or []) if isinstance(p, str)][:6],
        raw={"docket_number": row.get("docketNumber"), "query": query},
    )


class CourtListener(Connector):
    name = "courtlistener"
    category = "legal"
    license_note = "Free Law Project; free API, optional token raises rate limits."
    new_importance = 3

    def fetch(self) -> list[Record]:
        token = self.cfg.get("api_token")
        if token:
            http.session().headers["Authorization"] = f"Token {token}"
        records: dict[str, Record] = {}
        for query in self.cfg.get("queries", DEFAULT_QUERIES):
            params = {"type": "d", "q": query, "order_by": "dateFiled desc"}
            data = http.get(SEARCH_URL, params=params, min_interval=2.0).json()
            for row in data.get("results", []):
                r = parse_docket(row, query)
                if r is not None:
                    records[r.uid] = r
        return list(records.values())
