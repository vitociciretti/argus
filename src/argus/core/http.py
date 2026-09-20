"""Polite HTTP: identified User-Agent, retries with backoff, per-host rate limit.

Every connector goes through get() — being a good citizen is what keeps free
sources free.
"""
from __future__ import annotations

import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "argus-osint/0.1 (+https://github.com/vitociciretti/argus)"

_session: requests.Session | None = None
_last_hit: dict[str, float] = {}


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        # GDELT-style sources allow ~1 request/5s: backoff must clear that window
        retry = Retry(
            total=3,
            backoff_factor=3.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.mount("http://", HTTPAdapter(max_retries=retry))
        _session = s
    return _session


def get(url: str, params=None, min_interval: float = 1.0, timeout: float = 60.0) -> requests.Response:
    host = urlparse(url).netloc
    wait = _last_hit.get(host, 0.0) + min_interval - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    resp = session().get(url, params=params, timeout=timeout)
    _last_hit[host] = time.monotonic()
    resp.raise_for_status()
    return resp
