"""Render scan results into the daily markdown report.

House rules: deltas only, importance-sorted, watchlist hits pulled to the
top, quiet sources say so in exactly one line, and source health is always
shown — a report that is honestly empty on quiet days is one you keep reading.
"""
from __future__ import annotations

import re

from .core.base import Finding, ScanResult

CATEGORY_ORDER = [
    "sanctions",
    "legal",
    "regulatory",
    "ownership",
    "short-interest",
    "positioning",
    "labor",
    "biotech",
    "gov-spending",
    "liquidity",
    "geopolitical-risk",
    "policy-uncertainty",
    "trade-chokepoints",
    "nat-hazards",
    "crypto",
    "web-footprint",
    "attention",
    "prediction-markets",
    "news-events",
]
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

SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


def spark(series: list[float], width: int = 24) -> str:
    """Unicode sparkline, downsampled to `width` points."""
    if len(series) < 2:
        return ""
    if len(series) > width:
        step = len(series) / width
        series = [series[int(i * step)] for i in range(width)]
    lo, hi = min(series), max(series)
    if hi == lo:
        return SPARK_BLOCKS[0] * len(series)
    scale = (len(SPARK_BLOCKS) - 1) / (hi - lo)
    return "".join(SPARK_BLOCKS[int((v - lo) * scale)] for v in series)


def week_delta(series: list[float]) -> float | None:
    """Fractional change of the last point vs ~7 points back."""
    if len(series) < 2:
        return None
    base = series[-8] if len(series) >= 8 else series[0]
    if base == 0:
        return None
    return series[-1] / base - 1


def pulse_stat(series: list[float]) -> tuple[float | None, float | None, float | None]:
    """Reference frame for a pulse gauge: (z-score of the last point vs the series
    mean/std, its percentile within the series, weekly change). A level with no
    reference is unreadable — '220' means nothing until you know it is +1.8σ."""
    if len(series) < 3:
        return None, None, week_delta(series)
    n = len(series)
    mean = sum(series) / n
    var = sum((v - mean) ** 2 for v in series) / n
    std = var**0.5
    last = series[-1]
    z = (last - mean) / std if std > 0 else 0.0
    pct = sum(1 for v in series if v <= last) / n
    return z, pct, week_delta(series)


def pulse_lines(results: list[ScanResult]) -> list[str]:
    lines = []
    for result in results:
        for r in result.pulse:
            z, _pct, delta = pulse_stat(r.series)
            parts = []
            if z is not None:
                parts.append(f"{z:+.1f}σ")
            if delta is not None:
                parts.append(f"{delta:+.0%} wk")
            tail = f" ({', '.join(parts)})" if parts else ""
            lines.append(f"- {r.series_name}: {r.series[-1]:,.0f} `{spark(r.series)}`{tail}")
    return lines


def _briefing_lines(briefing, top: list[Finding] | None) -> list[str]:
    """Lead section. The LLM briefing when present; otherwise a deterministic
    'Top signals' pulled from the computed relevance ranking, so the report always
    opens with what matters rather than the first category alphabetically."""
    lines: list[str] = []
    if briefing is not None:
        lines.append("## Executive briefing")
        if briefing.headline:
            lines.append(f"**{briefing.headline}**")
            lines.append("")
        if briefing.narrative:
            lines.append(briefing.narrative)
            lines.append("")
        for s in briefing.signals:
            cats = f" _{', '.join(s.categories)}_" if s.categories else ""
            lines.append(f"- **[{s.importance}]** {s.title} — {s.why}{cats}")
        lines.append(f"\n_briefing by {briefing.model}_")
        lines.append("")
    elif top:
        lines.append("## Top signals today")
        for f in top:
            why = f.extra.get("why") or []
            why_s = f" _({'; '.join(why)})_" if why else ""
            link = f" — [link]({f.record.url})" if f.record.url else ""
            lines.append(
                f"- **[{f.importance}]** ({f.record.category}) {f.record.title} — "
                f"{f.reason}{why_s}{link}"
            )
        lines.append("")
    return lines


def _confluence_lines(clusters: list | None) -> list[str]:
    if not clusters:
        return []
    lines = ["## Cross-source confluence"]
    for c in clusters:
        n = len(c.findings)
        lines.append(
            f"- **{c.display}** — {', '.join(c.categories)} ({n} item{'s' if n != 1 else ''})"
        )
    lines.append("")
    return lines


def render(
    results: list[ScanResult],
    failures: list[tuple[str, Exception]],
    date_str: str,
    skipped: list[tuple[str, str]] | None = None,
    *,
    briefing=None,
    top: list[Finding] | None = None,
    clusters: list | None = None,
) -> str:
    skipped = skipped or []
    all_findings = [f for r in results for f in r.findings]
    watch_hits = _sorted([f for f in all_findings if f.watchlist])

    lines = [
        f"# argus daily report — {date_str}",
        "",
        f"_{len(results) + len(failures)} sources scanned · {len(all_findings)} findings · "
        f"{len(watch_hits)} watchlist hits · {len(failures)} failures_",
        "",
    ]

    lines.extend(_briefing_lines(briefing, top))
    lines.extend(_confluence_lines(clusters))

    if watch_hits:
        lines.append("## Watchlist hits")
        lines.extend(_bullet(f) for f in watch_hits)
        lines.append("")

    pulse = pulse_lines(results)
    if pulse:
        lines.append("## Market pulse")
        lines.extend(pulse)
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
    for name, msg in skipped:
        lines.append(f"- {name}: skipped — {msg}")
    for name, exc in failures:
        lines.append(f"- {name}: FAILED — {exc}")
    lines.append("")
    return "\n".join(lines)
