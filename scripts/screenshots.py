"""Regenerate docs/screenshots/*.svg from demo data: python scripts/screenshots.py"""
import asyncio
import tempfile

from toktop import config, demo, i18n

config.set_data_dir(tempfile.mkdtemp())
config.OFFLINE = True
i18n.set_lang("en")
demo.populate()

from toktop.common import SRCS  # noqa: E402
from toktop.stats import by_day  # noqa: E402
from toktop.tui import make_app  # noqa: E402


async def main():
    app = make_app(set(SRCS))
    async with app.run_test(size=(150, 46)) as pilot:
        await pilot.pause(0.5)
        while app.syncing:
            await pilot.pause(0.1)
        await pilot.hover("#cols", offset=(60, 8))
        await pilot.pause(0.3)
        app.save_screenshot("docs/screenshots/home.svg")
        days, _ = by_day(app.prows())
        busiest = max(days, key=lambda d: sum(days[d].values()))
        app.open_day(busiest)
        await pilot.pause(0.3)
        app.save_screenshot("docs/screenshots/calendar.svg")
        await pilot.press("3")
        await pilot.pause(0.3)
        app.save_screenshot("docs/screenshots/models.svg")
        await pilot.press("5")
        await pilot.pause(0.3)
        app.save_screenshot("docs/screenshots/prices.svg")


asyncio.run(main())
