"""API prices: fetched from OpenRouter once a day, with a built-in fallback table."""
import json
from datetime import datetime

from . import config
from .common import tidy_name

# USD prices per 1M tokens: (input, cached_input, output). Fallback only: the real prices
# are downloaded from OpenRouter once a day (see refresh_prices).
BUILTIN_PRICES = {
    "gpt-6-luna":           (0.10, 0.01,  0.50),
    "deepseek-v4.1-flash":  (0.15, 0.003, 0.60),
    "glm-5.3-flash":        (0.15, 0.03,  0.50),
    "claude-haiku-5-5":     (0.10, 0.01,  0.50),
    "claude-sonnet-5-5":    (2.00, 0.20,  10.00),
    "gpt-6.1-sol":          (2.00, 0.10,  10.00),
    "kimi-k3":              (3.00, 0.30,  15.00),
    "claude-opus-5-5":      (4.00, 0.20,  20.00),
    "claude-fable-5-2":     (8.00, 0.20,  40.00),
    "gpt-6-astra":          (10.00, 1.00, 50.00),
    "muse-wonder-1.0":      (4.00, 0.20,  20.00),
}

# ───────────────────────── prices (OpenRouter, once a day) ─────────────────────────

PRICE_URL = "https://openrouter.ai/api/v1/models"
PRICE_TTL = 24 * 3600
_PRICES = None  # norm -> (input, cached, output, cache_write) in $/1M


def norm_model(mid):
    s = tidy_name(mid).lower().replace(".", "-")
    toks = s.split("-")
    while len(toks) > 1 and toks[-1].isdigit() and len(toks[-1]) >= 6: toks.pop()  # date suffix
    return "-".join(toks)


def cache_file():
    return config.DATA / "prices.json"


def refresh_prices(force=False):
    """Download OpenRouter's public price list if the cached copy is older than a day. Anonymous request."""
    if config.OFFLINE: return False
    PRICE_CACHE = cache_file()
    try:
        if not force and PRICE_CACHE.exists() and datetime.now().timestamp() - PRICE_CACHE.stat().st_mtime < PRICE_TTL:
            return False
        import urllib.request
        req = urllib.request.Request(PRICE_URL, headers={"User-Agent": "toktop"})
        with urllib.request.urlopen(req, timeout=10) as r:
            models = json.load(r).get("data") or []
    except Exception:
        return False
    out = {}
    for m in models:
        mid = m.get("id") or ""
        if ":" in mid: continue  # variants :free, :batch, :thinking…
        p = m.get("pricing") or {}
        try:
            pi, po = float(p.get("prompt") or 0), float(p.get("completion") or 0)
            pc = float(p.get("input_cache_read") or pi)
            pw = float(p.get("input_cache_write") or pi)
        except (TypeError, ValueError):
            continue
        if min(pi, po, pc, pw) < 0 or not (pi or po): continue
        k = norm_model(mid)
        exact = mid.split("/")[-1].lower().replace(".", "-") == k  # the exact id beats its variants
        if k not in out or (exact and not out[k][5]):
            out[k] = [round(x * 1e6, 6) for x in (pi, pc, po, pw)] + [mid, exact]
    if not out: return False
    config.DATA.mkdir(parents=True, exist_ok=True)
    tmp = PRICE_CACHE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"source": "OpenRouter", "updated": datetime.now().isoformat(timespec="minutes"),
                               "prices": out}), encoding="utf-8")
    tmp.replace(PRICE_CACHE)
    global _PRICES
    _PRICES = None
    return True


def prices():
    """(table, source, date). The OpenRouter cache if it exists, otherwise the fallback table."""
    global _PRICES
    if _PRICES is None:
        tbl = {norm_model(k): (pi, pc, po, pi) for k, (pi, pc, po) in BUILTIN_PRICES.items()}
        src, upd = "builtin", ""
        try:
            d = json.loads(cache_file().read_text(encoding="utf-8"))
            live = {k: tuple(v[:4]) for k, v in d["prices"].items()}
            if live:
                tbl = {**tbl, **live}
                src, upd = d.get("source", "OpenRouter"), d.get("updated", "")
        except (OSError, ValueError, KeyError, TypeError):
            pass
        _PRICES = (tbl, src, upd)
    return _PRICES


def price_for(model):
    return prices()[0].get(norm_model(model))


