# argus

**OSINT connectors for finance** — the free public data that Bloomberg doesn't sell
and [OpenBB](https://github.com/OpenBB-finance/OpenBB) doesn't cover: sanctions
designations, regulatory rulemaking, prediction-market probabilities, conflict and
chokepoint monitoring, court dockets, layoff notices.

Named for Argus Panoptes, the hundred-eyed watchman.

## The idea

Every source here is **open** (public API, bulk download, or public page) and
**event-shaped**: argus normalizes each source into `Record`s, remembers what it
has seen in a local SQLite state store, and reports only **deltas** — new
sanctions designations, new SEC rules, prediction-market probability moves.
Levels are for dashboards; deltas are for briefings.

```
Connector.fetch()  ->  list[Record]      # normalized snapshot of one source
Connector.scan()   ->  list[Finding]     # what changed since the last scan
```

- **Record**: `uid` (stable, `source:native_id`), `ts`, `title`, `url`,
  `entities`, `metrics`, `raw`.
- **Finding**: a Record plus a `reason` ("new", "probability 62% -> 70%") and an
  `importance` (1–5).
- First run of any connector **seeds silently** — a 17k-row sanctions list
  produces zero findings on day one and only real additions afterwards.
- All HTTP goes through one polite client: identified User-Agent, retries with
  backoff, per-host rate limiting.

## Quickstart

```bash
pip install -e ".[dev]"

argus list                 # available connectors
argus fetch polymarket     # print one source's current snapshot
argus scan                 # all sources; prints deltas since last scan
argus scan ofac_sdn        # just one source
argus report               # daily markdown digest -> data/reports/YYYY-MM-DD.md
```

State lives in `data/state.db` (override with `--state`). Per-connector
configuration in `argus.toml` — see the annotated example in this repo.

## The daily report

`argus report` scans every source and writes two artifacts: a markdown digest
(for cron logs, pipes, Telegram later) and a **self-contained HTML briefing**
(`data/reports/YYYY-MM-DD.html` — dark risk-terminal design, watchlist cards,
probability-move bars, LED source health; zero JS, opens anywhere). Add
`--open` to pop it in the browser. Preview the full design with synthetic data:
`python scripts/demo_report.py`. Both formats follow three rules:

1. **Deltas, not levels** — only what changed since the last scan appears.
2. **Watchlist first** — findings matching `[watchlist]` terms in `argus.toml`
   (tickers, countries, commodities, free text) are tagged, bumped +1
   importance, and pulled into a top section. GDELT derives its news query
   from the watchlist when no explicit query is configured.
3. **Honest when quiet** — silent sources print one line, and a source-health
   footer distinguishes "no changes" from "returned 0 records" from "failed".

Run it once a day from cron; the state store makes each run report exactly the
gap since the previous one.

## Connectors

| name | category | signal |
|---|---|---|
| `ofac_sdn` | sanctions | new SDN designations |
| `courtlistener` | legal | new federal dockets matching watch queries |
| `federal_register` | regulatory | new rules/proposed rules from SEC, CFTC, Treasury, Fed, OFAC |
| `warn_tx` | labor | new Texas WARN layoff notices (more states: roadmap) |
| `clinicaltrials` | biotech | industry trials newly terminated/suspended/withdrawn |
| `usaspending` | gov-spending | new federal contract transactions >= $50M |
| `gpr` | geopolitical-risk | Geopolitical Risk Index spike (MA7/MA30) or level alert |
| `epu` | policy-uncertainty | US EPU spike vs trailing 30d mean or level alert |
| `portwatch` | trade-chokepoints | chokepoint transits entering disruption/surge vs 30d baseline |
| `polymarket` | prediction-markets | probability moves >= threshold on liquid markets |
| `kalshi` | prediction-markets | probability moves on macro/event markets (CFTC-regulated) |
| `gdelt` | news-events | new headlines matching watch terms |

All twelve are keyless. CourtListener optionally takes a free `api_token` for
higher rate limits. Index-style sources (GPR, EPU, PortWatch) alert on
**threshold crossings**, not levels, so a sustained crisis fires once on entry
instead of every day.

## Writing a connector

Subclass `Connector`, implement `fetch()`, register it in `registry.py`:

```python
class MySource(Connector):
    name = "my_source"
    category = "..."
    license_note = "..."          # always document the source's terms

    def fetch(self) -> list[Record]:
        data = http.get(URL).json()          # the shared polite client
        return [parse(item) for item in data]
```

Rules of the house:

1. **Prefer API/bulk over scraping.** Scrape only when no structured access
   exists, politely, and respect robots.txt.
2. **Stable uids.** Use the source's native identifier, never a row index.
3. **Pure parse functions** (`parse_*` at module level) so they're testable
   offline with fixture payloads.
4. **Seed quietly** unless the backlog genuinely is news.
5. **Document the license** in `license_note`.

## Roadmap

- [x] Core: Record/Finding, delta state store, polite HTTP, CLI
- [x] Example connectors: polymarket, federal_register, ofac_sdn, gdelt
- [x] Daily digest report (`argus report`) with watchlist boosting
- [x] Full keyless connector build-out (12 sources across 11 categories)
- [ ] Telegram/MP3 delivery of the daily report
- [ ] Key-gated connectors: ACLED, AGSI gas storage, ENTSO-E (free registration)
- [ ] More WARN states (CA, NY, WA), FDA warning letters, certificate
      transparency, ADS-B
- [ ] Daily CI run of every connector — find breakage before users do

## Legal note

Everything here reads public data via official APIs or public downloads. If you
extend it: public availability is what makes OSINT legal — no credentialed
access, no ToS-violating scraping at scale, and be careful with personal data
(GDPR/FADP applies to people, not companies).

## License

MIT
