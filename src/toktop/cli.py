"""Command line entry point."""
import argparse
import sys
import tempfile

from . import __version__, config, i18n
from .common import NAME, SRC_OF, SRCS, set_enabled
from .i18n import t


def main(argv=None):
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--lang", choices=i18n.SUPPORTED)
    known, _ = pre.parse_known_args(argv)
    if known.lang:
        i18n.set_lang(known.lang)

    ap = argparse.ArgumentParser(prog="toktop", description=t("Token usage across your AI coding tools, in the terminal."))
    ap.add_argument("-s", "--source", choices=["all", *NAME.values()], default="all",
                    help=t("start showing only this source"))
    ap.add_argument("--text", action="store_true", help=t("plain-text summary, no TUI"))
    ap.add_argument("--rebuild", action="store_true",
                    help=t("rebuild the history from the installed apps (data from deleted apps is kept)"))
    ap.add_argument("--demo", action="store_true", help=t("explore with made-up data (reads nothing, writes nothing)"))
    ap.add_argument("--lang", choices=i18n.SUPPORTED, help=t("interface language"))
    ap.add_argument("-V", "--version", action="version", version=f"toktop {__version__}")
    args = ap.parse_args(argv)
    if args.demo:
        from . import demo
        tmp = tempfile.mkdtemp(prefix="toktop-demo-")
        config.set_data_dir(tmp)
        config.OFFLINE = True
        demo.populate()
        set_enabled(demo.SHARE)

    if args.source != "all" and SRC_OF[args.source] not in SRCS:
        set_enabled([*SRCS, SRC_OF[args.source]])
    srcs = set(SRCS) if args.source == "all" else {SRC_OF[args.source]}
    from .history import sync
    if args.rebuild:
        found, errors = sync(rebuild=True)
        print(t("History rebuilt from: {apps}", apps=", ".join(NAME[s] for s in SRCS if s in found) or t("no app")))
        for e in errors:
            print(f"  {t('error')}:", e)
        return
    if args.text or not sys.stdout.isatty():
        from .text import render_text
        _, errors = sync()
        for e in errors:
            print(f"  {t('error')}:", e, file=sys.stderr)
        render_text(srcs)
        return
    from .tui import make_app
    make_app(srcs).run()


if __name__ == "__main__":
    main()
