import datetime as dt

from argus.core.base import Finding, Record, ScanResult
from argus.html_report import _prob_bar, render_html


def finding(title: str, importance: int = 2, url: str = "https://example.com", **kw) -> Finding:
    return Finding(
        Record(
            uid="t:1", source="test", category="test",
            ts=dt.datetime.now(dt.timezone.utc), title=title, url=url,
        ),
        reason="new",
        importance=importance,
        **kw,
    )


def test_render_html_basic_structure():
    hit = finding("Export controls tightened", importance=4)
    hit.watchlist = ["export controls"]
    results = [
        ScanResult("federal_register", "regulatory", [hit], 50, False),
        ScanResult("ofac_sdn", "sanctions", [], 17000, False),
        ScanResult("polymarket", "prediction-markets", [], 0, False),
    ]
    html = render_html(results, [("gdelt", RuntimeError("boom"))], "2026-09-20")
    assert "<!doctype html>" in html
    assert "ARGUS" in html
    assert "Export controls tightened" in html
    assert "watchlist hits" in html
    assert "quiet — no changes" in html.replace("&#8212;", "—") or "quiet" in html
    assert "high-priority signal" in html          # importance 4 triggers the banner
    assert 'class="led warn"' in html              # 0-record polymarket
    assert 'class="led fail"' in html and "boom" in html


def test_render_html_escapes_content():
    evil = finding("<script>alert(1)</script>", url='https://x.com/?a="><script>')
    html = render_html([ScanResult("s", "c", [evil], 5, False)], [], "2026-09-20")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_prob_bar_directions():
    up = _prob_bar({"from": 0.40, "to": 0.60})
    assert "up" in up and "40%" in up and "60%" in up and "+20pp" in up
    down = _prob_bar({"from": 0.60, "to": 0.40})
    assert "down" in down and "-20pp" in down
    assert _prob_bar({}) == ""
    assert _prob_bar({"from": "x"}) == ""
