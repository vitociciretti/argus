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

_sessions: dict[bool, requests.Session] = {}
_last_hit: dict[str, float] = {}


def session(retries: bool = True) -> requests.Session:
    if retries not in _sessions:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        if retries:
            retry = Retry(
                total=3,
                backoff_factor=3.0,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET",),
            )
            s.mount("https://", HTTPAdapter(max_retries=retry))
            s.mount("http://", HTTPAdapter(max_retries=retry))
        _sessions[retries] = s
    return _sessions[retries]


def get(
    url: str,
    params=None,
    min_interval: float = 1.0,
    timeout: float = 60.0,
    retries: bool = True,
    headers: dict | None = None,
) -> requests.Response:
    """retries=False is for sources (GDELT) whose rate limiter counts each
    retry as a fresh violation and extends the penalty window — there,
    failing fast and succeeding on the next scheduled scan beats digging in.
    headers is for sources with UA requirements (SEC wants a contact email)."""
    host = urlparse(url).netloc
    wait = _last_hit.get(host, 0.0) + min_interval - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    resp = session(retries).get(url, params=params, timeout=timeout, headers=headers)
    _last_hit[host] = time.monotonic()
    resp.raise_for_status()
    return resp


def post_json(
    url: str,
    payload: dict,
    min_interval: float = 1.0,
    timeout: float = 60.0,
) -> requests.Response:
    """POST for read-only search APIs that take JSON bodies (USAspending)."""
    host = urlparse(url).netloc
    wait = _last_hit.get(host, 0.0) + min_interval - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    resp = session(retries=False).post(url, json=payload, timeout=timeout)
    _last_hit[host] = time.monotonic()
    resp.raise_for_status()
    return resp
