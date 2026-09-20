"""Polymarket top markets via the public Gamma API (read-only, no key).

Signal is probability *moves*, not market existence — markets rotating into
the top-volume window are not news, so report_new is off.
"""
from __future__ import annotations

import json
import re

from ..core import http
from ..core.base import Connector, Record, probability_move_findings, utcnow

GAMMA_URL = "https://gamma-api.polymarket.com/markets"

# Top-by-volume is dominated by live sports/esports: league-prefixed slugs,
# plus daily fixtures which always embed the match date (political/macro
# markets don't). Heuristic, overridable via cfg["exclude_slug_pattern"].
SPORTS_SLUG = re.compile(
    r"^(nfl|nba|mlb|nhl|mls|cfb|cbb|epl|fl1|lal|ser|bun|lig|ucl|uel|atp|wta|"
    r"dota2|cs2|lol|val|f1|ufc|box|nascar)-"
    r"|-\d{4}-\d{2}-\d{2}(-|$)"
)


def parse_market(m: dict) -> Record | None:
    try:
        prices = json.loads(m.get("outcomePrices") or "[]")
        outcomes = json.loads(m.get("outcomes") or "[]")
    except (json.JSONDecodeError, TypeError):
        return None
    if not prices:
        return None
    idx = outcomes.index("Yes") if "Yes" in outcomes else 0
    return Record(
        uid=f"polymarket:{m['id']}",
        source="polymarket",
        category="prediction-markets",
        ts=utcnow(),
        title=m.get("question") or m.get("slug", "?"),
        url=f"https://polymarket.com/market/{m.get('slug', '')}",
        metrics={
            "probability": float(prices[idx]),
            "volume_24h": float(m.get("volume24hr") or 0.0),
        },
        raw={"end_date": m.get("endDate"), "liquidity": m.get("liquidity")},
    )


class Polymarket(Connector):
    name = "polymarket"
    category = "prediction-markets"
    license_note = "Public Gamma API, read-only, no key required."
    report_new = False

    def fetch(self) -> list[Record]:
        params = {
            "closed": "false",
            "limit": int(self.cfg.get("limit", 100)),
            "order": "volume24hr",
            "ascending": "false",
        }
        data = http.get(GAMMA_URL, params=params).json()
        pattern = self.cfg.get("exclude_slug_pattern")
        exclude = re.compile(pattern) if pattern else SPORTS_SLUG
        return [
            r
            for m in data
            if not exclude.search(m.get("slug") or "")
            and (r := parse_market(m)) is not None
        ]

    def metric_findings(self, records, state, first_run):
        return probability_move_findings(
            records,
            state,
            threshold=float(self.cfg.get("move_threshold", 0.05)),
            min_volume=float(self.cfg.get("min_volume_24h", 10_000)),
        )
