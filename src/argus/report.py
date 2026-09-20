"""Render scan results into the daily markdown report.

House rules: deltas only, importance-sorted, watchlist hits pulled to the
top, quiet sources say so in exactly one line, and source health is always
shown — a report that is honestly empty on quiet days is one you keep reading.
"""
from __future__ import annotations

import re

from .core.base import Finding, ScanResult

CATEGORY_ORDER = ["sanctions", "regulatory", "prediction-markets", "news-events"]
LOW_IMPORTANCE_CAP = 10
WATCHLIST_KEYS = ("tickers", "countries", "commodities", "terms")


def watchlist_terms(config: dict) -> list[str]:
    wl = config.get("watchlist", {})
    return [t for key in WATCHLIST_KEYS for t in wl.get(key, [])]


def matches(finding: Finding, terms: list[str]) -> list[str]:
    hay = f"{finding.record.title} {' '.join(finding.record.entities)}".lower()
    return [t for t in terms if re.search(rf"\b{re.escape(t.lower())}\b", hay)]


def apply_watchlist(results: list[ScanResult], terms: list[str]) -> None:
    """Tag findings that mention a watchlist term and bump their importance."""
    if not terms:
        return
    for result in results:
        for f in result.findings:
            hit = matches(f, terms)
            if hit:
                f.watchlist = hit
                f.importance = min(5, f.importance + 1)


def _bullet(f: Finding) -> str:
    tag = f" *(watchlist: {', '.join(f.watchlist)})*" if f.watchlist else ""
    link = f" — [link]({f.record.url})" if f.record.url else ""
    return f"- **[{f.importance}]** {f.record.title}{tag}\n  {f.reason}{link}"


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (-f.importance, -f.record.ts.timestamp()))


_sorted = sort_findings


def render(
    results: list[ScanResult],
    failures: list[tuple[str, Exception]],
    date_str: str,
) -> str:
    all_findings = [f for r in results for f in r.findings]
    watch_hits = _sorted([f for f in all_findings if f.watchlist])

    lines = [
        f"# argus daily report — {date_str}",
        "",
        f"_{len(results) + len(failures)} sources scanned · {len(all_findings)} findings · "
        f"{len(watch_hits)} watchlist hits · {len(failures)} failures_",
        "",
    ]

    if watch_hits:
        lines.append("## Watchlist hits")
        lines.extend(_bullet(f) for f in watch_hits)
        lines.append("")

    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    for result in sorted(results, key=lambda r: (order.get(r.category, 99), r.source)):
        lines.append(f"## {result.category} ({result.source})")
        if result.first_run:
            lines.append(
                f"_first run — baseline of {result.n_records} records seeded; "
                f"deltas start next scan_"
            )
            lines.append("")
            continue
        findings = _sorted([f for f in result.findings if not f.watchlist])
        if not findings:
            if any(f.watchlist for f in result.findings):
                lines.append("_all findings shown under watchlist hits_")
            else:
                lines.append("_quiet — no changes_")
        else:
            high = [f for f in findings if f.importance >= 3]
            low = [f for f in findings if f.importance <= 2]
            lines.extend(_bullet(f) for f in high + low[:LOW_IMPORTANCE_CAP])
            hidden = len(low) - min(len(low), LOW_IMPORTANCE_CAP)
            if hidden:
                lines.append(f"- _+{hidden} more low-importance items not shown_")
        lines.append("")

    lines.append("## Source health")
    for result in sorted(results, key=lambda r: r.source):
        if result.n_records == 0:
            lines.append(f"- {result.source}: WARNING — fetch returned 0 records")
        else:
            lines.append(f"- {result.source}: ok ({result.n_records} records)")
    for name, exc in failures:
        lines.append(f"- {name}: FAILED — {exc}")
    lines.append("")
    return "\n".join(lines)
