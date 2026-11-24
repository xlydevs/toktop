"""Readers for each app's local usage data."""
import json
import os
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import config
from .common import ALL, NAME, SRC_OF, set_colors, set_enabled

# ───────────────────────── paths ─────────────────────────

HOME = config.HOME
OC_DB = ZC_DB = CC_DIR = DH_LOG = DSH_SESS = OB_DB = None
PATHS = {}  # source -> the file or folder toktop reads (None if the app is not there)


def first_existing(cands):
    for p in cands:
        if p and Path(p).exists(): return Path(p)
    return None


def editor_dirs():
    """User folders of VS Code and its forks, where Cline, Roo Code and Kilo Code keep their tasks."""
    if config.WIN:
        base = [Path(os.environ["APPDATA"])] if os.environ.get("APPDATA") else []
    elif sys.platform == "darwin":
        base = [HOME / "Library/Application Support"]
    else:
        base = [Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config")]
    apps = ("Code", "Code - Insiders", "Cursor", "Windsurf", "VSCodium", "Trae", "Kiro", "Positron")
    return [b / a / "User/globalStorage" for b in base for a in apps] + [HOME / ".vscode-server/data/User/globalStorage"]


def data_home():
    return Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local/share")


def configure():
    """Find each app's data: [paths] in the config file first, then the usual places per OS.
    Also applies [sources] enabled/disabled and [colors]."""
    global OC_DB, ZC_DB, CC_DIR, DH_LOG, DSH_SESS, OB_DB
    c, ed = config.cfg_path, config.env_dirs()
    mac = sys.platform == "darwin"
    OC_DB = first_existing([c("opencode"), HOME / ".local/share/opencode/opencode.db",
                            HOME / ".config/opencode/opencode.db", *[d / "opencode/opencode.db" for d in ed]])
    ZC_DB = first_existing([c("zcode"), HOME / ".zcode/cli/db/db.sqlite", *[d / "zcode/cli/db/db.sqlite" for d in ed]])
    CC_DIR = first_existing([c("claude"), Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" if os.environ.get("CLAUDE_CONFIG_DIR") else None,
                             HOME / ".claude/projects", HOME / ".config/claude/projects"])
    DH_LOG = first_existing([c("dsh_log"), config.DATA / "deepseek-harness.jsonl"])
    DSH_SESS = first_existing([c("dsh_sessions"), HOME / ".dsh/sessions"])
    OB_DB = first_existing([c("openbot"), HOME / "Library/Application Support/OpenBot/openbot.db",
                            *[d / "OpenBot/openbot.db" for d in ed]])
    env = lambda var, default: Path(os.environ[var]).expanduser() if os.environ.get(var) else default  # noqa: E731
    codex = env("CODEX_HOME", HOME / ".codex")
    gem_home = env("GEMINI_CLI_HOME", HOME)
    goose = [Path(os.environ["GOOSE_PATH_ROOT"]) / "data/sessions/sessions.db"] if os.environ.get("GOOSE_PATH_ROOT") else []
    zed = [HOME / "Library/Application Support/Zed/threads/threads.db"] if mac else \
          [d / "Zed/threads/threads.db" for d in ed] + [data_home() / "zed/threads/threads.db"]
    PATHS.clear()
    PATHS.update({
        "cc": CC_DIR, "oc": OC_DB, "zc": ZC_DB, "ob": OB_DB, "dh": DH_LOG,
        "cx": first_existing([c("codex"), codex / "sessions"]),
        "gm": first_existing([c("gemini"), gem_home / ".gemini/tmp"]),
        "qw": first_existing([c("qwen"), env("QWEN_HOME", HOME / ".qwen") / "projects"]),
        "gs": first_existing([c("goose"), *goose, data_home() / "goose/sessions/sessions.db",
                              *[d / "Block/goose/data/sessions/sessions.db" for d in ed]]),
        "am": first_existing([c("amp"), data_home() / "amp/threads", *[d / "amp/threads" for d in ed]]),
        "cl": [d / "saoudrizwan.claude-dev/tasks" for d in editor_dirs() if (d / "saoudrizwan.claude-dev/tasks").exists()] or None,
        "ro": [d / "rooveterinaryinc.roo-cline/tasks" for d in editor_dirs() if (d / "rooveterinaryinc.roo-cline/tasks").exists()] or None,
        "ki": [d / "kilocode.kilo-code/tasks" for d in editor_dirs() if (d / "kilocode.kilo-code/tasks").exists()] or None,
        "zd": first_existing([c("zed"), *zed]),
        "ad": first_existing([c("aider_log"), config.DATA / "aider-analytics.jsonl"]),
    })
    if config.cfg_path("cline"): PATHS["cl"] = [config.cfg_path("cline")]
    en = config.enabled_sources()
    keys = [SRC_OF[n] for n in en if n in SRC_OF] if en is not None else list(ALL)
    off = config.disabled_sources()
    set_enabled([k for k in keys if NAME[k] not in off])
    set_colors(config.CONFIG.get("colors"))


def detected():
    """Sources whose app data is on this machine."""
    return {k for k, p in PATHS.items() if p}


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





# ───────────────────────── more apps ─────────────────────────
# Formats checked against each tool's source and the parsers in ccusage / tokscale.

def num(x):
    try:
        return max(int(x or 0), 0)
    except (TypeError, ValueError):
        return 0


def when(v):
    """Local datetime from epoch seconds/ms or an ISO string (naive strings are UTC)."""
    if v is None or v == "": return None
    try:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v).astimezone()
        v = str(v).strip().replace(" ", "T", 1)
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone()
    except (ValueError, OSError, OverflowError):
        return None


def provider_of(model):
    m = (model or "").lower().split("/")[-1]
    for pre, prov in (("claude", "anthropic"), ("gpt", "openai"), ("o1", "openai"), ("o3", "openai"), ("o4", "openai"),
                      ("codex", "openai"), ("gemini", "google"), ("deepseek", "deepseek"), ("qwen", "qwen"),
                      ("glm", "zai"), ("kimi", "moonshot"), ("grok", "xai"), ("mistral", "mistral")):
        if m.startswith(pre): return prov
    return (model or "").split("/")[0] if "/" in (model or "") else ""


def jsonl(path):
    try:
        fh = open(path, encoding="utf-8", errors="ignore")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line: continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if isinstance(d, dict): yield d


def read_json(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def put(live, src, sid, dt, model, prov, inp=0, out=0, cr=0, cw=0, reas=0, title="", project=""):
    if dt is None or not any((inp, out, cr, cw, reas)): return
    live.add(src, sid, dt.strftime("%Y-%m-%d"), model, prov, inp, out, cr, cw, reas)
    live.meta(src, sid, title, project, dt.strftime("%Y-%m-%d %H:%M"))


def load_cx(live):
    """Codex CLI: rollout JSONL. token_count events carry the per-request delta (last) and a running
    total; input includes cached and output includes reasoning. Forks replay their parent's events."""
    root = PATHS.get("cx")
    if not root: return
    files = {}
    for base in (root, root.parent / "archived_sessions"):
        if base.exists():
            for f in base.rglob("rollout-*.jsonl"): files.setdefault(f.name, f)
    names = {d.get("id"): d.get("thread_name") for d in jsonl(root.parent / "session_index.jsonl")}
    seen = set()
    for f in sorted(files.values(), key=lambda f: f.name):  # oldest first, so a fork's replay is the one skipped
        sid, cwd, prov, model, title, prev = f.stem[-36:], "", "openai", "?", "", None
        for d in jsonl(f):
            t, p = d.get("type"), d.get("payload") or {}
            if t == "session_meta":
                sid, cwd, prov = p.get("id") or sid, p.get("cwd") or cwd, p.get("model_provider") or prov
            elif t == "turn_context":
                model, cwd = p.get("model") or model, p.get("cwd") or cwd
            elif t == "event_msg" and p.get("type") == "user_message" and not title:
                title = str(p.get("message") or "").strip().splitlines()[0][:80] if p.get("message") else ""
            elif t == "event_msg" and p.get("type") == "token_count":
                info = p.get("info") or {}
                tot, last = info.get("total_token_usage"), info.get("last_token_usage")
                if not isinstance(tot, dict): continue
                model = info.get("model") or model
                cached_of = lambda u: num(u.get("cached_input_tokens") or u.get("cache_read_input_tokens"))  # noqa: E731
                key = (model, num(tot.get("input_tokens")), cached_of(tot), num(tot.get("output_tokens")), num(tot.get("reasoning_output_tokens")))
                if key == prev or key in seen: continue
                if isinstance(last, dict):
                    u = last
                elif prev:
                    u = {"input_tokens": key[1] - prev[1], "cached_input_tokens": key[2] - prev[2],
                         "output_tokens": key[3] - prev[3], "reasoning_output_tokens": key[4] - prev[4]}
                else:
                    u = tot
                seen.add(key); prev = key
                inp, cached, out, reas = num(u.get("input_tokens")), cached_of(u), num(u.get("output_tokens")), num(u.get("reasoning_output_tokens"))
                put(live, "cx", sid, when(d.get("timestamp")), model, prov, max(inp - cached, 0), max(out - reas, 0), cached,
                    num(u.get("cache_write_input_tokens")), reas, names.get(sid) or title, project_name(cwd))
    live.found.add("cx")


def load_gm(live):
    """Gemini CLI: ~/.gemini/tmp/<project>/chats/session-*.jsonl (older: one .json). Tokens on
    'gemini' messages; input includes cached; thoughts are separate; a message id can repeat (last wins)."""
    root = PATHS.get("gm")
    if not root: return
    for f in root.glob("*/chats/**/session-*.json*"):
        meta, msgs = {}, {}
        if f.suffix == ".json":
            d = read_json(f)
            if not isinstance(d, dict): continue
            meta = d
            for m in d.get("messages") or []: msgs[m.get("id") or len(msgs)] = m
        else:
            for d in jsonl(f):
                if "$set" in d and isinstance(d["$set"], dict): meta.update(d["$set"])
                elif "type" not in d and "sessionId" in d: meta.update(d)
                elif "type" in d: msgs[d.get("id") or len(msgs)] = d
        sid = meta.get("sessionId") or f.stem
        proj = f.relative_to(root).parts[0]
        proj = "" if len(proj) == 64 else proj  # old versions: a sha256 of the folder
        title = meta.get("summary") or ""
        for m in msgs.values():
            if not title and m.get("type") == "user" and isinstance(m.get("content"), str):
                title = m["content"].strip()[:80]
            tk = m.get("tokens")
            if m.get("type") != "gemini" or not isinstance(tk, dict): continue
            inp, out, cached, th, tool, total = (num(tk.get(k)) for k in ("input", "output", "cached", "thoughts", "tool", "total"))
            if not (total and total == inp + out + th + tool + cached): inp = max(inp - cached, 0)
            put(live, "gm", sid, when(m.get("timestamp")), m.get("model"), "google", inp + tool, out, cached, 0, th, title, proj)
    live.found.add("gm")


def load_qw(live):
    """Qwen Code: ~/.qwen/projects/<cwd>/chats/*.jsonl. usageMetadata on assistant records; prompt includes cached;
    thoughts can be inside candidates (then total == prompt + candidates)."""
    root = PATHS.get("qw")
    if not root: return
    seen = set()
    for f in root.glob("*/chats/**/*.jsonl"):
        title, rows = "", []
        for d in jsonl(f):
            t = d.get("type")
            if t == "system" and d.get("subtype") == "custom_title":
                title = str((d.get("systemPayload") or {}).get("title") or title)
            elif t == "assistant" and isinstance(d.get("usageMetadata"), dict):
                uid = d.get("uuid")
                if uid and uid in seen: continue
                seen.add(uid)
                rows.append(d)
        for d in rows:
            u = d["usageMetadata"]
            prompt, cand, th, cached, total = (num(u.get(k)) for k in ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount",
                                                                         "cachedContentTokenCount", "totalTokenCount"))
            out = max(cand - th, 0) if th and (not total or total == prompt + cand) else cand
            put(live, "qw", d.get("sessionId") or f.stem, when(d.get("timestamp")), d.get("model"), "qwen",
                max(prompt - cached, 0), out, cached, 0, th, title, project_name(d.get("cwd")))
    live.found.add("qw")


def load_gs(live):
    """Goose: sessions.db. usage_ledger has one row per request (newer versions); otherwise the
    session's accumulated totals. Input includes the cache."""
    db = PATHS.get("gs")
    if not db: return
    con = open_ro(db)
    sess = {}
    for sid, name, wd, created, prov, mcfg, ai, ao, acr, acw in con.execute(
            "SELECT id, name, working_dir, created_at, provider_name, model_config_json, accumulated_input_tokens, "
            "accumulated_output_tokens, accumulated_cache_read_tokens, accumulated_cache_write_tokens FROM sessions"):
        try:
            model = json.loads(mcfg or "{}").get("model_name")
        except ValueError:
            model = None
        sess[sid] = (name or "", project_name(wd), when(created), prov or "", model, ai, ao, acr, acw)
    ledger = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='usage_ledger'").fetchone()
    in_ledger = set()
    if ledger:
        for sid, ts, model, i, o, cr, cw in con.execute(
                "SELECT session_id, created_timestamp, model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens FROM usage_ledger"):
            name, proj, _, prov, smodel, *_ = sess.get(sid, ("", "", None, "", None, 0, 0, 0, 0))
            cr, cw = num(cr), num(cw)
            put(live, "gs", sid, when(ts), model or smodel, prov, max(num(i) - cr - cw, 0), num(o), cr, cw, 0, name, proj)
            in_ledger.add(sid)
    for sid, (name, proj, dt, prov, model, ai, ao, acr, acw) in sess.items():
        if sid in in_ledger: continue
        put(live, "gs", sid, dt, model, prov, max(num(ai) - num(acr) - num(acw), 0), num(ao), num(acr), num(acw), 0, name, proj)
    con.close()
    live.found.add("gs")


def load_am(live):
    """Amp: one JSON per thread. Usage per assistant message (input excludes cache); old threads: usageLedger."""
    root = PATHS.get("am")
    if not root: return
    for f in root.glob("T-*.json"):
        d = read_json(f)
        if not isinstance(d, dict): continue
        sid, title, created = d.get("id") or f.stem, d.get("title") or "", d.get("created")
        got = False
        for m in d.get("messages") or []:
            u = m.get("usage") if isinstance(m, dict) else None
            if m.get("role") != "assistant" or not isinstance(u, dict): continue
            got = True
            put(live, "am", sid, when(u.get("timestamp")) or when(created), u.get("model"), provider_of(u.get("model")),
                num(u.get("inputTokens")), num(u.get("outputTokens")), num(u.get("cacheReadInputTokens")),
                num(u.get("cacheCreationInputTokens")), 0, title)
        if not got:
            for e in (d.get("usageLedger") or {}).get("events") or []:
                tk = e.get("tokens") or {}
                put(live, "am", sid, when(e.get("timestamp")) or when(created), e.get("model"), provider_of(e.get("model")),
                    num(tk.get("input")), num(tk.get("output")), num(tk.get("cacheReadInputTokens")),
                    num(tk.get("cacheCreationInputTokens")), 0, title)
    live.found.add("am")


ROO_GROSS_FROM = 1762041600000  # Roo/Kilo count cache inside tokensIn from v3.29.5 on (always for the OpenAI protocol)
MODEL_TAG = re.compile(r"<model>([^<]{1,200})</model>")


def load_tasks(live, src):
    """Cline, Roo Code and Kilo Code (VS Code and forks): tasks/<id>/ui_messages.json, one
    'api_req_started' row per request with a JSON text {tokensIn, tokensOut, cacheReads, cacheWrites}."""
    roo = src in ("ro", "ki")
    if not PATHS.get(src): return
    for tasks in PATHS[src]:
        hist = {}
        h = read_json(tasks.parent / "state/taskHistory.json")
        for it in h if isinstance(h, list) else []:
            if isinstance(it, dict): hist[str(it.get("id"))] = (it.get("task") or "", it.get("cwdOnTaskInitialization") or "")
        for td in tasks.iterdir():
            msgs = read_json(td / "ui_messages.json")
            if not isinstance(msgs, list): continue
            title, cwd = hist.get(td.name, ("", ""))
            hi = read_json(td / "history_item.json")
            if isinstance(hi, dict): title, cwd = hi.get("task") or title, hi.get("workspace") or cwd
            fmodel = None
            try:
                tags = MODEL_TAG.findall((td / "api_conversation_history.json").read_text(encoding="utf-8", errors="ignore"))
                fmodel = tags[-1].strip() if tags else None
            except OSError:
                pass
            reqs = {}
            for m in msgs:
                if not isinstance(m, dict): continue
                if not title and m.get("say") == "task": title = str(m.get("text") or "")
                if m.get("say") != "api_req_started" or m.get("partial"): continue
                try:
                    j = json.loads(m.get("text") or "")
                except (TypeError, ValueError):
                    continue
                if not isinstance(j, dict) or "tokensIn" not in j or "tokensOut" not in j: continue
                reqs[m.get("ts")] = (m, j)
            for ts, (m, j) in reqs.items():
                ti, to, cr, cw = num(j.get("tokensIn")), num(j.get("tokensOut")), num(j.get("cacheReads")), num(j.get("cacheWrites"))
                t_ms = ts if isinstance(ts, (int, float)) else 0
                if roo and (t_ms >= ROO_GROSS_FROM or j.get("apiProtocol") == "openai"): ti = max(ti - cr - cw, 0)
                mi = m.get("modelInfo") or {}
                model = mi.get("modelId") or fmodel
                if model == "unknown": continue
                put(live, src, td.name, when(ts), model, mi.get("providerId") or provider_of(model), ti, to, cr, cw, 0,
                    title.strip().splitlines()[0][:80] if title.strip() else "", project_name(cwd))
    live.found.add(src)


def zstd_decompress(data):
    try:
        from compression import zstd  # Python 3.14+
        return zstd.decompress(data)
    except ImportError:
        pass
    try:
        import zstandard
        return zstandard.ZstdDecompressor().decompress(data, max_output_size=64 << 20)
    except ImportError:
        return None


def load_zd(live):
    """Zed: threads.db, one row per thread with its JSON (zstd-compressed in current versions).
    Token usage per request (request_token_usage) or a running total; input excludes the cache."""
    db = PATHS.get("zd")
    if not db: return
    con = open_ro(db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(threads)")}
    created = "created_at" if "created_at" in cols else "updated_at"
    folders = "folder_paths" if "folder_paths" in cols else "''"
    for tid, summary, ts, dtype, data, fp in con.execute(f"SELECT id, summary, {created}, data_type, data, {folders} FROM threads"):
        raw = zstd_decompress(data) if dtype == "zstd" else data
        if raw is None: continue
        try:
            j = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(j, dict) or j.get("imported"): continue
        m = j.get("model") or {}
        prov = m.get("provider") or ""
        tot = [0, 0, 0, 0]
        for u in (j.get("request_token_usage") or {}).values():
            for i, k in enumerate(("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")):
                tot[i] += num((u or {}).get(k))
        cum = j.get("cumulative_token_usage") or {}
        if not any(tot) or prov == "openai-subscribed":
            tot = [num(cum.get(k)) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")]
        proj = project_name((fp or "").split("\n")[0])
        put(live, "zd", tid, when(ts), m.get("model"), prov, *tot, 0, summary or j.get("title") or "", proj)
    con.close()
    live.found.add("zd")


def load_ad(live):
    """Aider: its --analytics-log JSONL. message_send events carry prompt/completion tokens (no cache split).
    There is no session id: a new one starts with each launch."""
    log = PATHS.get("ad")
    if not log: return
    sid = None
    for d in jsonl(log):
        ev, t = d.get("event"), d.get("time")
        if ev in ("launched", "cli session") or sid is None:
            dt0 = when(t)
            sid = "aider-" + (dt0.strftime("%Y%m%d-%H%M%S") if dt0 else "?")
        if ev != "message_send": continue
        p = d.get("properties") or {}
        model = p.get("main_model") or "?"
        put(live, "ad", sid, when(t), model, provider_of(model), num(p.get("prompt_tokens")), num(p.get("completion_tokens")))
    live.found.add("ad")


LOADERS = (("oc", load_oc), ("zc", load_zc), ("cc", load_cc), ("dh", load_dh), ("cx", load_cx), ("gm", load_gm),
           ("qw", load_qw), ("gs", load_gs), ("am", load_am), ("cl", lambda lv: load_tasks(lv, "cl")),
           ("ro", lambda lv: load_tasks(lv, "ro")), ("ki", lambda lv: load_tasks(lv, "ki")), ("zd", load_zd), ("ad", load_ad))
