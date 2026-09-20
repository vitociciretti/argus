"""Significant earthquakes from the USGS real-time GeoJSON feed. Finance
angle: fab regions, ports, cat-bond triggers, insurers."""
from __future__ import annotations

import datetime as dt

from ..core import http
from ..core.base import Connector, Finding, Record

FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"


def parse_quakes(payload: dict, min_mag: float) -> list[Record]:
    records = []
    for f in payload.get("features", []):
        props = f.get("properties", {})
        mag = props.get("mag") or 0.0
        if mag < min_mag:
            continue
        ts = dt.datetime.fromtimestamp((props.get("time") or 0) / 1000, tz=dt.timezone.utc)
        records.append(
            Record(
                uid=f"usgs:{f.get('id')}",
                source="usgs_quakes",
                category="nat-hazards",
                ts=ts,
                title=props.get("title", "?"),
                url=props.get("url", ""),
                entities=[props.get("place", "")],
                metrics={"magnitude": float(mag)},
            )
        )
    return records


class UsgsQuakes(Connector):
    name = "usgs_quakes"
    category = "nat-hazards"
    license_note = "US government work, public domain."

    def fetch(self) -> list[Record]:
        payload = http.get(FEED_URL).json()
        return parse_quakes(payload, float(self.cfg.get("min_magnitude", 6.0)))

    def finding_for_new(self, record: Record) -> Finding:
        mag = record.metrics.get("magnitude", 0)
        return Finding(record, f"M{mag:.1f} earthquake", 4 if mag >= 7.0 else 3)
