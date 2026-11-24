"""Textual TUI."""
from datetime import date, datetime, timedelta

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.theme import Theme
from textual.widget import Widget
from textual.widgets import Button, DataTable, Footer, Input, Static, TabbedContent, TabPane

from . import config, i18n
from .common import (
    ACCENT,
    BG,
    BRIGHT,
    COLOR,
    DIM,
    FG,
    KEY_OF,
    MUTED,
    NAME,
    OK_C,
    PANEL,
    SRCS,
    SURF,
    WARN_C,
    human,
    human_full,
    money,
    seg_widths,
    tidy_name,
)
from .history import load_history, sync
from .i18n import t
from .prices import norm_model, price_for, prices, refresh_prices
from .stats import PERIODS, api_value, by_day, by_model, by_session, by_src, filt, period_range, row_cost, totals, what_if

EIGHTHS = " ▁▂▃▄▅▆▇█"
HEAT = ["#1b2333", "#26335a", "#33487e", "#4562a6", "#6a88d0"]  # heat map (indigo, neutral against the sources)
CELL = ["#161e2d", "#1d2843", "#253457", "#2e416d", "#3a5287"]  # calendar cells (text on top)
SEL_BG, HOVER_BG = "#5a4a32", "#243049"

THEME = Theme(name="toktop", primary=ACCENT, secondary="#c3a6ff", accent=ACCENT, foreground=FG,
            background=BG, surface=SURF, panel=PANEL, success=OK_C, warning=WARN_C,
            error="#f28b82", dark=True,
            variables={"block-cursor-background": "#2a3754", "block-cursor-foreground": BRIGHT,
                       "block-cursor-text-style": "none", "block-cursor-blurred-background": "#202a40",
                       "block-cursor-blurred-foreground": FG, "block-hover-background": "#1c2538",
                       "footer-key-foreground": ACCENT, "input-selection-background": "#33415f"})

def level(v, mx):
    if not v or not mx: return 0
    return 1 + min(3, int((v / mx) ** 0.5 * 4))

def seg_text(vals, width, ch="█"):
    out = Text()
    for s, n in zip(SRCS, seg_widths([vals.get(s, 0) for s in SRCS], width)):
        if n: out.append(ch * n, style=COLOR[s])
    return out

def src_line(vals, total=None):
    """'● opencode 1.2M  ● claude 30M' with colours."""
    out = Text()
    for s in SRCS:
        if vals.get(s):
            out.append("● ", style=COLOR[s])
            out.append(f"{NAME[s]} {human(vals[s])}", style="#d6deeb")
            if total: out.append(f" {vals[s] / total * 100:.0f}%", style=MUTED)
            out.append("   ")
    return out

def day_title(d, long=False):
    dt = date.fromisoformat(d)
    return i18n.long_date(dt) if long else i18n.short_date(dt)

# ── column chart stacked by source ──
class ColumnChart(Widget):
    DEFAULT_CSS = "ColumnChart { height: 1fr; min-height: 8; }"
    hover = reactive(-1)
    YL = 8

    class Picked(Message):
        def __init__(self, day):
            super().__init__()
            self.day = day

    def __init__(self, **kw):
        super().__init__(**kw)
        self.days, self.start, self.end = {}, None, None
        self._bk, self._key, self._colw = [], None, 1

    def set_data(self, days, start, end):
        self.days, self.start, self.end, self._key = days, start, end, None
        self.refresh()

    def buckets(self, avail):
        key = (avail, self.start, self.end, id(self.days))
        if key == self._key: return self._bk
        s, e = date.fromisoformat(self.start), date.fromisoformat(self.end)
        n = (e - s).days + 1
        groups = []  # (label, title, days)
        if n <= avail:
            for i in range(n):
                d = s + timedelta(days=i)
                groups.append((str(d.day), day_title(d.isoformat()), [d]))
        else:
            ws = s - timedelta(days=s.weekday())
            weeks = (e - ws).days // 7 + 1
            if weeks <= avail:
                for w in range(weeks):
                    a = ws + timedelta(days=7 * w)
                    ds = [a + timedelta(days=i) for i in range(7) if s <= a + timedelta(days=i) <= e]
                    groups.append((f"{a.day}/{a.month}", t("week of {day} {month}", day=a.day, month=i18n.months_s()[a.month - 1]), ds))
            else:
                cur = s.replace(day=1)
                while cur <= e:
                    nxt = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
                    ds = [cur + timedelta(days=i) for i in range((nxt - cur).days) if s <= cur + timedelta(days=i) <= e]
                    groups.append((i18n.months_s()[cur.month - 1], f"{i18n.months()[cur.month - 1]} {cur.year}", ds))
                    cur = nxt
        bk = []
        for lab, title, ds in groups:
            vals = {}
            for d in ds:
                for k, v in self.days.get(d.isoformat(), {}).items():
                    vals[k] = vals.get(k, 0) + v
            bk.append({"lab": lab, "title": title, "vals": vals, "tot": sum(vals.values()),
                       "day": ds[0].isoformat(), "today": date.today() in ds})
        self._bk, self._key = bk, key
        return bk

    def render(self):
        w, h = self.size.width, self.size.height
        if w < 16 or h < 4 or not self.start: return Text("")
        avail = w - self.YL
        bk = self.buckets(avail)
        n = len(bk) or 1
        colw = max(1, min(avail // n, 7))
        bw = colw - 1 if colw >= 2 else 1
        self._colw = colw
        ch = h - 2
        mx = max((b["tot"] for b in bk), default=0) or 1
        stacks = []
        for b in bk:
            e8 = round(b["tot"] / mx * ch * 8)
            if b["tot"] and not e8: e8 = 1
            full, rem = divmod(e8, 8)
            rows = []
            for s, k in zip(SRCS, seg_widths([b["vals"].get(s, 0) for s in SRCS], full)):
                rows += [s] * k
            top = rows[-1] if rows else max(b["vals"], key=b["vals"].get, default="oc")
            stacks.append((full, rem, rows, top))
        out = Text(no_wrap=True, overflow="crop")
        for r in range(ch - 1, -1, -1):
            lab = human(mx) if r == ch - 1 else (human(mx / 2) if r == (ch - 1) // 2 and ch > 4 else "")
            out.append(f"{lab:>6} " + ("┤" if lab else "│"), style="#4b5570")
            for i, (full, rem, rows, top) in enumerate(stacks):
                bg = " on #243049" if i == self.hover else ""
                if r < full:
                    out.append("█" * bw, style=COLOR[rows[r]] + bg)
                elif r == full and rem:
                    out.append(EIGHTHS[rem] * bw, style=COLOR[top] + bg)
                else:
                    out.append(" " * bw, style=bg.strip() or None)
                if colw > bw: out.append(" " * (colw - bw))
            out.append("\n")
        # x axis
        axis = [" "] * avail
        maxl = max((len(b["lab"]) for b in bk), default=1)
        step = max(1, -(-(maxl + 1) // colw))
        for i in range(0, len(bk), step):
            lab = bk[i]["lab"]
            for j, c in enumerate(lab):
                if i * colw + j < avail: axis[i * colw + j] = c
        out.append(" " * self.YL + "".join(axis) + "\n", style=MUTED)
        # info line
        if 0 <= self.hover < len(bk):
            b = bk[self.hover]
            out.append(f"  {b['title']}", style="bold")
            out.append(f"  {human_full(b['tot'])} {t('tokens')}   ", style="#d6deeb")
            out.append_text(src_line(b["vals"]))
        else:
            tot = sum(b["tot"] for b in bk)
            out.append("  " + t("total {tot} · max {mx}", tot=human(tot), mx=human(mx)), style=MUTED)
            out.append("  ·  " + t("hover over a column, click opens the day"), style="#4b5570")
        return out

    def _col(self, event):
        off = event.get_content_offset(self)
        if off is None or off.x < self.YL or off.y >= self.size.height - 2: return -1
        i = (off.x - self.YL) // max(1, self._colw)
        return i if i < len(self._bk) else -1

    def on_mouse_move(self, event):
        self.hover = self._col(event)

    def on_leave(self, event):
        self.hover = -1

    def on_click(self, event):
        i = self._col(event)
        if i >= 0: self.post_message(self.Picked(self._bk[i]["day"]))

# ── heat map of the last year ──
class Heatmap(Widget):
    DEFAULT_CSS = "Heatmap { height: 9; }"
    hover = reactive("")

    class Picked(Message):
        def __init__(self, day):
            super().__init__()
            self.day = day

    def __init__(self, **kw):
        super().__init__(**kw)
        self.days = {}
        self._start, self._cw, self._pad = date.today(), 2, 0

    def set_data(self, days):
        self.days = days
        self.refresh()

    def render(self):
        w = self.size.width
        if w < 20: return Text("")
        today = date.today()
        cw = 3 if w - 4 >= 53 * 3 else 2
        self._cw = cw
        weeks = max(4, min(53, (w - 4) // cw))
        pad = " " * max(0, (w - 4 - weeks * cw) // 2)
        self._pad = len(pad)
        start = today - timedelta(days=today.weekday()) - timedelta(days=7 * (weeks - 1))
        self._start = start
        span = [start + timedelta(days=i) for i in range((today - start).days + 1)]
        mx = max((sum(self.days.get(d.isoformat(), {}).values()) for d in span), default=0)
        out = Text(no_wrap=True, overflow="crop")
        months = [" "] * (weeks * cw)
        prev = None
        for c in range(weeks):
            d = start + timedelta(days=7 * c)
            if d.month != prev and c * cw + 3 <= weeks * cw and months[max(0, c * cw - 1)] == " ":
                for j, ch in enumerate(i18n.months_s()[d.month - 1]): months[c * cw + j] = ch
            prev = d.month
        out.append(pad + "    " + "".join(months) + "\n", style=MUTED)
        for r in range(7):
            out.append(pad + f" {i18n.days_1()[r] if r in (0, 2, 4) else ' '}  ", style=MUTED)
            for c in range(weeks):
                d = start + timedelta(days=7 * c + r)
                if d > today:
                    out.append(" " * cw)
                    continue
                k = d.isoformat()
                v = sum(self.days.get(k, {}).values())
                style = HEAT[level(v, mx)]
                if k == self.hover: style = "bold " + ACCENT
                elif d == today: style += " bold"
                out.append("■" + " " * (cw - 1), style=style)
            out.append("\n")
        if self.hover:
            v = self.days.get(self.hover, {})
            out.append(pad + f"  {day_title(self.hover, True)}  ", style="bold")
            out.append(f"{human_full(sum(v.values()))} {t('tokens')}   ", style="#d6deeb")
            out.append_text(src_line(v))
        else:
            out.append(pad + "  " + t("less") + " ", style=MUTED)
            for c in HEAT: out.append("■ ", style=c)
            out.append(t("more") + "   ·  " + t("click a day to open it in the calendar"), style=MUTED)
        return out

    def _day(self, event):
        off = event.get_content_offset(self)
        x = off.x - self._pad - 4 if off else -1
        if x < 0 or not (1 <= off.y <= 7): return ""
        d = self._start + timedelta(days=7 * (x // self._cw) + off.y - 1)
        return d.isoformat() if d <= date.today() else ""

    def on_mouse_move(self, event):
        self.hover = self._day(event)

    def on_leave(self, event):
        self.hover = ""

    def on_click(self, event):
        d = self._day(event)
        if d: self.post_message(self.Picked(d))

# ── calendar cell: colour block, no borders ──
class DayCell(Widget):
    DEFAULT_CSS = """
    DayCell { height: 3; padding: 0 1; }
    DayCell:hover { tint: white 7%; }
    DayCell.-out { background: transparent; }
    DayCell.-out:hover { tint: transparent; }
    """

    class Picked(Message):
        def __init__(self, day):
            super().__init__()
            self.day = day

    def __init__(self, **kw):
        super().__init__(**kw)
        self.day, self.vals, self.ses, self.lvl, self.sel = None, {}, 0, 0, False

    def setup(self, day, vals, ses, lvl, sel):
        self.day, self.vals, self.ses, self.lvl = day, vals, ses, lvl
        self.set_class(day is None, "-out")
        self.select(sel)

    def select(self, sel):
        self.sel = bool(sel and self.day)
        self.styles.background = None if not self.day else (SEL_BG if self.sel else CELL[self.lvl])
        self.refresh()

    def render(self):
        if not self.day: return Text("")
        w = self.size.width - 2
        dt = date.fromisoformat(self.day)
        tot = sum(self.vals.values())
        today = self.day == date.today().isoformat()
        future = dt > date.today()
        l1 = Text(no_wrap=True, overflow="crop")
        num = f"{dt.day}"
        l1.append(num, style=("bold " + ACCENT) if (today or self.sel) else (DIM if future or not tot else "bold " + FG))
        if today and w >= len(num) + 4: l1.append(" " + t("today"), style=ACCENT)
        l2 = Text(human(tot) if tot else "", style="bold " + BRIGHT, no_wrap=True, overflow="crop")
        l3 = seg_text(self.vals, max(0, w), "▂") if tot else Text("")
        return Text("\n", no_wrap=True).join([l1, l2, l3])

    def on_click(self, event):
        if self.day: self.post_message(self.Picked(self.day))

class TokensApp(App):
    TITLE = "toktop"
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (96, "-medium"), (150, "-wide")]
    CSS = """
    Screen { background: $background; }
    * { scrollbar-color: #263044; scrollbar-color-hover: #33415f; scrollbar-color-active: #f2cc8f;
        scrollbar-background: #0f1420; scrollbar-background-hover: #0f1420; scrollbar-background-active: #0f1420; }
    #top { height: 1; padding: 0 1; background: $surface; }
    #brand { width: auto; color: $accent; text-style: bold; padding-right: 2; }
    #periods, #chips { width: auto; height: 1; }
    #periods { padding-right: 2; }
    #top Button { min-width: 4; margin: 0 1 0 0; background: $surface; color: #7c879f; border: none; text-style: none; }
    #top Button:hover { background: #222c42; }
    #periods Button:hover { color: #eef2fa; }
    #periods Button.-on { background: #f2cc8f; color: #0f1420; text-style: bold; }
    #periods Button.-on:hover { background: #f6d9a8; color: #0f1420; }
    #chips Button.-on { text-style: bold; }
    #chips Button.-off { text-style: strike; }
    #status { width: 1fr; content-align: right middle; color: #7c879f; }
    .-narrow #status { display: none; }
    .-narrow #top { layout: vertical; height: 2; }
    .-narrow #brand { display: none; }
    TabbedContent { height: 1fr; }
    Tabs { background: $background; }
    Tab { color: #7c879f; }
    Tab:hover { color: #eef2fa; }
    Tab.-active { color: #f2cc8f; text-style: bold; }
    TabPane { padding: 0 1; }
    .box { border: round #263044; border-title-color: #7c879f; border-title-style: bold; padding: 0 1; background: $background; }
    #kpis { grid-size: 6; grid-gutter: 0 1; grid-rows: 5; height: auto; margin-top: 1; }
    .-medium #kpis { grid-size: 3; }
    .-narrow #kpis { grid-size: 2; }
    .kpi { border: round #263044; border-title-color: #7c879f; padding: 0 1; height: 5; }
    #heat-box { height: auto; align-horizontal: center; }
    #home-mid { height: auto; }
    #chart-box { width: 1fr; height: 18; }
    #side { width: 52; height: auto; }
    .-narrow #home-mid { layout: vertical; }
    .-narrow #side { width: 1fr; }
    #by-src, #top-models { height: auto; }
    #cal-nav { height: 1; margin-top: 1; }
    #cal-nav Button { min-width: 5; margin-right: 1; background: #1a2335; color: #d6deeb; border: none; text-style: none; }
    #cal-nav Button:hover { background: #2a3754; color: #f2cc8f; }
    #cal-title { width: 1fr; content-align: center middle; text-style: bold; color: #eef2fa; }
    #cal-sum { height: auto; margin: 1 0 0 0; content-align: center middle; text-align: center; }
    #cal-body { height: 1fr; margin-top: 1; }
    #cal-left { width: 1fr; height: auto; }
    #cal-head { grid-size: 7; grid-gutter: 0 1; height: 1; margin-bottom: 1; }
    #cal-head Static { content-align: left middle; padding: 0 1; color: #7c879f; }
    #cal-grid { grid-size: 7; grid-rows: 3; grid-gutter: 1 1; height: auto; }
    #detail-box { width: 50; height: 1fr; margin-left: 2; border: none; border-left: solid #263044; padding: 0 2; }
    .-narrow #cal-body { layout: vertical; overflow-y: auto; }
    .-narrow #detail-box { width: 1fr; height: auto; min-height: 12; margin: 1 0 0 0; border-left: none; border-top: solid #263044; padding: 1 0 0 0; }
    .bar { height: 1; margin-top: 1; }
    .bar Static { width: 1fr; color: #7c879f; }
    DataTable { height: 1fr; margin-top: 1; background: $background; }
    DataTable:focus { background-tint: transparent; }
    DataTable > .datatable--header { background: $surface; color: #7c879f; text-style: bold; }
    DataTable:focus > .datatable--header { background-tint: transparent; }
    DataTable > .datatable--even-row { background: #121826; }
    DataTable > .datatable--hover { background: #1c2538; }
    DataTable > .datatable--header-hover { background: #222c42; color: #f2cc8f; }
    DataTable > .datatable--cursor, DataTable:focus > .datatable--cursor { background: #2a3754; text-style: none; }
    #search { margin-top: 1; border: round #263044; background: $background; padding: 0 1; }
    #search:focus { border: round #f2cc8f; }
    #sess-info { height: 4; border-top: hkey #263044; color: #d6deeb; }
    #price-head { height: auto; margin-top: 1; padding: 0 1; }
    #price-notes { height: auto; color: #7c879f; margin-top: 1; padding: 0 1; }
    #price-table { height: auto; max-height: 24; }
    Footer { background: $surface; }
    """
    BINDINGS = [
        Binding("q", "quit", t("quit")),
        Binding("escape", "unfocus", show=False),
        Binding("left", "time(-1)", t("back"), key_display="←"),
        Binding("right", "time(1)", t("forward"), key_display="→"),
        Binding("p", "cycle_period", t("period")),
        Binding("t", "src('t')", t("sources"), key_display="t/o/z/c/e/b"),
        *[Binding(k, f"src('{k}')", show=False) for k in KEY_OF],
        Binding("slash", "search", t("search"), key_display="/"),
        Binding("r", "resync", t("sync")),
        *[Binding(str(i + 1), f"tab('{tab}')", show=False) for i, tab in
          enumerate(("home", "calendar", "models", "sessions", "prices"))],
    ]

    def __init__(self, srcs, start_tab="home"):
        super().__init__()
        self.start_tab = start_tab
        self.rows, self.sess, self.meta = [], {}, {}
        self.srcs = set(srcs)
        self.period = "30d"
        self.cal_month = date.today().replace(day=1)
        self.sel_day = date.today().isoformat()
        self.found, self.errors, self.syncing = set(), [], False
        self.sorts = {"models-table": ("total", True), "sess-table": ("total", True)}
        self.tdata = {}
        self.query_text = ""

    # ── structure ──
    def compose(self) -> ComposeResult:
        with Horizontal(id="top"):
            yield Static("◈ toktop", id="brand")
            with Horizontal(id="periods"):
                for k, lbl in PERIODS:
                    yield Button(t(lbl), id=f"per-{k}", compact=True)
            with Horizontal(id="chips"):
                for s in SRCS:
                    yield Button(f"● {NAME[s]}", id=f"chip-{s}", compact=True)
            yield Static("", id="status")
        with TabbedContent(initial="home", id="tabs"):
            with TabPane(t("Home"), id="home"):
                with VerticalScroll():
                    with Grid(id="kpis"):
                        for k in ("tok", "ses", "avg", "inp", "out", "cache"):
                            yield Static("", id=f"kpi-{k}", classes="kpi")
                    with Vertical(id="heat-box", classes="box"):
                        yield Heatmap(id="heat")
                    with Horizontal(id="home-mid"):
                        with Vertical(id="chart-box", classes="box"):
                            yield ColumnChart(id="cols")
                        with Vertical(id="side"):
                            yield Static("", id="by-src", classes="box")
                            yield Static("", id="top-models", classes="box")
            with TabPane(t("Calendar"), id="calendar"):
                with Horizontal(id="cal-nav"):
                    yield Button("◀", id="cal-prev", compact=True)
                    yield Static("", id="cal-title")
                    yield Button(t("today"), id="cal-today", compact=True)
                    yield Button("▶", id="cal-next", compact=True)
                yield Static("", id="cal-sum")
                with Horizontal(id="cal-body"):
                    with Vertical(id="cal-left"):
                        with Grid(id="cal-head"):
                            for d in i18n.days_s(): yield Static(d)
                        with Grid(id="cal-grid"):
                            for i in range(42): yield DayCell(id=f"cell-{i}")
                    with VerticalScroll(id="detail-box"):
                        yield Static("", id="day-detail")
            with TabPane(t("Models"), id="models"):
                with Horizontal(classes="bar"):
                    yield Static("", id="models-hint")
                yield DataTable(id="models-table", cursor_type="row", zebra_stripes=True,
                                cursor_foreground_priority="renderable")
            with TabPane(t("Sessions"), id="sessions"):
                yield Input(placeholder=t("search by title, project, model or source…"), id="search")
                yield DataTable(id="sess-table", cursor_type="row", zebra_stripes=True,
                                cursor_foreground_priority="renderable")
                yield Static("", id="sess-info")
            with TabPane(t("Prices"), id="prices"):
                with VerticalScroll():
                    yield Static("", id="price-head")
                    yield DataTable(id="price-table", show_cursor=False, zebra_stripes=True)
                    yield Static("", id="price-notes")
        yield Footer()

    def on_mount(self):
        self.register_theme(THEME)
        self.theme = "toktop"
        for wid, title in (("chart-box", t("Usage per day")), ("by-src", t("By source")),
                           ("top-models", t("Top models")), ("heat-box", t("Last year"))):
            self.query_one(f"#{wid}").border_title = title
        for k, tt in (("tok", t("Tokens")), ("ses", t("Sessions")), ("avg", t("Daily average")),
                      ("inp", t("Input excl. cache")), ("out", t("Output")), ("cache", t("Cache read"))):
            self.query_one(f"#kpi-{k}").border_title = tt
        self.rows, self.sess, self.meta = load_history()
        self.refresh_all()
        if self.start_tab != "home": self.action_tab(self.start_tab)
        self.action_resync()

    # ── background sync ──
    @work(thread=True, exclusive=True)
    def do_sync(self, rebuild=False):
        found, errors = sync(rebuild)
        data = load_history()
        self.call_from_thread(self.synced, data, found, errors)
        if refresh_prices(force=rebuild):
            prices()
            self.call_from_thread(self.render_prices)
            self.call_from_thread(self.render_models)

    def synced(self, data, found, errors):
        self.rows, self.sess, self.meta = data
        self.found, self.errors, self.syncing = found, errors, False
        self.refresh_all()
        if errors: self.notify("\n".join(errors), title=t("Error reading an app"), severity="warning", timeout=10)

    def action_resync(self):
        if self.syncing: return
        self.syncing = True
        self.update_status()
        self.do_sync()

    # ── shared state ──
    def first_day(self):
        return min((r[2] for r in self.rows), default=None)

    def prange(self):
        return period_range(self.period, self.first_day())

    def prows(self):
        s, e = self.prange()
        return filt(self.rows, self.srcs, s, e)

    def update_status(self):
        tt = Text()
        if self.syncing:
            tt.append("⟳ " + t("reading apps…"), style=THEME.accent)
        else:
            tt.append(f"✓ {self.meta.get('last_sync', '—')[-5:]}", style="#a5d68f")
            hist = [] if config.OFFLINE else [NAME[s] for s in SRCS if s not in self.found and any(r[0] == s for r in self.rows)]
            if hist: tt.append("  ·  " + t("history only: {apps}", apps=", ".join(hist)), style=THEME.warning)
        self.query_one("#status").update(tt)

    def refresh_all(self):
        avail = {r[0] for r in self.rows} | self.found
        for s in SRCS:
            chip = self.query_one(f"#chip-{s}")
            chip.display = s in avail
            chip.set_class(s in self.srcs, "-on")
            chip.set_class(s not in self.srcs, "-off")
            chip.styles.color = COLOR[s] if s in self.srcs else "#3a4358"
            chip.tooltip = (f"{NAME[s]}: " + (t("read now") if s in self.found else t("app not found, history data"))
                            + " · " + t("click to show/hide"))
        for k, _ in PERIODS:
            self.query_one(f"#per-{k}").set_class(k == self.period, "-on")
        self.update_status()
        self.render_home()
        self.render_calendar()
        self.render_models()
        self.render_sessions()
        self.render_prices()

    # ── Home ──
    def render_home(self):
        rows = self.prows()
        s, e = self.prange()
        tt = totals(rows)
        ndays = (date.fromisoformat(e) - date.fromisoformat(s)).days + 1
        days, _ = by_day(rows)
        today = days.get(date.today().isoformat(), {})
        peak = max(days.items(), key=lambda kv: sum(kv[1].values()), default=(None, {}))

        def kpi(k, big, sub, color="#eef2fa"):
            txt = Text(no_wrap=True, overflow="ellipsis")
            txt.append(big + "\n", style=f"bold {color}")
            txt.append(sub, style=MUTED)
            self.query_one(f"#kpi-{k}").update(txt)

        kpi("tok", human_full(tt["total"]), f"{human(tt['total'])} · {t('today')} {human(sum(today.values()))}", THEME.accent)
        kpi("ses", human_full(tt["sessions"]), f"{human(tt['total'] // tt['sessions']) if tt['sessions'] else 0} {t('per session')}")
        kpi("avg", human(tt["total"] / ndays), f"{t('peak')} {human(sum(peak[1].values()))}" + (f" · {day_title(peak[0])}" if peak[0] else ""))
        share = lambda v: f"{v / tt['total'] * 100:.1f}% {t('of total')}" if tt["total"] else "—"
        kpi("inp", human(tt["inp"] + tt["cw"]), share(tt["inp"] + tt["cw"]))
        kpi("out", human(tt["out"] + tt["reas"]), share(tt["out"] + tt["reas"]))
        read = tt["cr"] + tt["inp"] + tt["cw"]
        kpi("cache", human(tt["cr"]), f"{t('hits')} {tt['cr'] / read * 100:.1f}% {t('of input')}" if read else "—", "#9cc8e8")
        per = t(dict(PERIODS)[self.period]).lower()
        self.query_one("#chart-box").border_title = f"{t('Usage')} · {per}"
        self.query_one("#cols", ColumnChart).set_data(days, s, e)
        # by source
        bs = by_src(rows)
        txt = Text(no_wrap=True, overflow="ellipsis")
        mxs = max(bs.values()) or 1
        for src in SRCS:
            if not bs[src]: continue
            txt.append("● ", style=COLOR[src])
            txt.append(f"{NAME[src]:<9}", style="#d6deeb")
            txt.append(f"{human(bs[src]):>8}", style="bold #eef2fa")
            txt.append(f" {bs[src] / tt['total'] * 100:4.0f}% ", style=MUTED)
            txt.append("█" * max(1, int(bs[src] / mxs * 20)), style=COLOR[src])
            txt.append("\n")
        self.query_one("#by-src").update(txt if bs and tt["total"] else Text(t("no usage in this period"), style=MUTED))
        # top models
        txt = Text(no_wrap=True, overflow="ellipsis")
        models = by_model(rows)[:7]
        mxm = models[0][4]["total"] if models else 1
        for name, tag, src, _, v in models:
            txt.append(f"{name[:20]:<20} ", style="#d6deeb")
            txt.append(f"{tag[:10]:<10}", style=COLOR[src])
            txt.append(f"{human(v['total']):>8} ", style="bold #eef2fa")
            txt.append("█" * max(1, int(v["total"] / mxm * 7)), style=COLOR[src])
            txt.append("\n")
        self.query_one("#top-models").update(txt if models else Text("—", style=MUTED))
        yr_days, _ = by_day(filt(self.rows, self.srcs))
        self.query_one("#heat", Heatmap).set_data(yr_days)

    # ── Calendar ──
    def render_calendar(self):
        m = self.cal_month
        self.query_one("#cal-title").update(f"{i18n.months()[m.month - 1].capitalize()} {m.year}")
        fd = self.first_day()
        self.query_one("#cal-prev").disabled = bool(fd) and m <= date.fromisoformat(fd).replace(day=1)
        self.query_one("#cal-next").disabled = m >= date.today().replace(day=1)
        nxt = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
        rows = filt(self.rows, self.srcs, m.isoformat(), (nxt - timedelta(days=1)).isoformat())
        days, ses = by_day(rows)
        tt = totals(rows)
        mx = max((sum(v.values()) for v in days.values()), default=0)
        txt = Text(justify="center")
        txt.append(human_full(tt["total"]), style="bold " + THEME.accent)
        txt.append(f" {t('tokens')}  ·  ", style=MUTED)
        txt.append(str(tt["sessions"]), style="bold #eef2fa")
        txt.append(f" {t('sessions')}  ·  ", style=MUTED)
        txt.append(f"{human(tt['total'] / max(1, len(days)))}", style="bold #eef2fa")
        txt.append(f" {t('per active day')}\n", style=MUTED)
        txt.append_text(src_line(by_src(rows), tt["total"]))
        self.query_one("#cal-sum").update(txt)
        lead = m.weekday()
        ndays = (nxt - m).days
        if not self.sel_day.startswith(m.isoformat()[:7]):
            today = date.today()
            self.sel_day = (today if today.replace(day=1) == m else m).isoformat()
        for i in range(42):
            cell = self.query_one(f"#cell-{i}", DayCell)
            dn = i - lead + 1
            if 1 <= dn <= ndays:
                d = m.replace(day=dn).isoformat()
                v = days.get(d, {})
                cell.setup(d, v, ses.get(d, 0), level(sum(v.values()), mx), d == self.sel_day)
            else:
                cell.setup(None, {}, 0, 0, False)
            cell.display = not (i >= 35 and lead + ndays <= 35)
        self.render_detail()

    def render_detail(self):
        d = self.sel_day
        rows = filt(self.rows, self.srcs, d, d)
        tt = totals(rows)
        txt = Text()
        txt.append((lambda x: x[:1].upper() + x[1:])(day_title(d, True)) + "\n", style="bold " + BRIGHT)
        if not rows:
            txt.append(t("No usage this day."), style=MUTED)
            self.query_one("#day-detail").update(txt)
            return
        txt.append(human_full(tt["total"]), style="bold " + THEME.accent)
        txt.append(f" {t('tokens')} · {tt['sessions']} {t('sessions')}\n", style=MUTED)
        txt.append(t("input {inp} · output {out} · cache {cr}", inp=human(tt["inp"] + tt["cw"]), out=human(tt["out"] + tt["reas"]), cr=human(tt["cr"])) + "\n\n", style=MUTED)
        bs = by_src(rows)
        txt.append_text(seg_text(bs, 40, "▬"))
        txt.append("\n")
        for s in SRCS:
            if bs[s]:
                txt.append("● ", style=COLOR[s])
                txt.append(f"{NAME[s]:<9}", style="#d6deeb")
                txt.append(f"{human(bs[s]):>8}", style="bold #eef2fa")
                txt.append(f"  {bs[s] / tt['total'] * 100:3.0f}%\n", style=MUTED)
        txt.append("\n" + t("MODELS") + "\n", style="bold " + MUTED)
        for name, _tag, s, _, v in by_model(rows)[:8]:
            txt.append("▍", style=COLOR[s])
            txt.append(f"{name[:26]:<26}", style="#d6deeb")
            txt.append(f"{human(v['total']):>8}\n", style="#eef2fa")
        txt.append("\n" + t("SESSIONS") + "\n", style="bold " + MUTED)
        for (s, sid), a in sorted(by_session(rows).items(), key=lambda kv: kv[1]["total"], reverse=True)[:10]:
            title, proj, first, _ = self.sess.get((s, sid), ("", "", "", ""))
            label = title or proj or sid[:12]
            txt.append("▍", style=COLOR[s])
            txt.append(f"{label[:30]:<30}", style="#d6deeb")
            txt.append(f"{human(a['total']):>8}\n", style="#eef2fa")
            if title and proj:
                txt.append(f"  {proj[:36]}\n", style=MUTED)
        self.query_one("#day-detail").update(txt)

    # ── sortable tables ──
    def fill(self, tid, cols, data):
        """cols = [(key, title, align)]; data = [{key: value, key+'_r': Text}]"""
        self.tdata[tid] = (cols, data)
        key, rev = self.sorts.get(tid, (cols[0][0], False))
        data = sorted(data, key=lambda r: (r[key].lower() if isinstance(r[key], str) else r[key]), reverse=rev)
        tbl = self.query_one(f"#{tid}", DataTable)
        cur = tbl.cursor_row
        tbl.clear(columns=True)
        for k, lbl, _ in cols:
            arrow = (" ▼" if rev else " ▲") if k == key else ""
            tbl.add_column(Text(lbl + arrow, justify="right" if _ == "r" else "left"), key=k)
        for r in data:
            cells = [r.get(k + "_r") or Text(str(r[k]), justify="right" if j == "r" else "left") for k, _, j in cols]
            tbl.add_row(*cells, key=r.get("_key"))
        if data: tbl.move_cursor(row=min(cur, len(data) - 1))

    def on_data_table_header_selected(self, event):
        tid = event.data_table.id
        if tid not in self.sorts or tid not in self.tdata: return
        key = event.column_key.value
        if key == "bar": key = "total"
        k0, rev = self.sorts[tid]
        self.sorts[tid] = (key, not rev) if key == k0 else (key, key not in ("name", "tag", "title", "project", "src", "first"))
        self.fill(tid, *self.tdata[tid])

    def render_models(self):
        rows = self.prows()
        tt = totals(rows)["total"] or 1
        models = by_model(rows)
        mx = models[0][4]["total"] if models else 1
        data = []
        for name, tag, s, full, v in models:
            pr = price_for(full)
            api = row_cost((0,) * 5 + (v["inp"], v["out"], v["cr"], v["cw"], v["reas"]), pr) if pr else -1
            data.append({"api": api, "api_r": Text(money(api) if pr else "—", style=FG if pr else DIM, justify="right"),
                         "name": name, "tag": tag, "total": v["total"], "inp": v["inp"] + v["cw"], "out": v["out"] + v["reas"],
                         "cr": v["cr"], "sessions": v["sessions"], "pct": v["total"] / tt * 100, "bar": v["total"],
                         "name_r": Text(name, style="#eef2fa"), "tag_r": Text(tag, style=COLOR[s]),
                         "total_r": Text(human_full(v["total"]), style="bold " + THEME.accent, justify="right"),
                         "inp_r": Text(human(v["inp"] + v["cw"]), justify="right"),
                         "out_r": Text(human(v["out"] + v["reas"]), justify="right"),
                         "cr_r": Text(human(v["cr"]), style="#9cc8e8", justify="right"),
                         "sessions_r": Text(str(v["sessions"]), justify="right"),
                         "pct_r": Text(f"{v['total'] / tt * 100:.1f}%", style=MUTED, justify="right"),
                         "bar_r": Text("█" * max(1, int(v["total"] / mx * 20)), style=COLOR[s])})
        self.fill("models-table", [("name", t("Model"), "l"), ("tag", t("Source"), "l"), ("total", t("Tokens"), "r"),
                                   ("inp", t("Input"), "r"), ("out", t("Output"), "r"), ("cr", t("Cache"), "r"),
                                   ("sessions", t("Sess."), "r"), ("api", "$ API", "r"), ("pct", "%", "r"),
                                   ("bar", "", "l")], data)
        self.query_one("#models-hint").update(
            f"{len(data)} {t('models')} · {t(dict(PERIODS)[self.period]).lower()} · {t('click a header to sort')}")

    def render_sessions(self):
        rows = self.prows()
        q = self.query_text.lower()
        data = []
        for (s, sid), a in by_session(rows).items():
            title, proj, first, last = self.sess.get((s, sid), ("", "", "", ""))
            main = max(a["models"], key=a["models"].get)
            hay = f"{title} {proj} {main} {NAME[s]} {sid}".lower()
            if q and q not in hay: continue
            read = a["cr"] + a["inp"] + a["cw"]
            hit = a["cr"] / read * 100 if read else 0
            data.append({"_key": f"{s}|{sid}", "first": first or min(a["days"]), "src": NAME[s], "project": proj,
                         "title": title or "—", "model": tidy_name(main), "total": a["total"], "hit": hit,
                         "first_r": Text(first or min(a["days"]), style=MUTED),
                         "src_r": Text(NAME[s], style=COLOR[s]),
                         "project_r": Text(proj or "—", style="#d6deeb"),
                         "title_r": Text(title or "—", style="#eef2fa"),
                         "total_r": Text(human_full(a["total"]), style="bold " + THEME.accent, justify="right"),
                         "hit_r": Text(f"{hit:.0f}%", style=MUTED, justify="right")})
        self.fill("sess-table", [("first", t("First"), "l"), ("src", t("Source"), "l"), ("project", t("Project"), "l"),
                                 ("title", t("Title"), "l"), ("model", t("Model"), "l"), ("total", t("Tokens"), "r"),
                                 ("hit", t("Cache"), "r")], data)
        self.query_one("#sess-info").update(Text(
            f"{len(data)} {t('sessions')} · {t(dict(PERIODS)[self.period]).lower()}" + (f" · {t('filter')} «{self.query_text}»" if q else ""),
            style=MUTED))

    def on_data_table_row_highlighted(self, event):
        if event.data_table.id != "sess-table" or event.row_key is None or not event.row_key.value: return
        s, sid = event.row_key.value.split("|", 1)
        a = by_session([r for r in self.prows() if r[0] == s and r[1] == sid]).get((s, sid))
        if not a: return
        title, proj, first, last = self.sess.get((s, sid), ("", "", "", ""))
        txt = Text(no_wrap=True, overflow="ellipsis")
        txt.append(title or t("(untitled)"), style="bold #eef2fa")
        txt.append(f"   {NAME[s]} · {proj or '—'} · {first} → {last[-5:] if last else ''}\n", style=MUTED)
        for m, v in sorted(a["models"].items(), key=lambda kv: kv[1], reverse=True)[:4]:
            txt.append(f"{tidy_name(m)} ", style="#d6deeb")
            txt.append(f"{human(v)}   ", style=THEME.accent)
        txt.append(f"\n{len(a['days'])} {t('day(s)')} · id {sid}", style="#4b5570")
        self.query_one("#sess-info").update(txt)

    def on_input_changed(self, event):
        if event.input.id == "search":
            self.query_text = event.value.strip()
            self.render_sessions()

    def render_prices(self):
        rows = self.prows()
        tt = totals(rows)
        period = t(dict(PERIODS)[self.period]).lower()
        txt = Text()
        txt.append(t("What if every token had gone through a single model?") + "\n", style="bold " + BRIGHT)
        if self.period == "all":
            sim = t("Simulation: all {tokens} tokens spent so far, at real API prices, with no subscriptions or discounts.",
                    tokens=human(tt["total"]))
        else:
            sim = t("Simulation: the {tokens} tokens of {period}, at real API prices, with no subscriptions or discounts.",
                    tokens=human(tt["total"]), period=period)
        txt.append(sim, style=MUTED)
        self.query_one("#price-head").update(txt)
        res = what_if(rows)
        mx = max((c for _, c, *_ in res), default=0) or 1
        used = {norm_model(n) for n, *_ in by_model(rows)}
        tbl = self.query_one("#price-table", DataTable)
        tbl.clear(columns=True)
        for k, lbl in (("m", t("Model")), ("c", t("Cost")), ("b", "")):
            tbl.add_column(lbl, key=k)
        for name, c, *_ in res:
            mine = norm_model(name) in used
            tbl.add_row(Text(("● " if mine else "  ") + name, style=BRIGHT if mine else FG),
                        Text(money(c), style="bold " + ACCENT, justify="right"),
                        Text("█" * max(1, int(c / mx * 40)), style=ACCENT if mine else DIM))
        cost, priced = api_value(rows)
        _, src, upd = prices()
        when = ""
        if upd:
            try:
                u = datetime.fromisoformat(upd)
                when = f" {u.day:02d}/{u.month:02d}"
            except ValueError:
                pass
        foot = Text()
        foot.append("● ", style=BRIGHT)
        foot.append(t("used in this period") + "\n", style=MUTED)
        foot.append(t("with the models you actually used") + " ", style=MUTED)
        foot.append(money(cost), style=FG)
        if tt["total"] and priced < tt["total"]:
            foot.append(" " + t("({pct}% of tokens have a known price)", pct=f"{priced / tt['total'] * 100:.0f}"), style=DIM)
        foot.append("\n" + t("prices") + ": ", style=MUTED)
        foot.append((t("built-in table") if src == "builtin" else src) + when, style=DIM)
        self.query_one("#price-notes").update(foot)

    # ── events ──
    def on_button_pressed(self, event):
        bid = event.button.id or ""
        if bid.startswith("per-"):
            self.period = bid[4:]
            self.refresh_all()
        elif bid.startswith("chip-"):
            self.toggle_src(bid[5:])
        elif bid in ("cal-prev", "cal-next"):
            self.shift_month(-1 if bid == "cal-prev" else 1)
        elif bid == "cal-today":
            self.cal_month = date.today().replace(day=1)
            self.sel_day = date.today().isoformat()
            self.render_calendar()

    def toggle_src(self, s):
        if s in self.srcs and len(self.srcs) == 1: return
        self.srcs ^= {s}
        self.refresh_all()

    def open_day(self, d):
        self.sel_day = d
        self.cal_month = date.fromisoformat(d).replace(day=1)
        self.render_calendar()
        self.action_tab("calendar")

    def on_column_chart_picked(self, event):
        self.open_day(event.day)

    def on_heatmap_picked(self, event):
        self.open_day(event.day)

    def on_day_cell_picked(self, event):
        self.sel_day = event.day
        for i in range(42):
            c = self.query_one(f"#cell-{i}", DayCell)
            c.select(c.day == event.day)
        self.render_detail()

    def shift_month(self, d):
        y, mo = divmod(self.cal_month.year * 12 + self.cal_month.month - 1 + d, 12)
        nm = date(y, mo + 1, 1)
        fd = self.first_day()
        if nm > date.today().replace(day=1) or (fd and nm < date.fromisoformat(fd).replace(day=1)):
            self.bell(); return
        self.cal_month = nm
        self.render_calendar()

    def action_time(self, d):
        if self.query_one("#tabs", TabbedContent).active == "calendar":
            self.shift_month(d)
        else:
            keys = [k for k, _ in PERIODS]
            self.period = keys[(keys.index(self.period) + d) % len(keys)]
            self.refresh_all()

    def action_cycle_period(self):
        keys = [k for k, _ in PERIODS]
        self.period = keys[(keys.index(self.period) + 1) % len(keys)]
        self.refresh_all()

    def action_src(self, k):
        if k == "t":
            self.srcs = set(SRCS)
            self.refresh_all()
        else:
            self.toggle_src(KEY_OF[k])

    def action_unfocus(self):
        self.set_focus(None)

    def action_search(self):
        self.action_tab("sessions")
        self.query_one("#search").focus()

    def action_tab(self, tab):
        tabs = self.query_one("#tabs", TabbedContent)
        self.set_focus(None)  # otherwise the focus left on the old tab reactivates it
        tabs.active = tab

    def on_tabbed_content_tab_activated(self, event):
        target = {"models": "#models-table", "sessions": "#sess-table", "prices": "#price-table"}.get(event.pane.id)
        if target: self.query_one(target).focus()


def make_app(srcs, start_tab="home"):
    return TokensApp(srcs, start_tab)
