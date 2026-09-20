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

`argus report` scans every source and renders a markdown digest built on three
rules:

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
| `polymarket` | prediction-markets | probability moves >= threshold on liquid markets |
| `federal_register` | regulatory | new rules/proposed rules from SEC, CFTC, Treasury, Fed, OFAC |
| `ofac_sdn` | sanctions | new SDN designations |
| `gdelt` | news-events | new headlines matching watch terms |

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
- [ ] Telegram/MP3 delivery of the daily report
- [ ] Full connector build-out: WARN notices, CourtListener, Kalshi, GPR/EPU,
      IMF PortWatch, ACLED, AGSI gas storage, ENTSO-E, USAspending,
      ClinicalTrials/FDA, certificate transparency, ADS-B
- [ ] Daily CI run of every connector — find breakage before users do

## Legal note

Everything here reads public data via official APIs or public downloads. If you
extend it: public availability is what makes OSINT legal — no credentialed
access, no ToS-violating scraping at scale, and be careful with personal data
(GDPR/FADP applies to people, not companies).

## License

MIT
