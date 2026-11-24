"""Shared constants, palette and formatting helpers."""
from . import i18n

SRCS = ("oc", "zc", "cc", "dh", "ob")
NAME = {"oc": "opencode", "zc": "zcode", "cc": "claude", "dh": "dsh", "ob": "openbot"}
SRC_OF = {v: k for k, v in NAME.items()}
# soft colours on a fixed night-blue background
COLOR = {"oc": "#63d3c4", "zc": "#c3a6ff", "cc": "#f4a98a", "dh": "#7fb2ff", "ob": "#a5d68f"}
KEY_OF = {"o": "oc", "z": "zc", "c": "cc", "e": "dh", "b": "ob"}
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

