from argus.connectors.federal_register import parse_document
from argus.connectors.gdelt import parse_articles
from argus.connectors.ofac_sdn import parse_sdn_csv
from argus.connectors.polymarket import parse_market


def test_parse_market_yes_outcome():
    r = parse_market({
        "id": "123",
        "question": "Will the Fed cut in December?",
        "slug": "fed-cut-december",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.72", "0.28"]',
        "volume24hr": 150000.5,
    })
    assert r.uid == "polymarket:123"
    assert r.metrics["probability"] == 0.72
    assert r.metrics["volume_24h"] == 150000.5
    assert "fed-cut-december" in r.url


def test_parse_market_malformed_returns_none():
    assert parse_market({"id": "1", "outcomePrices": "not json"}) is None
    assert parse_market({"id": "2", "outcomePrices": "[]"}) is None


def test_parse_fedreg_document():
    r = parse_document({
        "document_number": "2026-12345",
        "title": "Amendments to Form PF",
        "publication_date": "2026-09-18",
        "html_url": "https://www.federalregister.gov/d/2026-12345",
        "type": "Rule",
        "agencies": [{"name": "Securities and Exchange Commission"}],
    })
    assert r.uid == "fedreg:2026-12345"
    assert r.entities == ["Securities and Exchange Commission"]
    assert r.raw["type"] == "Rule"


def test_parse_sdn_csv_skips_junk_rows():
    text = (
        '12345,"ACME SHIPPING LLC","-0-","IRAN-EO13902",-0-,-0-,-0-,-0-,-0-,-0-,-0-,"remarks"\n'
        '99999,"SOME PERSON","individual","SDGT",-0-,-0-,-0-,-0-,-0-,-0-,-0-,"remarks"\n'
        'not_a_number,junk,row\n'
    )
    records = parse_sdn_csv(text)
    assert len(records) == 2
    assert records[0].uid == "ofac:12345"
    assert "ACME SHIPPING LLC" in records[0].title
    assert records[1].raw["sdn_type"] == "individual"


def test_parse_gdelt_articles():
    records = parse_articles({
        "articles": [
            {
                "url": "https://example.com/story",
                "title": "New export controls announced",
                "seendate": "20260919T140000Z",
                "domain": "example.com",
                "sourcecountry": "US",
            }
        ]
    })
    assert len(records) == 1
    assert records[0].uid.startswith("gdelt:")
    assert records[0].ts.year == 2026
