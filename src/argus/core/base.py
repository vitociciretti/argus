"""Connector contract.

A Connector fetches a snapshot of a public source and returns normalized
Records. The base class turns snapshots into Findings (deltas): never-seen
uids, plus whatever metric moves the connector flags. First run seeds the
state silently so a 17k-row sanctions list doesn't produce 17k "new" findings.
"""
from __future__ import annotations

import abc
import dataclasses
import datetime as dt
from typing import Any

import pandas as pd

from .state import StateStore


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


@dataclasses.dataclass
class Record:
    uid: str                # globally unique, stable across fetches: "source:native_id"
    source: str
    category: str
    ts: dt.datetime
    title: str
    url: str = ""
    entities: list[str] = dataclasses.field(default_factory=list)
    metrics: dict[str, float] = dataclasses.field(default_factory=dict)
    raw: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Finding:
    record: Record
    reason: str
    importance: int = 2  # 1 = background noise .. 5 = drop everything
    watchlist: list[str] = dataclasses.field(default_factory=list)  # matched terms
    extra: dict[str, Any] = dataclasses.field(default_factory=dict)  # renderer hints, e.g. {"from": .44, "to": .26}


@dataclasses.dataclass
class ScanResult:
    source: str
    category: str
    findings: list[Finding]
    n_records: int   # 0 records from a live source is a health warning, not quiet
    first_run: bool


def records_to_df(records: list[Record]) -> pd.DataFrame:
    rows = []
    for r in records:
        row: dict[str, Any] = {
            "uid": r.uid,
            "ts": r.ts,
            "title": r.title,
            "entities": ", ".join(r.entities),
            "url": r.url,
        }
        row.update(r.metrics)
        rows.append(row)
    return pd.DataFrame(rows)


class Connector(abc.ABC):
    name: str
    category: str
    cadence: str = "daily"
    license_note: str = ""
    report_new: bool = True    # emit a Finding for every never-seen uid
    seed_quietly: bool = True  # first run absorbs the backlog without findings
    new_importance: int = 2

    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or {}

    @abc.abstractmethod
    def fetch(self) -> list[Record]:
        ...

    def scan(self, state: StateStore) -> ScanResult:
        records = self.fetch()
        first_run = not state.is_seeded(self.name)
        known = state.known_uids(self.name)
        fresh = [r for r in records if r.uid not in known]

        findings: list[Finding] = []
        if self.report_new and not (first_run and self.seed_quietly):
            findings.extend(self.finding_for_new(r) for r in fresh)
        findings.extend(self.metric_findings(records, state, first_run))

        state.add_seen(records)
        state.mark_seeded(self.name)
        return ScanResult(self.name, self.category, findings, len(records), first_run)

    def finding_for_new(self, record: Record) -> Finding:
        return Finding(record, "new", self.new_importance)

    def metric_findings(
        self, records: list[Record], state: StateStore, first_run: bool
    ) -> list[Finding]:
        """Override to flag metric moves. Implementations must persist the new
        baseline via state.set_metric() for every record, including on first run."""
        return []
