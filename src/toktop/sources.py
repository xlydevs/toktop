"""Readers for each app's local usage data."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from . import config

# ───────────────────────── paths ─────────────────────────

HOME = config.HOME
OC_DB = ZC_DB = CC_DIR = DH_LOG = DSH_SESS = OB_DB = None


def first_existing(cands):
    for p in cands:
        if p and Path(p).exists(): return Path(p)
    return None


def configure():
    """Find each app's data: [paths] in the config file first, then the usual places per OS."""
    global OC_DB, ZC_DB, CC_DIR, DH_LOG, DSH_SESS, OB_DB
    c, ed = config.cfg_path, config.env_dirs()
    OC_DB = first_existing([c("opencode"), HOME / ".local/share/opencode/opencode.db",
                            HOME / ".config/opencode/opencode.db", *[d / "opencode/opencode.db" for d in ed]])
    ZC_DB = first_existing([c("zcode"), HOME / ".zcode/cli/db/db.sqlite", *[d / "zcode/cli/db/db.sqlite" for d in ed]])
    CC_DIR = first_existing([c("claude"), HOME / ".claude/projects"])
    DH_LOG = first_existing([c("dsh_log"), config.DATA / "deepseek-harness.jsonl"])
    DSH_SESS = first_existing([c("dsh_sessions"), HOME / ".dsh/sessions"])
    OB_DB = first_existing([c("openbot"), HOME / "Library/Application Support/OpenBot/openbot.db",
                            *[d / "OpenBot/openbot.db" for d in ed]])
    off = config.disabled_sources()
    if "opencode" in off: OC_DB = None
    if "zcode" in off: ZC_DB = None
    if "claude" in off: CC_DIR = None
    if "dsh" in off: DH_LOG = None
    if "openbot" in off: OB_DB = None


configure()


def open_ro(path):
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.execute("SELECT 1")
        return con
    except sqlite3.Error:
        return sqlite3.connect(path)


_AGENTS = None


def openbot_agents():
    """agent_id -> visible name of the OpenBot agents."""
    global _AGENTS
    if _AGENTS is None:
        _AGENTS = {}
        if OB_DB:
            try:
                con = open_ro(OB_DB)
                for aid, name in con.execute("SELECT agent_id, json_extract(agent_json,'$.name') FROM projection_agents"):
                    if name: _AGENTS[aid] = name
                con.close()
            except sqlite3.Error:
                pass
    return _AGENTS


def project_name(path):
    if not path: return ""
    p = str(path).replace("\\", "/").rstrip("/")
    name = p.split("/")[-1]
    if "/OpenBot/Agents/" in p:
        return openbot_agents().get(name, name.replace("agent-", "")[:8])
    if p == str(HOME).replace("\\", "/"): return "~"
    return name


def is_openbot(path):
    """Sessions launched by OpenBot (through Claude Code or opencode) count as their own source."""
    if not path: return False
    p = str(path).replace("\\", "/").rstrip("/")
    return "/OpenBot/" in p or p.split("/")[-1].lower().startswith("openbot")


# ───────────────────────── reading the apps ─────────────────────────

class Live:
    """Usage read from the apps: (src, session, day, model, provider) -> [inp, out, cr, cw, reas]."""

    def __init__(self):
        self.usage, self.sess, self.found = {}, {}, set()

    def add(self, src, sid, day, model, prov, inp=0, out=0, cr=0, cw=0, reas=0):
        k = (src, sid or "?", day, model or "?", prov or "")
        v = self.usage.setdefault(k, [0, 0, 0, 0, 0])
        v[0] += inp or 0; v[1] += out or 0; v[2] += cr or 0; v[3] += cw or 0; v[4] += reas or 0

    def meta(self, src, sid, title="", project="", ts=None):
        m = self.sess.setdefault((src, sid or "?"), {"title": "", "project": "", "first": None, "last": None})
        if title: m["title"] = title
        if project and not m["project"]: m["project"] = project
        if ts:
            m["first"] = min(m["first"] or ts, ts)
            m["last"] = max(m["last"] or ts, ts)


def iso_local(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()


def load_oc(live):
    """opencode: one row per session (session_v2 in 2.x, which already includes the session table)."""
    if not OC_DB: return
    con = open_ro(OC_DB)
    tbl = "session_v2" if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_v2'").fetchone() else "session"
    cols = {r[1] for r in con.execute(f"PRAGMA table_info({tbl})")}
    title = "title" if "title" in cols else "''"
    dirc = "directory" if "directory" in cols else "''"
    q = (f"SELECT id, {title}, {dirc}, json_extract(model,'$.id'), json_extract(model,'$.providerID'), tokens_input, "
         f"tokens_output, tokens_cache_read, tokens_cache_write, tokens_reasoning, time_created FROM {tbl}")
    for sid, ttl, d, mid, prov, ti, to, tcr, tcw, tr, tc in con.execute(q):
        if not tc or not any((ti, to, tcr, tcw, tr)): continue
        dt = datetime.fromtimestamp(tc / 1000)
        src = "ob" if is_openbot(d) else "oc"
        live.add(src, sid, dt.strftime("%Y-%m-%d"), mid, prov, ti, to, tcr, tcw, tr)
        live.meta(src, sid, ttl or "", project_name(d), dt.strftime("%Y-%m-%d %H:%M"))
        live.found.add(src)
    con.close()
    live.found.add("oc")


def load_zc(live):
    """zcode: model_usage (its input_tokens already include cache_read, which is subtracted)."""
    if not ZC_DB: return
    con = open_ro(ZC_DB)
    q = ("SELECT session_id, date(started_at/1000,'unixepoch','localtime'), model_id, REPLACE(provider_id,'builtin:',''), "
         "SUM(input_tokens-COALESCE(cache_read_input_tokens,0)), SUM(output_tokens), SUM(COALESCE(cache_read_input_tokens,0)), "
         "SUM(COALESCE(cache_creation_input_tokens,0)), SUM(COALESCE(reasoning_tokens,0)), MIN(started_at), MAX(started_at) "
         "FROM model_usage GROUP BY 1,2,3,4")
    for sid, day, mid, prov, i, o, r, w, rs, t0, t1 in con.execute(q):
        live.add("zc", sid, day, mid, prov, i, o, r, w, rs)
        for t in (t0, t1):
            if t: live.meta("zc", sid, ts=datetime.fromtimestamp(t / 1000).strftime("%Y-%m-%d %H:%M"))
    con.close()
    live.found.add("zc")


def load_cc(live):
    """Claude Code: JSONL under ~/.claude/projects. Each message counts once
    (its id repeats over several lines, one per streaming block)."""
    if not CC_DIR or not CC_DIR.exists(): return
    msgs, titles = {}, {}
    for f in CC_DIR.rglob("*.jsonl"):
        try:
            fh = open(f, encoding="utf-8", errors="ignore")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"custom-title"' in line:
                    try:
                        d = json.loads(line)
                        if d.get("type") == "custom-title" and d.get("customTitle"):
                            titles[d.get("sessionId")] = d["customTitle"]
                    except ValueError:
                        pass
                    continue
                if '"usage"' not in line: continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                m = d.get("message") or {}
                u = m.get("usage")
                if d.get("type") != "assistant" or not isinstance(u, dict): continue
                mid, ts = m.get("id") or d.get("requestId"), d.get("timestamp")
                if not mid or not ts: continue
                vals = (u.get("input_tokens") or 0, u.get("output_tokens") or 0,
                        u.get("cache_read_input_tokens") or 0, u.get("cache_creation_input_tokens") or 0)
                if not any(vals): continue
                msgs[mid] = (ts, d.get("sessionId") or "?", m.get("model") or "?", d.get("cwd") or "", vals)
    ob_sess = {sid for _, sid, _, cwd, _ in msgs.values() if is_openbot(cwd)}
    for ts, sid, model, cwd, (i, o, r, w) in msgs.values():
        try:
            dt = iso_local(ts)
        except ValueError:
            continue
        src = "ob" if sid in ob_sess else "cc"
        live.add(src, sid, dt.strftime("%Y-%m-%d"), model, "anthropic", i, o, r, w, 0)  # thinking is included in output
        live.meta(src, sid, titles.get(sid, ""), project_name(cwd), dt.strftime("%Y-%m-%d %H:%M"))
        live.found.add(src)
    live.found.add("cc")


def dsh_projects():
    """dsh session id -> project, read from the cwd in each session header."""
    out = {}
    if not DSH_SESS or not DSH_SESS.exists(): return out
    try:
        from compression import zstd
    except ImportError:
        zstd = None
    for d in DSH_SESS.glob("*/*"):
        if not d.is_dir(): continue
        cwd = None
        f = d / "session.v4.jsonl.zstd"
        if zstd and f.exists():
            try:
                with zstd.open(f, "rt", encoding="utf-8") as fh:
                    cwd = json.loads(fh.readline()).get("cwd")
            except Exception:
                cwd = None
        out[d.name] = project_name(cwd) if cwd else d.parent.name.strip("-").split("-")[-1]
    return out


def load_dh(live):
    """dsh: its local plugin writes one JSON line per request (the last one for each id wins)."""
    if not DH_LOG: return
    recs = {}
    with open(DH_LOG, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("id"): recs[d["id"]] = d
    projects = dsh_projects()
    for d in recs.values():
        try:
            dt = iso_local(d.get("ts") or "")
        except ValueError:
            continue
        sid = d.get("session_id") or "?"
        # dsh adds reasoning into output; it is only split out if the record says so
        rs = 0 if d.get("reasoning_in_output", True) else (d.get("reasoning") or 0)
        live.add("dh", sid, dt.strftime("%Y-%m-%d"), d.get("model"), d.get("provider"),
                 d.get("input_uncached"), d.get("output"), d.get("input_cached"), d.get("cache_write"), rs)
        live.meta("dh", sid, "", projects.get(sid, ""), dt.strftime("%Y-%m-%d %H:%M"))
    live.found.add("dh")


LOADERS = (("oc", load_oc), ("zc", load_zc), ("cc", load_cc), ("dh", load_dh))

