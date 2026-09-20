from __future__ import annotations

import argparse
import sys

from . import config as config_mod
from .core.base import records_to_df
from .core.state import StateStore
from .registry import CONNECTORS, make


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
    total = 0
    failures: list[tuple[str, Exception]] = []
    for name in names:
        seeded_before = state.is_seeded(name)
        try:
            findings = make(name, cfg).scan(state)
        except Exception as exc:  # a broken source must not kill the scan
            failures.append((name, exc))
            continue
        note = "" if seeded_before else " (first run: baseline seeded)"
        print(f"\n## {name} - {len(findings)} finding(s){note}")
        for f in sorted(findings, key=lambda f: -f.importance):
            print(f"- [{f.importance}] {f.record.title}")
            print(f"      {f.reason} | {f.record.url}")
        total += len(findings)
    print(f"\n=> {total} finding(s) across {len(names) - len(failures)} source(s)")
    for name, exc in failures:
        print(f"!! {name} failed: {exc}", file=sys.stderr)
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

    args = parser.parse_args(argv)
    cfg = config_mod.load(args.config)
    handler = {"list": cmd_list, "fetch": cmd_fetch, "scan": cmd_scan}[args.command]
    return handler(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
