"""Optional LLM briefing layer — the one place argus asks a model to READ the
day's deltas and say what matters, and why, across sources.

Everything else in argus is deterministic. This is not, so it obeys two rules:

1. **Config-gated.** Off unless ``[llm] enabled = true``. Nothing here runs, and
   no key is required, until you opt in.
2. **Graceful.** Any failure — no SDK installed, no API key, network down, a bad
   response — is logged to stderr and returns ``None``. The report then renders
   exactly as it would without this layer (the deterministic Top-signals section
   takes over). A broken model must never break the briefing, the same house rule
   that keeps a broken connector from killing the run.

Delivery is a Telegram push of the HTML at 06:45; this section rides at the top of
that HTML. Keeping the call cheap (a compact digest in, a small JSON out) matters
more than squeezing the model.
"""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import sys

from .core.base import ScanResult
from .relevance import Cluster
from .report import pulse_stat

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_MAX_FINDINGS = 40


@dataclasses.dataclass
class Signal:
    title: str
    why: str
    categories: list[str]
    importance: int


@dataclasses.dataclass
class Briefing:
    headline: str
    narrative: str
    signals: list[Signal]
    model: str


def _load_api_key(cfg: dict) -> str | None:
    """Env first (standard), then an explicit key in the gitignored local config,
    then an ``env_file`` the config points at (e.g. the Telegram bot's .env, so
    one key serves both). Never a hardcoded default."""
    llm = cfg.get("llm", {})
    if key := os.environ.get("ANTHROPIC_API_KEY"):
        return key
    if key := llm.get("api_key"):
        return str(key)
    env_file = llm.get("env_file")
    if env_file:
        path = pathlib.Path(env_file).expanduser()
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    return None


def _digest(
    results: list[ScanResult],
    top: list,
    clusters: list[Cluster],
) -> str:
    """A compact, model-facing text of the day's state: the ranked findings, the
    confluence clusters, and the pulse gauges with their z-scores. Small on
    purpose — the model needs the signal, not all 95 rows."""
    lines: list[str] = ["## Ranked findings (highest priority first)"]
    for f in top[:DEFAULT_MAX_FINDINGS]:
        why = f.extra.get("why") or []
        why_s = f" [{'; '.join(why)}]" if why else ""
        lines.append(
            f"- [{f.importance}] ({f.record.category}) {f.record.title} — {f.reason}{why_s}"
        )

    if clusters:
        lines.append("\n## Cross-source confluence (same entity, multiple categories)")
        for c in clusters:
            lines.append(f"- {c.display}: {', '.join(c.categories)}")

    pulse_rows = [(r, res) for res in results for r in res.pulse]
    if pulse_rows:
        lines.append("\n## Market pulse (level, z-score vs own history, weekly change)")
        for r, _ in pulse_rows:
            z, _pct, wk = pulse_stat(r.series)
            z_s = f"{z:+.1f}σ" if z is not None else "n/a"
            wk_s = f"{wk:+.0%} wk" if wk is not None else ""
            lines.append(f"- {r.series_name}: {r.series[-1]:,.0f} ({z_s}) {wk_s}")

    return "\n".join(lines)


SYSTEM = """You are the analyst desk for a one-person systematic macro/futures fund. \
Every morning you receive argus, an OSINT delta feed: only things that CHANGED since \
yesterday across sanctions, SEC ownership (13D/13G), federal rulemaking, court dockets, \
short-interest, CFTC positioning, liquidity (RRP/TGA), trade chokepoints, clinical \
trials, government contracts, prediction markets and attention gauges.

Your job is to convert that catalog into a briefing a portfolio manager can act on in \
sixty seconds. Rules:
- Lead with what MATTERS to a macro/cross-asset book, not what is merely new. Most 13G \
  filings are noise; an activist 13D, a chokepoint disruption, a liquidity-drain \
  crossing or a cross-source confluence is not.
- Say WHY each item matters in one clause — the mechanism or the exposure — never just \
  restate the headline.
- If the day is genuinely quiet, say so plainly. Do not manufacture urgency.
- No hedging padding, no "may or may not". Commit.

Return ONLY a JSON object, no prose around it, with exactly these keys:
{
  "headline": "<=90 chars, the single most important read of the day",
  "narrative": "2-4 sentences: the state of the world per this feed and what a macro PM should watch",
  "signals": [
    {"title": "<short>", "why": "<one clause: mechanism/exposure>",
     "categories": ["<category>", ...], "importance": <1-5>}
  ]
}
Include at most 6 signals, ordered most important first. If nothing is material, return \
an empty signals list and say so in the narrative."""


def _parse(text: str, model: str) -> Briefing | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    data = json.loads(text[start : end + 1])
    signals = [
        Signal(
            title=str(s.get("title", "")).strip(),
            why=str(s.get("why", "")).strip(),
            categories=[str(c) for c in s.get("categories", [])],
            importance=int(s.get("importance", 3)),
        )
        for s in data.get("signals", [])
        if s.get("title")
    ]
    return Briefing(
        headline=str(data.get("headline", "")).strip(),
        narrative=str(data.get("narrative", "")).strip(),
        signals=signals,
        model=model,
    )


def generate(
    results: list[ScanResult],
    top: list,
    clusters: list[Cluster],
    cfg: dict,
) -> Briefing | None:
    """Produce the LLM briefing, or None if disabled or anything fails."""
    llm = cfg.get("llm", {})
    if not llm.get("enabled", False):
        return None
    if not top and not clusters:
        return None  # nothing to brief on; the report's quiet-day lines suffice

    try:
        import anthropic
    except ImportError:
        print("[synthesis] skipped — anthropic SDK not installed (uv pip install anthropic)", file=sys.stderr)
        return None

    # An explicit key from env/config wins; otherwise let the SDK resolve its own
    # credentials (ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / an `ant` OAuth
    # profile), so the briefing lights up the moment any of those is present.
    api_key = _load_api_key(cfg)
    model = llm.get("model", DEFAULT_MODEL)
    effort = llm.get("effort", "medium")
    # Construction raises TypeError when the SDK finds no credentials at all, and
    # a call raises AuthenticationError when they are present but rejected. Both
    # mean the same thing to the user: add a key.
    try:
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    except (anthropic.AuthenticationError, TypeError):
        print(
            "[synthesis] skipped — no Anthropic credentials; put your key in "
            "argus.local.toml as [llm] api_key, or export ANTHROPIC_API_KEY",
            file=sys.stderr,
        )
        return None

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=int(llm.get("max_tokens", 2000)),
            system=SYSTEM,
            output_config={"effort": effort},
            messages=[{"role": "user", "content": _digest(results, top, clusters)}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        briefing = _parse(text, model)
        if briefing is None:
            print("[synthesis] skipped — could not parse model JSON", file=sys.stderr)
        return briefing
    except anthropic.AuthenticationError:
        print(
            "[synthesis] skipped — Anthropic credentials rejected; check [llm] api_key",
            file=sys.stderr,
        )
        return None
    except Exception as exc:  # a broken model must not break the briefing
        print(f"[synthesis] skipped — {type(exc).__name__}: {exc}", file=sys.stderr)
        return None
