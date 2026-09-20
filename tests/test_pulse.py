import datetime as dt

from argus.core.base import Connector, Record, ScanResult
from argus.core.state import StateStore
from argus.html_report import render_html, svg_sparkline
from argus.report import pulse_lines, render, spark, week_delta


def series_record(name: str, series: list[float]) -> Record:
    return Record(
        uid=f"t:{name}", source="t", category="c",
        ts=dt.datetime.now(dt.timezone.utc), title=name,
        series=series, series_name=name,
    )


def test_spark_shapes():
    s = spark([1, 2, 3, 4, 5, 6, 7, 8])
    assert s[0] == "▁" and s[-1] == "█"
    assert spark([5, 5, 5]) == "▁▁▁"  # flat series doesn't crash
    assert spark([1]) == ""


def test_spark_downsamples():
    assert len(spark(list(range(200)), width=24)) == 24


def test_week_delta():
    import pytest
    assert week_delta([100] * 7 + [110]) == pytest.approx(0.10)
    assert week_delta([100, 50]) == pytest.approx(-0.5)  # short series falls back to first
    assert week_delta([5]) is None


def test_scan_collects_pulse(tmp_path):
    class Fake(Connector):
        name = "fake_pulse"
        category = "c"

        def fetch(self):
            return [
                series_record("GPR", [100.0] * 10),
                Record(uid="t:x", source="t", category="c",
                       ts=dt.datetime.now(dt.timezone.utc), title="no series"),
            ]

    result = Fake({}).scan(StateStore(tmp_path / "s.db"))
    assert [r.series_name for r in result.pulse] == ["GPR"]


def test_pulse_in_markdown_even_when_quiet():
    r = ScanResult("gpr", "geopolitical-risk", [], 1, False,
                   pulse=[series_record("GPR", [100.0, 120.0, 90.0, 110.0, 130.0])])
    text = render([r], [], "2026-09-20")
    assert "## Market pulse" in text
    assert "GPR: 130" in text
    assert "▁" in text or "█" in text


def test_pulse_in_html_with_sparkline():
    r = ScanResult("gpr", "geopolitical-risk", [], 1, False,
                   pulse=[series_record("GPR", [100.0, 120.0, 90.0, 110.0, 130.0])])
    html = render_html([r], [], "2026-09-20")
    assert "market pulse" in html
    assert "<svg class=\"spark\"" in html
    assert "+30% wk" in html  # 130 vs first point 100


def test_svg_sparkline_direction_colors():
    assert "#34d399" in svg_sparkline([1.0, 2.0, 3.0])
    assert "#f87171" in svg_sparkline([3.0, 2.0, 1.0])
    assert svg_sparkline([1.0]) == ""
