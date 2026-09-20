"""Certificate transparency via crt.sh: new TLS certificates on watched
domains reveal unannounced subdomains (products, subsidiaries, deal sites).

Requires [crtsh] domains in argus.toml — skipped otherwise. crt.sh is slow
and flaky; failures show in source health and resolve on the next scan.
"""
from __future__ import annotations

import datetime as dt

from ..core import http
from ..core.base import ConfigSkip, Connector, Record

API_URL = "https://crt.sh/"


def parse_certs(payload: list, domain: str, since: dt.datetime) -> list[Record]:
    records = {}
    for cert in payload:
        try:
            ts = dt.datetime.fromisoformat(cert["entry_timestamp"]).replace(
                tzinfo=dt.timezone.utc
            )
        except (KeyError, ValueError):
            continue
        if ts < since:
            continue
        names = sorted(set((cert.get("name_value") or "").splitlines()))
        key = "|".join(names)
        records[key] = Record(
            uid=f"crtsh:{cert.get('id')}",
            source="crtsh",
            category="web-footprint",
            ts=ts,
            title=f"{domain}: new cert for {', '.join(names)[:100]}",
            url=f"https://crt.sh/?q={domain}",
            entities=[domain],
            raw={"names": names, "issuer": cert.get("issuer_name", "")[:80]},
        )
    return list(records.values())


class CrtSh(Connector):
    name = "crtsh"
    category = "web-footprint"
    license_note = "crt.sh (Sectigo) public CT log search."
    new_importance = 2

    def fetch(self) -> list[Record]:
        domains = self.cfg.get("domains", [])
        if not domains:
            raise ConfigSkip("set [crtsh] domains in argus.toml to enable")
        since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            days=int(self.cfg.get("window_days", 30))
        )
        records = []
        for domain in domains[:10]:
            payload = http.get(
                API_URL,
                params={"q": f"%.{domain}", "output": "json"},
                min_interval=5.0,
                timeout=90.0,
                retries=False,
            ).json()
            records.extend(parse_certs(payload, domain, since))
        return records
