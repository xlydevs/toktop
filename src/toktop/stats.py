"""Aggregations over usage rows."""
from datetime import date, timedelta

from .common import NAME, SRCS, tidy_name
from .prices import BUILTIN_PRICES, norm_model, price_for, prices


def rtot(r):
    return r[5] + r[6] + r[7] + r[8] + r[9]


def filt(rows, srcs, start=None, end=None):
    return [r for r in rows if r[0] in srcs and (start is None or start <= r[2] <= end)]


def totals(rows):
    t = {"inp": 0, "out": 0, "cr": 0, "cw": 0, "reas": 0}
    ses = set()
    for r in rows:
        t["inp"] += r[5]; t["out"] += r[6]; t["cr"] += r[7]; t["cw"] += r[8]; t["reas"] += r[9]
        ses.add((r[0], r[1]))
    t["total"] = t["inp"] + t["out"] + t["cr"] + t["cw"] + t["reas"]
    t["sessions"] = len(ses)
    return t


def by_day(rows):
    """{day: {src: tokens}} and {day: number of sessions}"""
    days, ses = {}, {}
    for r in rows:
        d = days.setdefault(r[2], {})
        d[r[0]] = d.get(r[0], 0) + rtot(r)
        ses.setdefault(r[2], set()).add((r[0], r[1]))
    return days, {k: len(v) for k, v in ses.items()}


def by_src(rows):
    out = dict.fromkeys(SRCS, 0)
    for r in rows: out[r[0]] += rtot(r)
    return out


def by_model(rows):
    """[(name, label, src, model, {inp,out,cr,cw,reas,total,sessions})] sorted by usage."""
    agg = {}
    for r in rows:
        a = agg.setdefault((r[3], r[4], r[0]), [0, 0, 0, 0, 0, set()])
        for i in range(5): a[i] += r[5 + i]
        a[5].add(r[1])
    out = []
    for (m, p, s), a in agg.items():
        total = sum(a[:5])
        if not total: continue
        tag = p if s == "oc" and p else NAME[s]
        out.append([tidy_name(m), tag, s, m, {"inp": a[0], "out": a[1], "cr": a[2], "cw": a[3], "reas": a[4],
                                               "total": total, "sessions": len(a[5])}])
    out.sort(key=lambda x: x[4]["total"], reverse=True)
    # two models that shorten to the same label get their full name back
    keys = [(n, t) for n, t, *_ in out]
    for x in out:
        if keys.count((x[0], x[1])) > 1: x[0] = x[3]
    return out


def by_session(rows):
    agg = {}
    for r in rows:
        a = agg.setdefault((r[0], r[1]), {"total": 0, "inp": 0, "cr": 0, "cw": 0, "models": {}, "days": set()})
        t = rtot(r)
        a["total"] += t; a["inp"] += r[5]; a["cr"] += r[7]; a["cw"] += r[8]
        a["models"][r[3]] = a["models"].get(r[3], 0) + t
        a["days"].add(r[2])
    return agg


def row_cost(r, p):
    pi, pc, po, pw = p
    return (r[5] * pi + r[8] * pw + r[7] * pc + (r[6] + r[9]) * po) / 1e6


def api_value(rows):
    """API-price cost of the models with a known rate: (cost, tokens with a rate)."""
    cost = priced = 0
    for r in rows:
        p = price_for(r[3])
        if not p: continue
        cost += row_cost(r, p)
        priced += rtot(r)
    return cost, priced


def what_if(rows):
    """Cost of all usage with a single model: the ones you use (with a rate) and the reference ones."""
    t = totals(rows)
    tbl = prices()[0]
    names = [n for n, *_ in by_model(rows) if price_for(n)][:12]
    names += [n for n in BUILTIN_PRICES if norm_model(n) in tbl]
    seen, res = set(), []
    for n in names:
        k = norm_model(n)
        if k in seen: continue
        seen.add(k)
        pi, pc, po, pw = tbl[k]
        c = (t["inp"] * pi + t["cw"] * pw + t["cr"] * pc + (t["out"] + t["reas"]) * po) / 1e6
        res.append((tidy_name(n), c, pi, pc, po))
    return sorted(res, key=lambda x: x[1])


PERIODS = [("7d", "7 days"), ("30d", "30 days"), ("month", "This month"), ("year", "This year"), ("all", "All")]


def period_range(p, first_day=None):
    t = date.today()
    s = {"7d": t - timedelta(days=6), "30d": t - timedelta(days=29), "month": t.replace(day=1),
         "year": t.replace(month=1, day=1)}.get(p)
    if s is None:
        s = date.fromisoformat(first_day) if first_day else t
    return s.isoformat(), t.isoformat()


