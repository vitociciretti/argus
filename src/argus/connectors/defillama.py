"""DeFi protocol TVL moves via the free DefiLlama API. Signal: large TVL
swings on major protocols between scans (own-delta, not their change_1d, so
double runs in a day don't re-fire)."""
from __future__ import annotations

from ..core import http
from ..core.base import Connector, Finding, Record, utcnow

API_URL = "https://api.llama.fi/protocols"


def parse_protocols(payload: list, min_tvl: float, top: int) -> list[Record]:
    rows = [p for p in payload if (p.get("tvl") or 0) >= min_tvl and p.get("slug")]
    rows.sort(key=lambda p: -(p.get("tvl") or 0))
    records = []
    for p in rows[:top]:
        records.append(
            Record(
                uid=f"llama:{p['slug']}",
                source="defillama",
                category="crypto",
                ts=utcnow(),
                title=f"{p.get('name', p['slug'])} — TVL ${p['tvl'] / 1e9:.2f}bn",
                url=f"https://defillama.com/protocol/{p['slug']}",
                entities=[p.get("name", p["slug"])],
                metrics={"tvl": float(p["tvl"])},
                raw={"chain": p.get("chain"), "category": p.get("category")},
            )
        )
    return records


class DefiLlama(Connector):
    name = "defillama"
    category = "crypto"
    license_note = "DefiLlama open API, free."
    report_new = False

    def fetch(self) -> list[Record]:
        payload = http.get(API_URL).json()
        return parse_protocols(
            payload,
            min_tvl=float(self.cfg.get("min_tvl", 100e6)),
            top=int(self.cfg.get("top", 100)),
        )

    def metric_findings(self, records, state, first_run):
        threshold = float(self.cfg.get("move_pct", 0.20))
        findings = []
        for r in records:
            tvl = r.metrics["tvl"]
            prev = state.get_metric(r.uid, "tvl")
            state.set_metric(r.uid, "tvl", tvl)
            if prev is None or prev <= 0:
                continue
            change = tvl / prev - 1
            if abs(change) >= threshold:
                findings.append(
                    Finding(
                        r,
                        f"TVL {change:+.0%}: ${prev / 1e9:.2f}bn -> ${tvl / 1e9:.2f}bn",
                        4 if change <= -0.35 else 3,  # crashes are often exploits
                    )
                )
        return findings
