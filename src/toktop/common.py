"""Shared constants, palette and formatting helpers."""
from . import i18n

# key (stored in the history, never change it), short name, label, colour, kind
#   auto: toktop finds and reads the app's own files
#   manual: the app has to be set up to write a usage log (toktop shows instructions)
APPS = (
    ("cc", "claude", "Claude Code", "#f4a98a", "auto"),
    ("cx", "codex", "Codex CLI", "#e8ecf2", "auto"),
    ("gm", "gemini", "Gemini CLI", "#5fa8f5", "auto"),
    ("qw", "qwen", "Qwen Code", "#9d8cff", "auto"),
    ("oc", "opencode", "opencode", "#63d3c4", "auto"),
    ("gs", "goose", "Goose", "#e8d36a", "auto"),
    ("am", "amp", "Amp", "#ff6b57", "auto"),
    ("cl", "cline", "Cline", "#b8c4d6", "auto"),
    ("ro", "roo", "Roo Code", "#c98bff", "auto"),
    ("ki", "kilo", "Kilo Code", "#f8f675", "auto"),
    ("zd", "zed", "Zed", "#4c8dff", "auto"),
    ("zc", "zcode", "zcode", "#c3a6ff", "auto"),
    ("ob", "openbot", "OpenBot", "#a5d68f", "auto"),
    ("dh", "dsh", "dsh (deepseek-harness)", "#7fb2ff", "manual"),
    ("ad", "aider", "Aider", "#3fcf5e", "manual"),
)
ALL = tuple(a[0] for a in APPS)
NAME = {a[0]: a[1] for a in APPS}
LABEL = {a[0]: a[2] for a in APPS}
COLOR = {a[0]: a[3] for a in APPS}
KIND = {a[0]: a[4] for a in APPS}
SRC_OF = {v: k for k, v in NAME.items()}
SRCS = list(ALL)  # sources in use; changed in place (other modules import this same list)
KEY_OF = {"o": "oc", "z": "zc", "c": "cc", "e": "dh", "b": "ob"}


def set_enabled(keys):
    SRCS[:] = [k for k in ALL if k in set(keys)]


def set_colors(custom):
    """[colors] in the config file: name = "#rrggbb"."""
    for name, col in (custom or {}).items():
        k = SRC_OF.get(name)
        if k and isinstance(col, str) and len(col) == 7 and col.startswith("#"):
            COLOR[k] = col


BG, SURF, PANEL, BORDER = "#0f1420", "#141b2a", "#1a2335", "#263044"
FG, BRIGHT, MUTED, DIM = "#d6deeb", "#eef2fa", "#7c879f", "#4b5570"
ACCENT, CACHE_C, OK_C, WARN_C = "#f2cc8f", "#9cc8e8", "#a5d68f", "#f2cc8f"

def human(n):
    n = int(n or 0)
    if n >= 1_000_000_000_000: return f"{n / 1e12:.2f}T"
    if n >= 1_000_000_000: return f"{n / 1e9:.2f}B"
    if n >= 1_000_000: return f"{n / 1e6:.1f}M" if n >= 100_000_000 else f"{n / 1e6:.2f}M"
    if n >= 1_000: return f"{n / 1e3:.1f}k"
    return str(n)


def human_full(n):
    s = f"{int(n or 0):,}"
    return s.replace(",", ".") if i18n.LANG == "es" else s


def money(x):
    return f"${x:,.2f}"


def tidy_name(mid):
    """Short model name: no provider prefix and no free/contributor suffixes."""
    s = (mid or "?").split("/")[-1]
    if s.endswith(":free"): s = s[:-5]
    toks = s.split("-")
    while toks and toks[-1] in ("free", "contributor"): toks.pop()
    return "-".join(toks) or (mid or "?")


def seg_widths(vals, width):
    """Split `width` cells across the values (the sum is exactly width)."""
    tot = sum(vals)
    if tot <= 0 or width <= 0: return [0] * len(vals)
    exact = [width * v / tot for v in vals]
    w = [int(e) for e in exact]
    for i in sorted(range(len(vals)), key=lambda i: exact[i] - w[i], reverse=True)[:width - sum(w)]:
        w[i] += 1
    return w

