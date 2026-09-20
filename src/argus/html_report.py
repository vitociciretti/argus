"""Self-contained HTML rendering of the daily report.

One file, zero external JS, inline CSS — it opens anywhere, archives cleanly,
and can be pushed to Telegram/email as-is. Dark risk-terminal aesthetic:
watchlist cards up top, probability-move bars for prediction markets, LED
source-health footer.
"""
from __future__ import annotations

import datetime as dt
import html as html_mod

from .core.base import Finding, ScanResult
from .report import CATEGORY_ORDER, LOW_IMPORTANCE_CAP, sort_findings

IMPORTANCE_COLORS = {5: "#f43f5e", 4: "#fb923c", 3: "#fbbf24", 2: "#38bdf8", 1: "#64748b"}
CATEGORY_ICONS = {
    "sanctions": "&#128683;",           # 🚫
    "legal": "&#9878;&#65039;",         # ⚖️
    "regulatory": "&#127963;&#65039;",  # 🏛️
    "ownership": "&#128100;",           # 👤
    "short-interest": "&#128201;",      # 📉
    "positioning": "&#9879;&#65039;",   # ⚗️
    "labor": "&#128188;",               # 💼
    "biotech": "&#129514;",             # 🧪
    "gov-spending": "&#127974;",        # 🏦
    "liquidity": "&#128167;",           # 💧
    "geopolitical-risk": "&#127758;",   # 🌎
    "policy-uncertainty": "&#128200;",  # 📈
    "trade-chokepoints": "&#128674;",   # 🚢
    "nat-hazards": "&#127755;",         # 🌋
    "crypto": "&#9939;&#65039;",        # ⛓️
    "web-footprint": "&#128737;&#65039;",  # 🛡️
    "attention": "&#128064;",           # 👀
    "prediction-markets": "&#127919;",  # 🎯
    "news-events": "&#128225;",         # 📡
}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@400;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',system-ui,sans-serif;background:#06090f;color:#e2e8f0;min-height:100vh}
body::before{content:'';position:fixed;inset:0;pointer-events:none;background:
 radial-gradient(1100px 550px at 72% -10%,rgba(34,211,238,.09),transparent 60%),
 radial-gradient(900px 500px at 8% 110%,rgba(251,191,36,.06),transparent 60%)}
.grid-bg{position:fixed;inset:0;pointer-events:none;
 background-image:linear-gradient(rgba(148,163,184,.045) 1px,transparent 1px),
 linear-gradient(90deg,rgba(148,163,184,.045) 1px,transparent 1px);
 background-size:42px 42px;
 -webkit-mask-image:radial-gradient(ellipse at 50% 0%,#000 25%,transparent 72%);
 mask-image:radial-gradient(ellipse at 50% 0%,#000 25%,transparent 72%)}
.wrap{max-width:1060px;margin:0 auto;padding:44px 24px;position:relative}
header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:20px}
.brand{display:flex;align-items:center;gap:15px}
.brand svg{width:46px;height:46px;filter:drop-shadow(0 0 14px rgba(34,211,238,.55))}
.brand h1{font-size:29px;font-weight:800;letter-spacing:.26em;color:#f8fafc;line-height:1}
.brand .tag{font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:#64748b;margin-top:6px}
.date{font-family:'JetBrains Mono',monospace;font-size:14px;color:#7dd3fc;text-align:right}
.date .iso{display:block;font-size:11px;color:#475569;margin-top:4px}
.stats{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:13px;margin:30px 0 6px}
.stat{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:15px;
 padding:17px 19px;backdrop-filter:blur(6px);animation:rise .55s ease both}
.stat .num{font-family:'JetBrains Mono',monospace;font-size:36px;font-weight:700;color:#f1f5f9;
 display:block;line-height:1.05;font-variant-numeric:tabular-nums}
.stat .label{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:#64748b}
.stat.gold .num{color:#fbbf24;text-shadow:0 0 20px rgba(251,191,36,.45)}
.stat.bad .num{color:#f43f5e;text-shadow:0 0 20px rgba(244,63,94,.4)}
.banner{margin-top:22px;display:flex;align-items:center;gap:12px;padding:14px 18px;border-radius:13px;
 border:1px solid rgba(244,63,94,.45);background:linear-gradient(90deg,rgba(244,63,94,.14),rgba(251,146,60,.06));
 font-weight:600;font-size:14px;animation:rise .55s ease both}
.banner .pulse{width:10px;height:10px;border-radius:50%;background:#f43f5e;
 box-shadow:0 0 12px #f43f5e;animation:pulse 1.3s infinite}
section{margin-top:40px;animation:rise .55s ease both}
h2{font-size:12px;letter-spacing:.24em;text-transform:uppercase;color:#94a3b8;
 display:flex;align-items:center;gap:11px;margin-bottom:15px}
h2 .icon{font-size:16px}
h2 .count{font-family:'JetBrains Mono',monospace;font-size:11px;color:#22d3ee;
 border:1px solid rgba(34,211,238,.35);border-radius:99px;padding:2px 10px}
h2::after{content:'';flex:1;height:1px;background:linear-gradient(90deg,rgba(148,163,184,.28),transparent)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
.card{background:linear-gradient(180deg,rgba(255,255,255,.05),rgba(255,255,255,.02));
 border:1px solid rgba(255,255,255,.09);border-left:3px solid var(--imp);border-radius:15px;
 padding:16px 18px;transition:transform .18s ease,border-color .18s ease;animation:rise .55s ease both}
.card:hover{transform:translateY(-3px);border-color:rgba(251,191,36,.5)}
.rows{display:flex;flex-direction:column;gap:10px}
.row{display:flex;gap:14px;align-items:flex-start;background:rgba(255,255,255,.03);
 border:1px solid rgba(255,255,255,.08);border-left:3px solid var(--imp);border-radius:13px;
 padding:14px 17px;transition:border-color .18s ease;animation:rise .55s ease both}
.row:hover{border-color:rgba(34,211,238,.45)}
.row .body{flex:1;min-width:0}
.badge{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:12px;color:var(--imp);
 border:1px solid var(--imp);border-radius:9px;padding:2px 9px;flex-shrink:0;
 box-shadow:0 0 14px color-mix(in srgb,var(--imp) 30%,transparent)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:9px}
.chip{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.08em;color:#fbbf24;
 background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.4);border-radius:99px;padding:2px 9px}
.src{font-family:'JetBrains Mono',monospace;font-size:10px;color:#475569;letter-spacing:.1em;text-transform:uppercase}
.title{font-size:15px;font-weight:600;line-height:1.45;margin:7px 0 5px;overflow-wrap:anywhere}
.title a{color:#e2e8f0;text-decoration:none}
.title a:hover{color:#22d3ee}
.reason{font-family:'JetBrains Mono',monospace;font-size:12px;color:#94a3b8}
.linkout{margin-left:auto;flex-shrink:0;color:#334155;font-size:15px;text-decoration:none;transition:color .15s}
.linkout:hover{color:#22d3ee}
.quiet{display:flex;gap:11px;align-items:center;color:#475569;font-size:13.5px;
 font-family:'JetBrains Mono',monospace;padding:15px 18px;
 border:1px dashed rgba(148,163,184,.2);border-radius:13px}
.quiet .ok{color:#34d399}
.more{color:#475569;font-size:12px;font-family:'JetBrains Mono',monospace;padding:6px 4px}
.prob{display:flex;align-items:center;gap:11px;font-family:'JetBrains Mono',monospace;
 font-size:12px;margin-top:11px;font-variant-numeric:tabular-nums}
.prob .from{color:#64748b}
.prob .to.up{color:#34d399}.prob .to.down{color:#f87171}
.pp.up{color:#34d399}.pp.down{color:#f87171}
.track{position:relative;flex:1;height:6px;border-radius:3px;background:rgba(148,163,184,.16);min-width:80px}
.range{position:absolute;top:0;height:100%;border-radius:3px}
.range.up{background:linear-gradient(90deg,rgba(52,211,153,.2),#34d399)}
.range.down{background:linear-gradient(270deg,rgba(248,113,113,.2),#f87171)}
.dot{position:absolute;top:50%;width:10px;height:10px;border-radius:50%;transform:translate(-50%,-50%)}
.dot.up{background:#34d399;box-shadow:0 0 11px #34d399}
.dot.down{background:#f87171;box-shadow:0 0 11px #f87171}
.health{display:grid;grid-template-columns:repeat(auto-fill,minmax(225px,1fr));gap:12px}
.hcard{display:flex;align-items:center;gap:12px;background:rgba(255,255,255,.03);
 border:1px solid rgba(255,255,255,.08);border-radius:13px;padding:13px 16px;
 font-family:'JetBrains Mono',monospace;font-size:12.5px;animation:rise .55s ease both}
.hcard .n{color:#475569;margin-left:auto}
.hcard .msg{color:#f87171;font-size:11px;overflow-wrap:anywhere}
.led{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.led.ok{background:#34d399;box-shadow:0 0 10px #34d399}
.led.warn{background:#fbbf24;box-shadow:0 0 10px #fbbf24;animation:pulse 1.6s infinite}
.led.fail{background:#f43f5e;box-shadow:0 0 10px #f43f5e;animation:pulse 1.2s infinite}
.led.off{background:#334155}
.msg.dim{color:#475569}
footer{margin-top:52px;text-align:center;color:#475569;font-size:11.5px;
 font-family:'JetBrains Mono',monospace;letter-spacing:.08em}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
@media(max-width:640px){.stats{grid-template-columns:repeat(2,1fr)}.date{text-align:left}}
"""

EYE_SVG = """<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M4 24C10 13 17 8 24 8s14 5 20 16c-6 11-13 16-20 16S10 35 4 24Z" stroke="#22d3ee" stroke-width="2.5"/>
<circle cx="24" cy="24" r="7.5" fill="#22d3ee"/><circle cx="21.5" cy="21.5" r="2.2" fill="#06090f"/>
</svg>"""


def _esc(text: str) -> str:
    return html_mod.escape(str(text), quote=True)


def _imp_color(f: Finding) -> str:
    return IMPORTANCE_COLORS.get(f.importance, "#64748b")


def _prob_bar(extra: dict) -> str:
    try:
        p_from, p_to = float(extra["from"]), float(extra["to"])
    except (KeyError, TypeError, ValueError):
        return ""
    direction = "up" if p_to >= p_from else "down"
    left = min(p_from, p_to) * 100
    width = abs(p_to - p_from) * 100
    return (
        f'<div class="prob"><span class="from">{p_from:.0%}</span>'
        f'<div class="track"><div class="range {direction}" style="left:{left:.1f}%;width:{width:.1f}%"></div>'
        f'<div class="dot {direction}" style="left:{p_to * 100:.1f}%"></div></div>'
        f'<span class="to {direction}">{p_to:.0%}</span>'
        f'<span class="pp {direction}">{(p_to - p_from) * 100:+.0f}pp</span></div>'
    )


def _card(f: Finding, i: int) -> str:
    chips = "".join(f'<span class="chip">{_esc(t)}</span>' for t in f.watchlist)
    link = f' <a href="{_esc(f.record.url)}">{_esc(f.record.title)}</a>' if f.record.url else _esc(f.record.title)
    return (
        f'<div class="card" style="--imp:{_imp_color(f)};animation-delay:{min(i, 20) * 60}ms">'
        f'<div class="chips">{chips}<span class="badge">{f.importance}</span></div>'
        f'<span class="src">{_esc(f.record.source)}</span>'
        f'<div class="title">{link}</div>'
        f'<div class="reason">{_esc(f.reason)}</div>'
        f"{_prob_bar(f.extra)}</div>"
    )


def _row(f: Finding, i: int) -> str:
    out = (
        f' <a class="linkout" href="{_esc(f.record.url)}" title="open source">&#8599;</a>'
        if f.record.url
        else ""
    )
    return (
        f'<div class="row" style="--imp:{_imp_color(f)};animation-delay:{min(i, 20) * 60}ms">'
        f'<span class="badge">{f.importance}</span>'
        f'<div class="body"><div class="title">{_esc(f.record.title)}</div>'
        f'<div class="reason">{_esc(f.reason)}</div>{_prob_bar(f.extra)}</div>{out}</div>'
    )


def _quiet(text: str) -> str:
    return f'<div class="quiet"><span class="ok">&#10003;</span>{_esc(text)}</div>'


def _category_section(result: ScanResult) -> str:
    icon = CATEGORY_ICONS.get(result.category, "&#128752;")
    findings = sort_findings([f for f in result.findings if not f.watchlist])
    header = (
        f'<h2><span class="icon">{icon}</span>{_esc(result.category)}'
        f'<span class="count">{result.source} &middot; {len(findings)}</span></h2>'
    )
    if result.first_run:
        body = _quiet(f"first run — baseline of {result.n_records} records seeded; deltas start next scan")
    elif not findings:
        if any(f.watchlist for f in result.findings):
            body = _quiet("all findings shown under watchlist hits")
        else:
            body = _quiet("quiet — no changes")
    else:
        high = [f for f in findings if f.importance >= 3]
        low = [f for f in findings if f.importance <= 2]
        rows = "".join(_row(f, i) for i, f in enumerate(high + low[:LOW_IMPORTANCE_CAP]))
        hidden = len(low) - min(len(low), LOW_IMPORTANCE_CAP)
        if hidden:
            rows += f'<div class="more">+{hidden} more low-importance items not shown</div>'
        body = f'<div class="rows">{rows}</div>'
    return f"<section>{header}{body}</section>"


def _health_section(
    results: list[ScanResult],
    failures: list[tuple[str, Exception]],
    skipped: list[tuple[str, str]],
) -> str:
    cards = []
    for i, r in enumerate(sorted(results, key=lambda r: r.source)):
        if r.n_records == 0:
            cards.append(
                f'<div class="hcard" style="animation-delay:{i * 60}ms"><span class="led warn"></span>'
                f"{_esc(r.source)}<span class='n'>0 records</span></div>"
            )
        else:
            cards.append(
                f'<div class="hcard" style="animation-delay:{i * 60}ms"><span class="led ok"></span>'
                f"{_esc(r.source)}<span class='n'>{r.n_records:,}</span></div>"
            )
    for name, msg in skipped:
        cards.append(
            f'<div class="hcard"><span class="led off"></span>{_esc(name)}'
            f'<span class="msg dim">{_esc(msg[:80])}</span></div>'
        )
    for name, exc in failures:
        cards.append(
            f'<div class="hcard"><span class="led fail"></span>{_esc(name)}'
            f'<span class="msg">{_esc(str(exc)[:90])}</span></div>'
        )
    return (
        '<section><h2><span class="icon">&#128161;</span>source health'
        f'<span class="count">{len(results)} ok &middot; {len(skipped)} skipped &middot; '
        f'{len(failures)} failed</span></h2>'
        f'<div class="health">{"".join(cards)}</div></section>'
    )


def render_html(
    results: list[ScanResult],
    failures: list[tuple[str, Exception]],
    date_iso: str,
    skipped: list[tuple[str, str]] | None = None,
) -> str:
    skipped = skipped or []
    date = dt.date.fromisoformat(date_iso)
    all_findings = [f for r in results for f in r.findings]
    watch_hits = sort_findings([f for f in all_findings if f.watchlist])
    n_hot = sum(1 for f in all_findings if f.importance >= 4)

    stats = (
        f'<div class="stat"><span class="num">{len(results) + len(failures)}</span>'
        f'<span class="label">sources</span></div>'
        f'<div class="stat"><span class="num">{len(all_findings)}</span>'
        f'<span class="label">findings</span></div>'
        f'<div class="stat{" gold" if watch_hits else ""}"><span class="num">{len(watch_hits)}</span>'
        f'<span class="label">watchlist hits</span></div>'
        f'<div class="stat{" bad" if failures else ""}"><span class="num">{len(failures)}</span>'
        f'<span class="label">failures</span></div>'
    )

    banner = ""
    if n_hot:
        banner = (
            f'<div class="banner"><span class="pulse"></span>'
            f"{n_hot} high-priority signal{'s' if n_hot != 1 else ''} today &mdash; review the top cards first</div>"
        )

    watch_section = ""
    if watch_hits:
        cards = "".join(_card(f, i) for i, f in enumerate(watch_hits))
        watch_section = (
            '<section><h2><span class="icon">&#9889;</span>watchlist hits'
            f'<span class="count">{len(watch_hits)}</span></h2><div class="cards">{cards}</div></section>'
        )

    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    categories = "".join(
        _category_section(r)
        for r in sorted(results, key=lambda r: (order.get(r.category, 99), r.source))
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>argus &mdash; {date_iso}</title><style>{CSS}</style></head>
<body><div class="grid-bg"></div><div class="wrap">
<header>
<div class="brand">{EYE_SVG}<div><h1>ARGUS</h1><div class="tag">OSINT daily briefing</div></div></div>
<div class="date">{date.strftime("%A")} &middot; {date.strftime("%d %B %Y")}<span class="iso">deltas since previous scan</span></div>
</header>
<div class="stats">{stats}</div>
{banner}
{watch_section}
{categories}
{_health_section(results, failures, skipped)}
<footer>generated by argus &middot; every source is public &middot; {date_iso}</footer>
</div></body></html>"""
