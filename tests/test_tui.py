import pytest

from toktop import config, demo, i18n
from toktop.common import SRCS


@pytest.mark.parametrize("lang", ["en", "es"])
@pytest.mark.parametrize("size", [(160, 48), (80, 40)])
async def test_tui_smoke(lang, size):
    config.OFFLINE = True
    demo.populate()
    i18n.set_lang(lang)
    from toktop.tui import make_app
    app = make_app(set(SRCS))
    async with app.run_test(size=size) as pilot:
        await pilot.pause(0.3)
        while app.syncing:
            await pilot.pause(0.1)
        assert app.rows
        for key in ("2", "3", "4", "5", "1"):
            await pilot.press(key)
            await pilot.pause(0.1)
        await pilot.press("2")
        await pilot.click("#cell-10")
        await pilot.press("left", "right", "p", "c", "t")
        await pilot.pause(0.2)
        assert app.srcs == set(SRCS)


async def test_first_run_picker_saves_choice(monkeypatch, tmp_path):
    import toktop.tui as tui
    from toktop import onboard
    from toktop.common import KIND
    monkeypatch.setattr(tui, "refresh_prices", lambda force=False: False)
    app = tui.make_app(set(SRCS))
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        assert isinstance(app.screen, onboard.AppsScreen)
        sel = app.screen.query_one("#apps")
        sel.deselect_all()
        sel.select("gm")
        sel.select("ad")
        await pilot.click("#save")
        await pilot.pause(0.3)
        assert SRCS == ["gm", "ad"] and KIND["ad"] == "manual"
        assert isinstance(app.screen, onboard.SetupScreen)  # aider needs its log set up
        assert "analytics-log" in app.screen.text
        await pilot.click("#close")
        await pilot.press("a")
        await pilot.pause(0.2)
        assert isinstance(app.screen, onboard.AppsScreen)
    text = (tmp_path / "config.toml").read_text()
    assert 'enabled = ["gemini", "aider"]' in text
    config.CONFIG = {}
