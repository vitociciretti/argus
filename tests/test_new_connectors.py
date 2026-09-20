import datetime as dt

from argus.connectors.clinicaltrials import parse_study
from argus.connectors.courtlistener import parse_docket
from argus.connectors.epu import parse_epu
from argus.connectors.kalshi import parse_event_markets
from argus.connectors.portwatch import build_records
from argus.connectors.usaspending import parse_transaction
from argus.connectors.warn_tx import parse_notice
from argus.core.base import Record, crossing_findings
from argus.core.state import StateStore


def test_kalshi_parse_event_markets():
    event = {
        "title": "Fed decision in October?",
        "category": "Economics",
        "markets": [
            {
                "ticker": "KXFED-26OCT-C25",
                "event_ticker": "KXFED-26OCT",
                "status": "active",
                "last_price_dollars": "0.7200",
                "volume_24h_fp": "15000",
                "yes_sub_title": "Cut 25bps",
            },
            {"ticker": "X", "status": "settled", "last_price_dollars": "1.0"},
        ],
    }
    records = parse_event_markets(event)
    assert len(records) == 1
    r = records[0]
    assert r.uid == "kalshi:KXFED-26OCT-C25"
    assert r.metrics["probability"] == 0.72
    assert "Cut 25bps" in r.title


def test_warn_parse_notice():
    r = parse_notice(
        {
            "notice_date": "2026-06-23T00:00:00.000",
            "job_site_name": "JPMorgan Chase & Co.",
            "total_layoff_number": "244",
            "city_name": "Plano",
            "county_name": "Collin",
        }
    )
    assert r.metrics["layoffs"] == 244.0
    assert "JPMorgan" in r.title and "Plano" in r.title
    assert r.uid.startswith("warn_tx:")
    assert parse_notice({"job_site_name": ""}) is None


def test_usaspending_parse_transaction():
    r = parse_transaction(
        {
            "Transaction Amount": 507938027.16,
            "Recipient Name": "BECHTEL NATIONAL, INC.",
            "Awarding Agency": "Department of Energy",
            "Action Date": "2026-09-17",
            "generated_internal_id": "CONT_AWD_X",
        }
    )
    assert "508M" in r.title.replace(",", "")
    assert r.uid == "usaspending:CONT_AWD_X:2026-09-17"


def test_clinicaltrials_parse_study_and_status_uid():
    study = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT05718700", "briefTitle": "Bulevirtide study"},
            "statusModule": {
                "overallStatus": "TERMINATED",
                "lastUpdatePostDateStruct": {"date": "2026-09-18"},
            },
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Gilead Sciences"}},
            "designModule": {"phases": ["PHASE3"]},
        }
    }
    r = parse_study(study)
    assert r.uid == "ctgov:NCT05718700:TERMINATED"  # status baked into uid
    assert "Gilead" in r.title and "PHASE3" in r.title


def test_courtlistener_parse_docket():
    r = parse_docket(
        {
            "docket_id": 74812776,
            "caseName": "SEC v. POLCARI",
            "court": "District Court, D. New Jersey",
            "dateFiled": "2026-09-18",
            "docket_absolute_url": "/docket/74812776/sec-v-polcari/",
            "party": ["SEC", "Polcari"],
        },
        query='"securities fraud"',
    )
    assert r.uid == "courtlistener:74812776"
    assert "POLCARI" in r.title
    assert r.url.startswith("https://www.courtlistener.com/docket/")


def test_epu_parse():
    csv_text = "day,month,year,daily_policy_index\n" + "\n".join(
        f"{i % 28 + 1},{i // 28 + 1},2026,100.0" for i in range(40)
    ) + "\n19,9,2026,300.0"
    record, n = parse_epu(csv_text)
    assert n == 41
    assert record.metrics["epu"] == 300.0
    assert record.metrics["mean30"] == 100.0
    assert record.metrics["ratio"] == 3.0


def _pw_rows(n_recent: float, n_base: float) -> list[dict]:
    rows = []
    day = dt.date(2026, 9, 13)
    for i in range(40):
        d = (day - dt.timedelta(days=i)).isoformat()
        rows.append(
            {"date": d, "portid": "chokepoint1", "portname": "Suez Canal",
             "n_total": n_recent if i < 7 else n_base}
        )
    return rows


def test_portwatch_ratio():
    records = build_records(_pw_rows(10.0, 20.0))
    assert len(records) == 1
    assert records[0].metrics["ratio"] == 0.5
    assert "Suez" in records[0].title


def test_crossing_fires_only_on_entry(tmp_path):
    state = StateStore(tmp_path / "s.db")
    rec = Record(uid="x:1", source="x", category="c",
                 ts=dt.datetime.now(dt.timezone.utc), title="x")

    def check(value):
        return crossing_findings(rec, state, "ratio", value, alert_above=1.4,
                                 reason_fmt="{prev:.1f}->{value:.1f}")

    assert check(1.0) == []      # baseline stored, no prev
    assert check(1.2) == []      # below threshold
    fired = check(1.6)           # crosses in -> fires
    assert len(fired) == 1 and "1.2->1.6" in fired[0].reason
    assert check(1.8) == []      # still in zone -> silent
    assert check(1.0) == []      # exits quietly
    assert len(check(1.5)) == 1  # re-enters -> fires again
