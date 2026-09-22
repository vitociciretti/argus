"""Turn a flat delta feed into a ranked one.

The connectors emit a STATIC importance per finding — every SCHEDULE 13D scores 4
whether Elliott Management filed it or an unknown individual did. This module adds
a COMPUTED relevance on top of that static floor, from signals the connectors
already carry:

- a **known material actor** in the entities (an activist fund's 13D is not the
  same event as a passive filer's),
- the **magnitude** in the metrics (a $1bn contract, a 12pp probability move),
- and — the rarest and most valuable — **cross-source confluence**: the same
  entity surfacing in MORE THAN ONE category the same day. A layoff notice + a
  new securities-fraud docket + a 13D on one name is a story; three unrelated
  bullets scattered across three sections is not.

Everything here is deterministic and API-free. It sharpens the report on its own
(material items get boosted and pulled up; a confluence section appears when the
data earns it) AND it produces the ranked input the optional LLM layer reads.
"""
from __future__ import annotations

import dataclasses
import re

from .core.base import Finding, ScanResult

# Well-known activist investors and event-driven funds. A 13D/amendment from one
# of these is a materially different event from the same form filed by an unknown
# holder — that distinction is exactly what the static per-form importance throws
# away. Passive index giants (BlackRock/Vanguard/State Street) are DELIBERATELY
# absent: they file 13Gs constantly, so boosting them would amplify noise, not cut
# it. Substring match, lower-cased. Extend via [relevance] extra_actors in config.
KNOWN_ACTORS: tuple[str, ...] = (
    "elliott", "icahn", "starboard", "saba capital", "pershing square", "ackman",
    "third point", "loeb", "trian", "peltz", "jana partners", "valueact", "value act",
    "engine capital", "engaged capital", "politan", "sachem head", "corvex",
    "land & buildings", "legion partners", "ancora", "steel partners",
    "greenwood investors", "ryan cohen", "cohen ryan", "hestia", "blackwells",
    "mantle ridge", "glenview", "sarissa", "cannell", "kimmeridge", "irenic",
    "jeffrey smith", "carl icahn", "gamestop",
)

# Legal-form suffixes stripped before joining entities across sources, so
# "Kinetik Holdings Inc." and "Kinetik Holdings" collapse to one actor.
_SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|company|co|llc|l\.?l\.?c|lp|l\.?p|"
    r"plc|ltd|limited|sa|s\.?a|ag|nv|n\.?v|group|holdings?|trust|the|fund)\b",
    re.IGNORECASE,
)
_NONWORD = re.compile(r"[^a-z0-9 ]+")
_STOP = {"", "the", "and", "for", "of", "com", "new", "capital", "partners"}


def normalize_entity(name: str) -> str:
    """Collapse an entity to a joinable key: lower-case, drop legal suffixes and
    punctuation, squeeze whitespace. Returns '' for anything too generic to join
    on (a bare stopword, a single short token)."""
    s = _NONWORD.sub(" ", name.lower())
    s = _SUFFIXES.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    tokens = [t for t in s.split() if t not in _STOP]
    if not tokens or not any(len(t) >= 4 for t in tokens):
        return ""
    return " ".join(tokens)


@dataclasses.dataclass
class Cluster:
    """One entity seen across two or more categories in a single scan."""

    key: str
    display: str
    categories: list[str]
    findings: list[Finding]


def _known_actor(text: str, extra: tuple[str, ...]) -> str | None:
    low = text.lower()
    for actor in (*KNOWN_ACTORS, *extra):
        if actor in low:
            return actor
    return None


def _magnitude(f: Finding) -> tuple[float, str | None]:
    """Score dollar / probability magnitude from the metrics the connectors
    already attach. Returns (score_component, why-string-or-None)."""
    amount = f.record.metrics.get("amount")
    if amount:
        if amount >= 1e9:
            return 0.40, f"${amount / 1e9:,.1f}bn"
        if amount >= 250e6:
            return 0.30, f"${amount / 1e6:,.0f}M"
        if amount >= 100e6:
            return 0.20, f"${amount / 1e6:,.0f}M"
        if amount >= 50e6:
            return 0.10, f"${amount / 1e6:,.0f}M"
    p_from, p_to = f.extra.get("from"), f.extra.get("to")
    if isinstance(p_from, (int, float)) and isinstance(p_to, (int, float)):
        delta = abs(p_to - p_from)
        if delta >= 0.10:
            return 0.30, f"{delta * 100:+.0f}pp move"
        if delta >= 0.05:
            return 0.15, f"{delta * 100:+.0f}pp move"
    return 0.0, None


def build_clusters(results: list[ScanResult]) -> dict[str, Cluster]:
    """Find entities that appear across >= 2 DIFFERENT categories this scan.

    Cross-CATEGORY is the bar, not cross-finding: a fund filing ten 13Ds is ten
    ownership rows, not confluence. The same name showing up in ownership AND
    legal AND biotech is the thing worth a human's attention.
    """
    by_key: dict[str, Cluster] = {}
    for result in results:
        if result.first_run:
            continue
        for f in result.findings:
            for entity in f.record.entities or [f.record.title]:
                key = normalize_entity(entity)
                if not key:
                    continue
                cl = by_key.get(key)
                if cl is None:
                    cl = by_key[key] = Cluster(key, entity.strip(), [], [])
                if result.category not in cl.categories:
                    cl.categories.append(result.category)
                cl.findings.append(f)
    return {k: c for k, c in by_key.items() if len(c.categories) >= 2}


def apply(results: list[ScanResult], cfg: dict) -> list[Cluster]:
    """Score every finding, record the reasons in ``extra``, and gently boost the
    importance of material ones (capped at 5, same convention as the watchlist).
    Returns the confluence clusters for rendering and for the LLM layer.
    """
    rel_cfg = cfg.get("relevance", {})
    extra_actors = tuple(a.lower() for a in rel_cfg.get("extra_actors", []))
    clusters = build_clusters(results)
    in_cluster: dict[int, Cluster] = {}
    for cl in clusters.values():
        for f in cl.findings:
            in_cluster[id(f)] = cl

    for result in results:
        for f in result.findings:
            score = 0.0
            why: list[str] = []

            hay = f"{f.record.title} {' '.join(f.record.entities)}"
            actor = _known_actor(hay, extra_actors)
            if actor:
                score += 0.5
                why.append(f"known actor ({actor})")

            mag_score, mag_why = _magnitude(f)
            if mag_why:
                score += mag_score
                why.append(mag_why)

            if f.watchlist:
                score += 0.3
                why.append(f"watchlist: {', '.join(f.watchlist)}")

            cl = in_cluster.get(id(f))
            if cl is not None:
                score += 0.6
                others = [c for c in cl.categories if c != result.category]
                why.append(f"confluence: also in {', '.join(others)}")

            f.extra["relevance"] = round(min(score, 1.0), 3)
            f.extra["why"] = why
            if score >= 0.5:
                f.importance = min(5, f.importance + 1)

    return sorted(clusters.values(), key=lambda c: (-len(c.categories), c.display))


def top_signals(results: list[ScanResult], n: int = 8) -> list[Finding]:
    """The n highest-priority findings across every source, by (importance,
    computed relevance, recency). Skips first-run baselines and de-dupes by uid.
    This is the deterministic lead section — and the LLM layer's input."""
    seen: set[str] = set()
    out: list[Finding] = []
    pool = [
        f
        for r in results
        if not r.first_run
        for f in r.findings
    ]
    pool.sort(
        key=lambda f: (
            -f.importance,
            -float(f.extra.get("relevance", 0.0)),
            -f.record.ts.timestamp(),
        )
    )
    for f in pool:
        if f.record.uid in seen:
            continue
        seen.add(f.record.uid)
        out.append(f)
        if len(out) >= n:
            break
    return out
