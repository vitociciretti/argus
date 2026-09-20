"""New SCHEDULE 13D/13G filings (activist and 5% stakes) from EDGAR's daily
form index, plus Form 4 insider filings for explicitly watched companies.

The daily .idx is sturdier than full-text search: one plain-text file per
business day listing every filing by form type. ~35 13Ds and ~900 Form 4s
per day, which is why Form 4 is watchlist-only.
"""
from __future__ import annotations

import datetime as dt
import re

from ..core import http
from ..core.base import Connector, Finding, Record

IDX_URL = "https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{q}/form.{ymd}.idx"
LINE_RE = re.compile(r"^(?P<form>.{1,18}?)\s{2,}(?P<company>.+?)\s{2,}(?P<cik>\d+)\s+(?P<date>\d{8})\s+(?P<file>\S+)\s*$")
STAKE_FORMS = ("SCHEDULE 13D", "SCHEDULE 13G")


def parse_idx(text: str, form4_companies: list[str]) -> list[Record]:
    needles = [c.lower() for c in form4_companies]
    records = []
    for line in text.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        form = m["form"].strip()
        company = m["company"].strip()
        is_stake = any(form.startswith(f) for f in STAKE_FORMS)
        is_form4 = form in ("4", "4/A") and any(n in company.lower() for n in needles)
        if not (is_stake or is_form4):
            continue
        accession = m["file"].rsplit("/", 1)[-1].removesuffix(".txt")
        ts = dt.datetime.strptime(m["date"], "%Y%m%d").replace(tzinfo=dt.timezone.utc)
        records.append(
            Record(
                uid=f"edgar:{accession}:{m['cik']}",
                source="edgar_ownership",
                category="ownership",
                ts=ts,
                title=f"{form}: {company}",
                url=f"https://www.sec.gov/Archives/{m['file']}",
                entities=[company],
                raw={"form": form, "cik": m["cik"]},
            )
        )
    return records


class EdgarOwnership(Connector):
    name = "edgar_ownership"
    category = "ownership"
    license_note = "US government work, public domain; respect SEC fair-access (declared UA, <=10 req/s)."

    def fetch(self) -> list[Record]:
        form4_companies = self.cfg.get("form4_companies", [])
        records: dict[str, Record] = {}
        found_days = 0
        day = dt.date.today()
        for _ in range(8):  # walk back over weekends/holidays
            url = IDX_URL.format(year=day.year, q=(day.month - 1) // 3 + 1, ymd=day.strftime("%Y%m%d"))
            try:
                text = http.get(url, min_interval=0.5).text
            except Exception:
                day -= dt.timedelta(days=1)
                continue
            for r in parse_idx(text, form4_companies):
                records[r.uid] = r
            found_days += 1
            if found_days >= int(self.cfg.get("days", 2)):
                break
            day -= dt.timedelta(days=1)
        return list(records.values())

    def finding_for_new(self, record: Record) -> Finding:
        form = record.raw.get("form", "")
        if form == "SCHEDULE 13D":
            return Finding(record, "new activist stake filing", 4)
        if form.startswith("SCHEDULE 13D"):
            return Finding(record, "13D amendment", 3)
        if form.startswith("SCHEDULE 13G"):
            return Finding(record, "new/amended passive 5% stake", 2)
        return Finding(record, "insider Form 4 (watched company)", 3)
