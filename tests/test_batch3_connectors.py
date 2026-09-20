import datetime as dt

import pytest

from argus.connectors.cftc_cot import parse_report
from argus.connectors.crtsh import CrtSh, parse_certs
from argus.connectors.defillama import parse_protocols
from argus.connectors.edgar_ownership import parse_idx
from argus.connectors.openfda_recalls import parse_recalls
from argus.connectors.regsho_threshold import parse_threshold
from argus.connectors.usgs_quakes import parse_quakes
from argus.core.base import ConfigSkip

IDX_SAMPLE = """Form Type   Company Name   CIK   Date Filed  File Name
---------------------------------------------------------------
1-A/A            Casa Shares Assets, LLC                                       1988874     20260918    edgar/data/1988874/0001493152-26-043199.txt
SCHEDULE 13D     New Fortress Energy Inc.                                      1749723     20260918    edgar/data/1749723/0001193125-26-395888.txt
SCHEDULE 13G/A   Vanguard Group Inc                                            102909      20260918    edgar/data/102909/0001104659-26-108754.txt
4                Tesla, Inc.                                                   1318605     20260918    edgar/data/1318605/0001628280-26-043000.txt
4                Acme Widgets Corp                                             999999      20260918    edgar/data/999999/0001628280-26-043001.txt
"""


def test_edgar_parse_idx_filters_forms():
    records = parse_idx(IDX_SAMPLE, form4_companies=["tesla"])
    forms = {r.raw["form"] for r in records}
    assert forms == {"SCHEDULE 13D", "SCHEDULE 13G/A", "4"}
    companies = {r.entities[0] for r in records}
    assert "Tesla, Inc." in companies
    assert "Acme Widgets Corp" not in companies  # form 4 not on watch
    d13 = next(r for r in records if r.raw["form"] == "SCHEDULE 13D")
    assert d13.url.endswith("0001193125-26-395888.txt")


def test_regsho_parse():
    text = (
        "Symbol|Security Name|Market Category|Reg SHO Threshold Flag|Rule 3210|Filler\n"
        "AAPD|DIREXION SHS ETF|G|Y|N|\n"
        "AMOD|ALPHA MODUS HLDGS|S|Y|N|\n"
    )
    records = parse_threshold(text, dt.datetime.now(dt.timezone.utc))
    assert [r.uid for r in records] == ["regsho:AAPD", "regsho:AMOD"]


def test_cot_parse_and_filter():
    rows = [
        {
            "market_and_exchange_names": "GOLD - COMMODITY EXCHANGE INC.",
            "cftc_contract_market_code": "088691",
            "report_date_as_yyyy_mm_dd": "2026-09-15T00:00:00.000",
            "open_interest_all": "400000",
            "noncomm_positions_long_all": "250000",
            "noncomm_positions_short_all": "50000",
        },
        {
            "market_and_exchange_names": "BUTTER (CASH SETTLED) - CHICAGO MERCANTILE EXCHANGE",
            "cftc_contract_market_code": "052641",
            "report_date_as_yyyy_mm_dd": "2026-09-15T00:00:00.000",
            "open_interest_all": "10000",
            "noncomm_positions_long_all": "5000",
            "noncomm_positions_short_all": "1000",
        },
    ]
    records = parse_report(rows, ["GOLD"])
    assert len(records) == 1
    assert records[0].uid == "cot:088691"
    assert records[0].metrics["net_pct_oi"] == 0.5


def test_usgs_parse_min_magnitude():
    payload = {
        "features": [
            {"id": "us1", "properties": {"mag": 7.1, "time": 1758300000000,
                                         "title": "M 7.1 - somewhere", "place": "somewhere", "url": "u"}},
            {"id": "us2", "properties": {"mag": 4.9, "time": 1758300000000,
                                         "title": "M 4.9 - elsewhere", "place": "elsewhere", "url": "u"}},
        ]
    }
    records = parse_quakes(payload, 6.0)
    assert [r.uid for r in records] == ["usgs:us1"]
    assert records[0].metrics["magnitude"] == 7.1


def test_openfda_parse():
    payload = {
        "results": [
            {"recall_number": "D-123-2026", "recalling_firm": "Pfizer",
             "classification": "Class I", "product_description": "Drug X 10mg tablets",
             "report_date": "20260917", "reason_for_recall": "contamination"}
        ]
    }
    records = parse_recalls(payload)
    assert records[0].uid == "fda:D-123-2026"
    assert "Pfizer" in records[0].title


def test_defillama_parse_orders_and_floors():
    payload = [
        {"slug": "big", "name": "Big", "tvl": 5e9},
        {"slug": "small", "name": "Small", "tvl": 1e6},
        {"slug": "mid", "name": "Mid", "tvl": 2e8},
    ]
    records = parse_protocols(payload, min_tvl=1e8, top=10)
    assert [r.uid for r in records] == ["llama:big", "llama:mid"]


def test_crtsh_skips_without_domains():
    with pytest.raises(ConfigSkip):
        CrtSh({}).fetch()


def test_crtsh_parse_window():
    now = dt.datetime.now(dt.timezone.utc)
    payload = [
        {"id": 1, "entry_timestamp": now.replace(tzinfo=None).isoformat(),
         "name_value": "new.example.com", "issuer_name": "R3"},
        {"id": 2, "entry_timestamp": "2020-01-01T00:00:00",
         "name_value": "old.example.com", "issuer_name": "R3"},
    ]
    records = parse_certs(payload, "example.com", now - dt.timedelta(days=30))
    assert len(records) == 1
    assert "new.example.com" in records[0].title
