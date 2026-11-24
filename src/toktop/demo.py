"""Made-up usage data for `toktop --demo` and for the screenshots."""
import random
from datetime import date, timedelta

from .history import hist_connect

PROJECTS = ["webshop", "api-gateway", "dotfiles", "ml-notebooks", "blog", "cli-tools", "mobile-app", "infra"]
TITLES = ["Fix flaky login test", "Add dark mode", "Refactor payment service", "Write migration for orders",
          "Speed up CI cache", "Explain this regex", "Port script to Rust", "Review PR feedback",
          "Set up Docker compose", "Draft release notes", "Debug memory leak", "Add rate limiting",
          "Translate README", "Clean up warnings", "Prototype search UI", "Bump dependencies"]
# source -> [(model, provider, weight)]
MODELS = {
    "cc": [("claude-opus-5-5", "anthropic", 3), ("claude-sonnet-5-5", "anthropic", 5), ("claude-haiku-5-5", "anthropic", 2)],
    "oc": [("deepseek-v4.1-flash", "opencode-go", 5), ("glm-5.3-flash", "zai", 2), ("kimi-k3", "moonshot", 2),
           ("gpt-6-luna", "openai", 1)],
    "zc": [("glm-5.3-flash", "zai", 1)],
    "dh": [("deepseek-v4.1-flash", "deepseek", 1)],
    "ob": [("claude-haiku-5-5", "anthropic", 2), ("deepseek-v4.1-flash", "deepseek", 3)],
}
SHARE = {"cc": 0.38, "oc": 0.27, "zc": 0.08, "dh": 0.12, "ob": 0.15}


def populate(days=300, seed=7):
    rnd = random.Random(seed)
    today = date.today()
    usage, sess = {}, {}
    n = 0
    for back in range(days - 1, -1, -1):
        d = today - timedelta(days=back)
        ramp = 0.35 + 0.65 * (1 - back / days)  # usage grows over time
        if rnd.random() < (0.45 if d.weekday() >= 5 else 0.12):
            continue
        for src, share in SHARE.items():
            if rnd.random() > 0.55 + share: continue
            for _ in range(rnd.randint(1, 3)):
                n += 1
                sid = f"demo-{src}-{n:05d}"
                model, prov, _ = rnd.choices(MODELS[src], weights=[w for *_, w in MODELS[src]])[0]
                scale = ramp * rnd.lognormvariate(16.2, 0.9) * share
                cr = int(scale)
                inp = int(scale * rnd.uniform(0.02, 0.06))
                out = int(scale * rnd.uniform(0.004, 0.012))
                cw = int(scale * rnd.uniform(0.0, 0.03)) if src in ("cc", "ob") else 0
                reas = int(out * rnd.uniform(0.1, 0.4)) if src in ("oc", "zc") else 0
                usage[(src, sid, d.isoformat(), model, prov)] = (inp, out, cr, cw, reas)
                hh = rnd.randint(8, 22)
                ts = f"{d.isoformat()} {hh:02d}:{rnd.randint(0, 59):02d}"
                title = "" if src in ("dh", "zc") else rnd.choice(TITLES)
                proj = rnd.choice(PROJECTS) if src != "ob" else rnd.choice(["Researcher", "Editor", "Scout"])
                sess[(src, sid)] = (title, proj, ts, ts)
    con = hist_connect()
    with con:
        con.executemany("INSERT OR REPLACE INTO usage VALUES(?,?,?,?,?,?,?,?,?,?)", [(*k, *v) for k, v in usage.items()])
        con.executemany("INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?)", [(*k, *v) for k, v in sess.items()])
        con.execute("INSERT OR REPLACE INTO meta VALUES('last_sync', ?)", (f"{today.isoformat()} 12:00",))
        for s in SHARE:
            con.execute("INSERT OR REPLACE INTO meta VALUES(?, ?)", ("seen_" + s, f"{today.isoformat()} 12:00"))
    con.close()
