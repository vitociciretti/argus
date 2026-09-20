"""Industry-sponsored trial halts from ClinicalTrials.gov API v2 (no key).

Terminated/suspended/withdrawn trials are disclosed here before most price
reaction — one of the strongest pure-OSINT event sources left. The uid embeds
the status, so a status flip on a known trial surfaces as a new finding.
"""
from __future__ import annotations

import datetime as dt

from ..core import http
from ..core.base import Connector, Finding, Record

API_URL = "https://clinicaltrials.gov/api/v2/studies"
HALT_STATUSES = "TERMINATED|SUSPENDED|WITHDRAWN"


def parse_study(study: dict) -> Record | None:
    proto = study.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    status_mod = proto.get("statusModule", {})
    nct = ident.get("nctId")
    status = status_mod.get("overallStatus", "?")
    if not nct:
        return None
    sponsor = (
        proto.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", "?")
    )
    phases = proto.get("designModule", {}).get("phases", [])
    phase = "/".join(phases) if phases else "N/A"
    updated = status_mod.get("lastUpdatePostDateStruct", {}).get("date", "")
    try:
        ts = dt.datetime.fromisoformat(updated).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        ts = dt.datetime.now(dt.timezone.utc)
    return Record(
        uid=f"ctgov:{nct}:{status}",
        source="clinicaltrials",
        category="biotech",
        ts=ts,
        title=f"{sponsor}: {ident.get('briefTitle', '?')} [{status}, {phase}]",
        url=f"https://clinicaltrials.gov/study/{nct}",
        entities=[sponsor],
        raw={"phase": phase, "status": status, "nct": nct},
    )


class ClinicalTrials(Connector):
    name = "clinicaltrials"
    category = "biotech"
    license_note = "US government work, public domain; official free API v2."

    def fetch(self) -> list[Record]:
        params = {
            "filter.overallStatus": self.cfg.get("statuses", HALT_STATUSES),
            "query.spons": "AREA[LeadSponsorClass]INDUSTRY",
            "sort": "LastUpdatePostDate:desc",
            "pageSize": int(self.cfg.get("limit", 100)),
            "fields": "NCTId|BriefTitle|OverallStatus|Phase|LeadSponsorName|LastUpdatePostDate",
        }
        data = http.get(API_URL, params=params).json()
        return [r for s in data.get("studies", []) if (r := parse_study(s)) is not None]

    def finding_for_new(self, record: Record) -> Finding:
        phase = record.raw.get("phase", "")
        late_stage = "PHASE3" in phase or "PHASE4" in phase
        return Finding(
            record,
            f"trial {record.raw.get('status', '?').lower()}",
            4 if late_stage else 2,
        )
