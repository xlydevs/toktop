from datetime import date, timedelta

from toktop import common, stats

ROWS = [  # (src, sid, day, model, provider, inp, out, cr, cw, reas)
    ("cc", "a", "2026-01-01", "claude-opus-5-5", "anthropic", 1_000_000, 100_000, 10_000_000, 0, 0),
    ("oc", "b", "2026-01-02", "deepseek-v4.1-flash", "opencode-go", 2_000_000, 200_000, 0, 0, 50_000),
    ("oc", "b", "2026-01-03", "deepseek-v4.1-flash", "opencode-go", 1, 1, 1, 1, 1),
]


def test_totals_and_grouping():
    t = stats.totals(ROWS)
    assert t["total"] == sum(stats.rtot(r) for r in ROWS)
    assert t["sessions"] == 2
    assert stats.by_src(ROWS)["oc"] == 2_250_005
    days, ses = stats.by_day(ROWS)
    assert set(days) == {"2026-01-01", "2026-01-02", "2026-01-03"} and ses["2026-01-02"] == 1
    top = stats.by_model(ROWS)[0]
    assert top[0] == "claude-opus-5-5" and top[4]["sessions"] == 1


def test_filter_by_source_and_period():
    assert len(stats.filt(ROWS, {"oc"})) == 2
    assert len(stats.filt(ROWS, {"cc", "oc"}, "2026-01-02", "2026-01-02")) == 1


def test_period_range():
    today = date.today()
    assert stats.period_range("7d") == ((today - timedelta(days=6)).isoformat(), today.isoformat())
    assert stats.period_range("all", "2025-05-01") == ("2025-05-01", today.isoformat())
    assert all(stats.period_range(k)[1] == today.isoformat() for k, _ in stats.PERIODS)


def test_api_value_uses_known_prices():
    cost, priced = stats.api_value(ROWS[:1])
    assert priced == stats.rtot(ROWS[0]) and cost > 0
    res = stats.what_if(ROWS)
    assert res == sorted(res, key=lambda x: x[1])
    assert any(n == "claude-opus-5-5" for n, *_ in res)


def test_formatting_helpers():
    assert common.human(1_234) == "1.2k"
    assert common.human(2_500_000_000) == "2.50B"
    assert common.human(3_000_000_000_000) == "3.00T"
    assert common.tidy_name("nvidia/foo-bar-free") == "foo-bar"
    assert sum(common.seg_widths([3, 1, 0], 10)) == 10
    assert common.seg_widths([0, 0], 5) == [0, 0]
