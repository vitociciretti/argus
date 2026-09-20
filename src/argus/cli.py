from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys

from . import config as config_mod
from . import report as report_mod
from .core.base import ScanResult, records_to_df
from .core.state import StateStore
from .registry import CONNECTORS, make


def _run_scans(
    names: list[str], cfg: dict, state: StateStore
) -> tuple[list[ScanResult], list[tuple[str, Exception]]]:
    results: list[ScanResult] = []
    failures: list[tuple[str, Exception]] = []
    for name in names:
        try:
            results.append(make(name, cfg).scan(state))
        except Exception as exc:  # a broken source must not kill the run
            failures.append((name, exc))
    return results, failures


def cmd_list(args: argparse.Namespace, cfg: dict) -> int:
    for name, cls in sorted(CONNECTORS.items()):
        print(f"{name:<18} {cls.category:<20} {cls.cadence:<8} {cls.license_note}")
    return 0


def cmd_fetch(args: argparse.Namespace, cfg: dict) -> int:
    connector = make(args.source, cfg)
    records = connector.fetch()
    df = records_to_df(records)
    if args.limit:
        df = df.head(args.limit)
    print(df.to_string(index=False, max_colwidth=70))
    print(f"\n{len(records)} records from {args.source}")
    return 0


def cmd_scan(args: argparse.Namespace, cfg: dict) -> int:
    state = StateStore(args.state)
    names = args.sources or sorted(CONNECTORS)
    results, failures = _run_scans(names, cfg, state)
    total = 0
    for r in results:
        note = " (first run: baseline seeded)" if r.first_run else ""
        print(f"\n## {r.source} - {len(r.findings)} finding(s){note}")
        for f in sorted(r.findings, key=lambda f: -f.importance):
            print(f"- [{f.importance}] {f.record.title}")
            print(f"      {f.reason} | {f.record.url}")
        total += len(r.findings)
    print(f"\n=> {total} finding(s) across {len(results)} source(s)")
    for name, exc in failures:
        print(f"!! {name} failed: {exc}", file=sys.stderr)
    return 1 if failures else 0


def cmd_report(args: argparse.Namespace, cfg: dict) -> int:
    state = StateStore(args.state)
    names = args.sources or sorted(CONNECTORS)
    results, failures = _run_scans(names, cfg, state)
    report_mod.apply_watchlist(results, report_mod.watchlist_terms(cfg))
    date_str = dt.date.today().isoformat()
    text = report_mod.render(results, failures, date_str)
    print(text)
    if not args.no_write:
        out_dir = pathlib.Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{date_str}.md"
        path.write_text(text)
        print(f"[written to {path}]", file=sys.stderr)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="argus", description="OSINT-for-finance connectors")
    parser.add_argument("--config", default=None, help="path to argus.toml")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list available connectors")

    p_fetch = sub.add_parser("fetch", help="fetch one source and print the snapshot")
    p_fetch.add_argument("source", choices=sorted(CONNECTORS))
    p_fetch.add_argument("--limit", type=int, default=25)

    p_scan = sub.add_parser("scan", help="scan sources and print deltas since last run")
    p_scan.add_argument("sources", nargs="*", metavar="source")
    p_scan.add_argument("--state", default="data/state.db")

    p_report = sub.add_parser("report", help="scan and render the daily markdown report")
    p_report.add_argument("sources", nargs="*", metavar="source")
    p_report.add_argument("--state", default="data/state.db")
    p_report.add_argument("--out", default="data/reports", help="report output directory")
    p_report.add_argument("--no-write", action="store_true", help="print only, don't write file")

    args = parser.parse_args(argv)
    cfg = config_mod.load(args.config)
    handler = {"list": cmd_list, "fetch": cmd_fetch, "scan": cmd_scan, "report": cmd_report}[
        args.command
    ]
    return handler(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
