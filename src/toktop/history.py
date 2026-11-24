"""Own history database: usage never decreases, so deleted apps keep their counts."""
import sqlite3
from datetime import datetime

from . import config, sources
from .common import NAME

# ───────────────────────── history ─────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage(src TEXT, sid TEXT, day TEXT, model TEXT, provider TEXT,
  inp INTEGER, out INTEGER, cr INTEGER, cw INTEGER, reas INTEGER, PRIMARY KEY(src, sid, day, model, provider));
CREATE TABLE IF NOT EXISTS sessions(src TEXT, sid TEXT, title TEXT, project TEXT, first TEXT, last TEXT,
  PRIMARY KEY(src, sid));
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""


def hist_connect():
    config.DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.history_db(), timeout=10)
    con.executescript(SCHEMA)
    migrate(con)
    return con


def migrate(con):
    """OpenBot used to run inside claude/opencode: its sessions move to source 'ob'. Idempotent."""
    if con.execute("SELECT 1 FROM meta WHERE k='mig_openbot'").fetchone(): return
    with con:
        ob = "SELECT src, sid FROM sessions WHERE src IN ('oc','cc') AND (project LIKE 'openbot%')"
        con.execute(f"UPDATE OR IGNORE usage SET src='ob' WHERE (src, sid) IN ({ob})")
        con.execute(f"UPDATE OR IGNORE sessions SET src='ob' WHERE (src, sid) IN ({ob})")
        con.execute("UPDATE sessions SET project=substr(project, 11) WHERE project LIKE 'OpenBot · %'")
        con.execute("INSERT OR REPLACE INTO meta VALUES('mig_openbot', '1')")


def sync(rebuild=False):
    """Read the apps and dump them into the history. Each value keeps the maximum
    seen, so what an app deletes is not subtracted. Returns (sources, errors)."""
    live, errors = sources.Live(), []
    for src, fn in (() if config.OFFLINE else sources.LOADERS):
        try:
            fn(live)
        except Exception as e:  # a broken app must not take down the others
            errors.append(f"{NAME[src]}: {e}")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    con = hist_connect()
    with con:
        if rebuild:
            for src in live.found:
                con.execute("DELETE FROM usage WHERE src=?", (src,))
                con.execute("DELETE FROM sessions WHERE src=?", (src,))
        con.executemany(
            "INSERT INTO usage VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(src,sid,day,model,provider) DO UPDATE SET "
            "inp=max(inp,excluded.inp), out=max(out,excluded.out), cr=max(cr,excluded.cr), "
            "cw=max(cw,excluded.cw), reas=max(reas,excluded.reas)",
            [(*k, *v) for k, v in live.usage.items()])
        con.executemany(
            "INSERT INTO sessions VALUES(?,?,?,?,?,?) ON CONFLICT(src,sid) DO UPDATE SET "
            "title=CASE WHEN excluded.title<>'' THEN excluded.title ELSE title END, "
            "project=CASE WHEN excluded.project<>'' THEN excluded.project ELSE project END, "
            "first=min(COALESCE(first,excluded.first), COALESCE(excluded.first,first)), "
            "last=max(COALESCE(last,''), COALESCE(excluded.last,''))",
            [(s, i, m["title"], m["project"], m["first"], m["last"]) for (s, i), m in live.sess.items()])
        con.execute("INSERT OR REPLACE INTO meta VALUES('last_sync', ?)", (now,))
        for src in live.found:
            con.execute("INSERT OR REPLACE INTO meta VALUES(?, ?)", ("seen_" + src, now))
    con.close()
    return live.found, errors


# usage row: (src, sid, day, model, provider, inp, out, cr, cw, reas)
def load_history():
    con = hist_connect()
    rows = con.execute("SELECT src, sid, day, model, provider, inp, out, cr, cw, reas FROM usage").fetchall()
    sess = {(s, i): (t or "", p or "", f or "", la or "") for s, i, t, p, f, la in con.execute("SELECT * FROM sessions")}
    meta = dict(con.execute("SELECT k, v FROM meta"))
    con.close()
    return rows, sess, meta


