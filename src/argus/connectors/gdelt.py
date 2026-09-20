"""GDELT DOC 2.0 headline search on configurable watch terms. Headline flow
is context rather than signal, so findings carry low importance."""
from __future__ import annotations

import datetime as dt
import hashlib

from ..core import http
from ..core.base import Connector, Record, utcnow

DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
DEFAULT_QUERY = '("export controls" OR "new sanctions" OR "tariffs on") sourcelang:english'


def parse_articles(payload: dict) -> list[Record]:
    records = []
    for a in payload.get("articles", []):
        url = a.get("url", "")
        try:
            ts = dt.datetime.strptime(a.get("seendate", ""), "%Y%m%dT%H%M%SZ").replace(
                tzinfo=dt.timezone.utc
            )
        except ValueError:
            ts = utcnow()
        records.append(
            Record(
                uid="gdelt:" + hashlib.sha1(url.encode()).hexdigest()[:16],
                source="gdelt",
                category="news-events",
                ts=ts,
                title=a.get("title", ""),
                url=url,
                entities=[a.get("domain", "")],
                raw={"source_country": a.get("sourcecountry")},
            )
        )
    return records


class Gdelt(Connector):
    name = "gdelt"
    category = "news-events"
    license_note = "Free API; articles link to original publishers. Cite GDELT."
    new_importance = 1

    def fetch(self) -> list[Record]:
        params = {
            "query": self.cfg.get("query", DEFAULT_QUERY),
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(int(self.cfg.get("max_records", 40))),
            "timespan": self.cfg.get("timespan", "1d"),
            "sort": "datedesc",
        }
        resp = http.get(DOC_URL, params=params, min_interval=5.0)
        try:
            payload = resp.json()
        except ValueError:
            raise RuntimeError(f"GDELT returned non-JSON (bad query?): {resp.text[:200]}")
        return parse_articles(payload)
