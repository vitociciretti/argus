"""Nasdaq Reg SHO threshold list — securities with persistent fails-to-
deliver, a squeeze-risk flag. New symbols on the list are the signal.

v1 limitation: a symbol that leaves the list and returns months later won't
re-fire (uid is permanent). NYSE list is roadmap.
"""
from __future__ import annotations

import datetime as dt

from ..core import http
from ..core.base import Connector, Record

URL = "https://www.nasdaqtrader.com/dynamic/symdir/regsho/nasdaqth{ymd}.txt"


def parse_threshold(text: str, ts: dt.datetime) -> list[Record]:
    records = []
    for line in text.splitlines()[1:]:  # skip header
        parts = line.split("|")
        if len(parts) < 4 or not parts[0] or parts[0].startswith("Symbol"):
            continue
        symbol, name = parts[0].strip(), parts[1].strip()
        if not symbol or symbol.lower().startswith("total"):
            continue
        records.append(
            Record(
                uid=f"regsho:{symbol}",
                source="regsho_threshold",
                category="short-interest",
                ts=ts,
                title=f"{symbol} on Reg SHO threshold list — {name}",
                url="https://www.nasdaqtrader.com/trader.aspx?id=RegSHOThreshold",
                entities=[symbol, name],
            )
        )
    return records


class RegShoThreshold(Connector):
    name = "regsho_threshold"
    category = "short-interest"
    license_note = "Nasdaq Trader public symbol directory."
    new_importance = 3

    def fetch(self) -> list[Record]:
        day = dt.date.today()
        for _ in range(6):  # latest available settlement date
            try:
                resp = http.get(URL.format(ymd=day.strftime("%Y%m%d")))
                if resp.text.strip() and "Symbol" in resp.text[:200]:
                    ts = dt.datetime.combine(day, dt.time(0), tzinfo=dt.timezone.utc)
                    return parse_threshold(resp.text, ts)
            except Exception:
                pass
            day -= dt.timedelta(days=1)
        raise RuntimeError("no Reg SHO threshold file found in the last 6 days")
