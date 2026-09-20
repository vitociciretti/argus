"""Texas WARN notices via the state's Socrata open-data API (no key).

Legally mandated layoff pre-announcements — they hit this dataset before most
news coverage. Texas first because it's a top-2 state economy with a clean
API; more states are roadmap. Note: the dataset updates with a lag of weeks.
"""
from __future__ import annotations

import datetime as dt
import hashlib

from ..core import http
from ..core.base import Connector, Finding, Record

API_URL = "https://data.texas.gov/resource/8w53-c4f6.json"


def parse_notice(row: dict) -> Record | None:
    name = (row.get("job_site_name") or "").strip()
    if not name:
        return None
    try:
        total = int(float(row.get("total_layoff_number") or 0))
    except ValueError:
        total = 0
    notice_date = (row.get("notice_date") or "")[:10]
    try:
        ts = dt.datetime.fromisoformat(notice_date).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        ts = dt.datetime.now(dt.timezone.utc)
    key = f"{name}|{notice_date}|{row.get('layoff_date', '')}|{total}"
    uid = "warn_tx:" + hashlib.sha1(key.encode()).hexdigest()[:16]
    city = (row.get("city_name") or "").strip()
    return Record(
        uid=uid,
        source="warn_tx",
        category="labor",
        ts=ts,
        title=f"{name} — {total} layoffs ({city}, TX)",
        url="https://www.twc.texas.gov/data-reports/warn-act-listings",
        entities=[name],
        metrics={"layoffs": float(total)},
        raw={"county": row.get("county_name"), "layoff_date": row.get("layoff_date")},
    )


class WarnTx(Connector):
    name = "warn_tx"
    category = "labor"
    license_note = "Texas open data (Socrata), public record."
    new_importance = 3

    def fetch(self) -> list[Record]:
        params = {
            "$order": "notice_date DESC",
            "$limit": int(self.cfg.get("limit", 200)),
        }
        data = http.get(API_URL, params=params).json()
        min_layoffs = float(self.cfg.get("min_layoffs", 0))
        return [
            r
            for row in data
            if (r := parse_notice(row)) is not None and r.metrics["layoffs"] >= min_layoffs
        ]

    def finding_for_new(self, record: Record) -> Finding:
        big = record.metrics.get("layoffs", 0) >= float(self.cfg.get("big_layoff", 500))
        return Finding(record, "new WARN notice", 4 if big else 3)
