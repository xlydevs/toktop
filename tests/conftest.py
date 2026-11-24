import json
import sqlite3
import time

import pytest

from toktop import config, i18n, prices, sources


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Every test gets its own data dir, no config file, no network and English."""
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    monkeypatch.setattr(config, "CONFIG", {})
    monkeypatch.setattr(sources, "HOME", tmp_path / "home")  # never touch the real apps
    monkeypatch.setattr(config, "env_dirs", lambda: [])
    for var in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "APPDATA", "LOCALAPPDATA", "CODEX_HOME", "CLAUDE_CONFIG_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("TOKTOP_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setattr(config, "OFFLINE", False)
    monkeypatch.setattr(prices, "_PRICES", None)
    i18n.set_lang("en")
    sources.configure()
    yield tmp_path


def use_paths(**paths):
    config.CONFIG = {"paths": {k: str(v) for k, v in paths.items()}}
    sources.configure()


def make_opencode(path, rows):
    """rows: (id, title, directory, model, provider, inp, out, cr, cw, reas, ms_timestamp)"""
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE session_v2(id TEXT, title TEXT, directory TEXT, model TEXT, tokens_input INT, "
                "tokens_output INT, tokens_cache_read INT, tokens_cache_write INT, tokens_reasoning INT, time_created INT)")
    con.executemany("INSERT INTO session_v2 VALUES(?,?,?,?,?,?,?,?,?,?)",
                    [(i, ti, d, json.dumps({"id": m, "providerID": p}), *v, ts) for i, ti, d, m, p, *v, ts in rows])
    con.commit()
    con.close()


def make_zcode(path, rows):
    """rows: (session, ms_timestamp, model, provider, input_incl_cache, out, cache_read, cache_write, reas)"""
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE model_usage(session_id TEXT, started_at INT, model_id TEXT, provider_id TEXT, "
                "input_tokens INT, output_tokens INT, cache_read_input_tokens INT, cache_creation_input_tokens INT, "
                "reasoning_tokens INT)")
    con.executemany("INSERT INTO model_usage VALUES(?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()


def claude_line(msg_id, session, ts, cwd, model="claude-sonnet-5-5", inp=10, out=5, cr=100, cw=0):
    return json.dumps({"type": "assistant", "sessionId": session, "timestamp": ts, "cwd": cwd,
                       "message": {"id": msg_id, "model": model, "usage": {
                           "input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cr,
                           "cache_creation_input_tokens": cw}}})


def ms(day, hour=12):
    return int(time.mktime(time.strptime(f"{day} {hour}", "%Y-%m-%d %H")) * 1000)
