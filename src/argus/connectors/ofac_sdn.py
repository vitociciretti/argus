"""OFAC SDN list — new designations only. The list is ~17k rows; the first
run seeds them silently and every later run reports just the additions."""
from __future__ import annotations

import csv
import io

from ..core import http
from ..core.base import Connector, Record, utcnow

SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"


def parse_sdn_csv(text: str) -> list[Record]:
    records = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 4 or not row[0].strip().isdigit():
            continue
        ent_num = row[0].strip()
        name = row[1].strip()
        sdn_type = row[2].strip() or "entity"
        programs = row[3].strip()
        records.append(
            Record(
                uid=f"ofac:{ent_num}",
                source="ofac_sdn",
                category="sanctions",
                ts=utcnow(),
                title=f"{name} [{sdn_type}] - {programs}",
                url="https://sanctionssearch.ofac.treas.gov/",
                entities=[name],
                raw={"programs": programs, "sdn_type": sdn_type},
            )
        )
    return records


class OfacSdn(Connector):
    name = "ofac_sdn"
    category = "sanctions"
    license_note = "US government work, public domain."
    new_importance = 4

    def fetch(self) -> list[Record]:
        resp = http.get(SDN_URL, min_interval=2.0)
        return parse_sdn_csv(resp.content.decode("latin-1", errors="replace"))
