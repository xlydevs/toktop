"""Plain-text summary (also used when stdout is not a terminal)."""
import os
import sys
from datetime import date, timedelta

from . import i18n
from .common import COLOR, NAME, SRCS, human, human_full, seg_widths
from .history import load_history
from .i18n import t
from .stats import by_day, by_model, by_src, filt, totals

# ───────────────────────── plain text ─────────────────────────

def render_text(srcs):
    A = {"r": "\033[0m", "b": "\033[1m", "g": "\033[90m", "c": "\033[36m", "w": "\033[97m"}
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        A = dict.fromkeys(A, "")

    def hexc(h):
        return "" if not A["r"] else f"\033[38;2;{int(h[1:3], 16)};{int(h[3:5], 16)};{int(h[5:7], 16)}m"

    rows, sess, meta = load_history()
    rows = filt(rows, srcs)
    if not rows:
        print(t("No data yet.")); return
    tt = totals(rows)
    print(f"  {A['b']}{A['w']}{human_full(tt['total'])}{A['r']} {A['g']}{t('tokens')}{A['r']}  ·  "
          f"{A['c']}{tt['sessions']}{A['r']} {A['g']}{t('sessions')}{A['r']}  ·  {A['g']}{t('updated')} {meta.get('last_sync', '?')}{A['r']}")
    print(f"  {A['g']}" + t("input {inp} · output {out} · cache {cr} · reas {reas}", inp=human(tt['inp']), out=human(tt['out']),
          cr=human(tt['cr']), reas=human(tt['reas'])) + f"{A['r']}\n")
    bs = by_src(rows)
    for s in SRCS:
        if bs[s]:
            n = int(bs[s] / tt["total"] * 30)
            print(f"  {hexc(COLOR[s])}{'█' * max(1, n)}{A['r']}{' ' * (30 - max(1, n))} {NAME[s]:<9} {human(bs[s]):>8} {bs[s] / tt['total'] * 100:4.0f}%")
    print(f"\n  {A['b']}{t('Top models')}{A['r']}")
    for name, tag, s, _, v in by_model(rows)[:8]:
        print(f"  {name[:28]:<28} {hexc(COLOR[s])}{tag[:12]:<12}{A['r']} {human(v['total']):>8} {v['total'] / tt['total'] * 100:5.1f}%")
    print(f"\n  {A['b']}{t('Last 7 days')}{A['r']}")
    days, ses = by_day(rows)
    last = [(date.today() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    mx = max((sum(days.get(d, {}).values()) for d in last), default=0) or 1
    for d in last:
        v = days.get(d, {})
        tot = sum(v.values())
        w = max(1, int(tot / mx * 30)) if tot else 0
        bar = "".join(f"{hexc(COLOR[s])}{'█' * n}{A['r']}" for s, n in zip(SRCS, seg_widths([v.get(s, 0) for s in SRCS], w)))
        dt = date.fromisoformat(d)
        print(f"  {i18n.days_1()[dt.weekday()]} {dt.day:>2}/{dt.month:<2} {bar}{' ' * (30 - w)} {human(tot):>8} {A['g']}({ses.get(d, 0)} {t('sess')}){A['r']}")


