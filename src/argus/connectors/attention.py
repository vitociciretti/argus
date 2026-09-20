"""Attention proxies: Hacker News mentions of watch terms (Algolia API) and
Wikipedia pageview spikes on canary articles (Wikimedia REST API).

Wikipedia article views on pages like "Bank run" spiking to multiples of
their trailing mean is a documented retail-panic canary.
"""
from __future__ import annotations

import datetime as dt

from ..core import http
from ..core.base import Connector, Finding, Record, crossing_findings

HN_URL = "https://hn.algolia.com/api/v1/search_by_date"
WIKI_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia/all-access/user/{page}/daily/{start}/{end}"
)
DEFAULT_WIKI_PAGES = ["Bank_run", "Recession", "Stock_market_crash", "Hyperinflation"]


class HnMentions(Connector):
    name = "hn_mentions"
    category = "attention"
    license_note = "HN Algolia public search API."
    new_importance = 1

    def fetch(self) -> list[Record]:
        terms = self.cfg.get("terms") or [
            t for t in self.cfg.get("watchlist", {}).get("terms", [])
        ]
        records: dict[str, Record] = {}
        for term in terms[:8]:
            params = {"query": f'"{term}"', "tags": "story", "hitsPerPage": 25}
            payload = http.get(HN_URL, params=params, min_interval=1.0).json()
            for hit in payload.get("hits", []):
                oid = hit.get("objectID")
                if not oid or not hit.get("title"):
                    continue
                try:
                    ts = dt.datetime.fromisoformat(hit["created_at"].replace("Z", "+00:00"))
                except (KeyError, ValueError):
                    ts = dt.datetime.now(dt.timezone.utc)
                records[oid] = Record(
                    uid=f"hn:{oid}",
                    source="hn_mentions",
                    category="attention",
                    ts=ts,
                    title=hit["title"],
                    url=hit.get("url") or f"https://news.ycombinator.com/item?id={oid}",
                    entities=[term],
                    metrics={"points": float(hit.get("points") or 0)},
                )
        return list(records.values())

    def finding_for_new(self, record: Record) -> Finding:
        hot = record.metrics.get("points", 0) >= float(self.cfg.get("hot_points", 100))
        return Finding(record, f"HN mention ({record.entities[0]})", 2 if hot else 1)


class WikiPageviews(Connector):
    name = "wiki_pageviews"
    category = "attention"
    license_note = "Wikimedia public REST API."
    report_new = False

    def fetch(self) -> list[Record]:
        pages = self.cfg.get("pages", DEFAULT_WIKI_PAGES)
        end = dt.date.today() - dt.timedelta(days=1)
        start = end - dt.timedelta(days=40)
        records = []
        for page in pages:
            url = WIKI_URL.format(
                page=page, start=start.strftime("%Y%m%d00"), end=end.strftime("%Y%m%d00")
            )
            try:
                items = http.get(url, min_interval=0.5).json().get("items", [])
            except Exception:
                continue  # per-page gaps shouldn't kill the connector
            if len(items) < 20:
                continue
            views = [it["views"] for it in items]
            latest = views[-1]
            base = sum(views[:-1]) / len(views[:-1])
            ratio = latest / base if base else 1.0
            records.append(
                Record(
                    uid=f"wiki:{page}",
                    source="wiki_pageviews",
                    category="attention",
                    ts=dt.datetime.combine(end, dt.time(0), tzinfo=dt.timezone.utc),
                    title=f'Wikipedia "{page.replace("_", " ")}" — {latest:,} views/day '
                    f"({ratio:.1f}x its 40d mean)",
                    url=f"https://en.wikipedia.org/wiki/{page}",
                    metrics={"views": float(latest), "ratio": ratio},
                )
            )
        if not records:
            raise RuntimeError("no pageview series returned")
        return records

    def metric_findings(self, records, state, first_run):
        findings = []
        for r in records:
            findings += crossing_findings(
                r, state, "ratio", r.metrics["ratio"],
                alert_above=float(self.cfg.get("spike_ratio", 3.0)),
                reason_fmt="attention spike: {prev:.1f}x -> {value:.1f}x trailing mean",
                importance=3,
            )
        return findings
