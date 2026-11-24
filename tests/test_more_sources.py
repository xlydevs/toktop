"""Readers for the apps added after the first release, fed with records shaped like the real ones."""
import json
import sqlite3

from conftest import use_paths

from toktop import config, sources


def rows(src):
    live = sources.Live()
    dict(sources.LOADERS)[src](live)
    return live


def wjsonl(path, recs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n")


def test_codex_uses_deltas_and_skips_replays(isolated):
    root = isolated / "codex/sessions"
    tc = lambda tot, last: {"timestamp": "2026-09-01T10:01:59Z", "type": "event_msg", "payload": {"type": "token_count", "info": {  # noqa: E731
        "total_token_usage": tot, "last_token_usage": last}}}
    u = lambda i, c, o, r: {"input_tokens": i, "cached_input_tokens": c, "output_tokens": o, "reasoning_output_tokens": r}  # noqa: E731
    recs = [{"timestamp": "2026-09-01T10:00:00Z", "type": "session_meta", "payload": {"id": "s1", "cwd": "/w/repo", "model_provider": "openai"}},
            {"timestamp": "2026-09-01T10:00:01Z", "type": "turn_context", "payload": {"model": "gpt-6-codex"}},
            {"timestamp": "2026-09-01T10:00:02Z", "type": "event_msg", "payload": {"type": "user_message", "message": "Fix the tests"}},
            tc(u(1000, 800, 100, 40), u(1000, 800, 100, 40)),
            tc(u(1000, 800, 100, 40), u(1000, 800, 100, 40)),  # repeated snapshot
            tc(u(3000, 2500, 300, 60), u(2000, 1700, 200, 20))]
    wjsonl(root / "2026/09/01/rollout-2026-09-01T10-00-00-s1.jsonl", recs)
    # a fork replays the same history
    wjsonl(root / "2026/09/02/rollout-2026-09-02T10-00-00-s2.jsonl",
           [{"timestamp": "2026-09-02T10:00:00Z", "type": "session_meta", "payload": {"id": "s2"}}, recs[1], recs[3], recs[5]])
    use_paths(codex=root)
    live = rows("cx")
    (k, v), = live.usage.items()
    assert k[0:2] == ("cx", "s1") and k[3] == "gpt-6-codex"
    assert v == [200 + 300, 60 + 180, 800 + 1700, 0, 60]  # input without cache, output without reasoning
    assert live.sess[("cx", "s1")]["title"] == "Fix the tests" and live.sess[("cx", "s1")]["project"] == "repo"


def test_gemini_jsonl_last_record_wins(isolated):
    root = isolated / "gemini/tmp"
    msg = {"id": "m1", "timestamp": "2026-09-03T12:01:00Z", "type": "gemini", "model": "gemini-3-pro"}
    wjsonl(root / "myproj/chats/session-2026-09-03T12-00-abcd.jsonl", [
        {"sessionId": "g1", "projectHash": "x", "startTime": "2026-09-03T12:00:00Z"},
        {"id": "u1", "timestamp": "2026-09-03T12:00:30Z", "type": "user", "content": "Hello there"},
        msg,
        {**msg, "tokens": {"input": 1000, "output": 50, "cached": 600, "thoughts": 30, "tool": 10, "total": 1090}}])
    use_paths(gemini=root)
    live = rows("gm")
    assert list(live.usage.values()) == [[400 + 10, 50, 600, 0, 30]]
    assert live.sess[("gm", "g1")]["title"] == "Hello there" and live.sess[("gm", "g1")]["project"] == "myproj"


def test_qwen_thoughts_inside_candidates(isolated):
    root = isolated / "qwen/projects"
    rec = {"uuid": "a", "type": "assistant", "model": "qwen3.5-plus", "timestamp": "2026-09-04T14:24:56Z", "sessionId": "q1", "cwd": "/w/app",
           "usageMetadata": {"promptTokenCount": 1200, "candidatesTokenCount": 76, "thoughtsTokenCount": 39, "cachedContentTokenCount": 200,
                             "totalTokenCount": 1276}}
    wjsonl(root / "-w-app/chats/q1.jsonl", [rec, rec])
    use_paths(qwen=root)
    assert list(rows("qw").usage.values()) == [[1000, 37, 200, 0, 39]]


def test_goose_ledger_and_fallback(isolated):
    db = isolated / "goose.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE sessions(id, name, working_dir, created_at, provider_name, model_config_json, accumulated_input_tokens, "
                "accumulated_output_tokens, accumulated_cache_read_tokens, accumulated_cache_write_tokens)")
    con.execute("CREATE TABLE usage_ledger(session_id, created_timestamp, model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)")
    cfg = json.dumps({"model_name": "claude-sonnet-5-5"})
    con.execute("INSERT INTO sessions VALUES('s1','Ledger','/w/a','2026-09-02 13:56:11','anthropic',?,0,0,0,0)", (cfg,))
    con.execute("INSERT INTO sessions VALUES('s2','Old','/w/b','2026-09-02 14:00:00','anthropic',?,900,90,400,0)", (cfg,))
    con.execute("INSERT INTO usage_ledger VALUES('s1',1788357383,'claude-sonnet-5-5',5000,100,4000,0)")
    con.commit(); con.close()
    use_paths(goose=db)
    u = rows("gs").usage
    assert sorted(v for v in u.values()) == [[500, 90, 400, 0, 0], [1000, 100, 4000, 0, 0]]


def test_amp_message_usage(isolated):
    root = isolated / "amp/threads"
    root.mkdir(parents=True)
    (root / "T-1.json").write_text(json.dumps({"v": 1, "id": "T-1", "created": 1775304000000, "title": "Amp thread", "messages": [
        {"role": "user", "messageId": 1, "usage": None},
        {"role": "assistant", "messageId": 2, "usage": {"model": "claude-sonnet-4-0", "timestamp": "2026-04-04T12:00:05Z", "inputTokens": 4,
                                                         "outputTokens": 194, "cacheReadInputTokens": 0, "cacheCreationInputTokens": 48122}}]}))
    use_paths(amp=root)
    (k, v), = rows("am").usage.items()
    assert k[4] == "anthropic" and v == [4, 194, 0, 48122, 0]


def ui_task(tasks, tid, reqs, history=None):
    td = tasks / tid
    td.mkdir(parents=True)
    (td / "ui_messages.json").write_text(json.dumps(
        [{"ts": 1, "type": "say", "say": "task", "text": "Build the thing"}] +
        [{"ts": ts, "type": "say", "say": "api_req_started", **extra, "text": json.dumps(j)} for ts, j, extra in reqs] +
        [{"ts": 9, "type": "say", "say": "api_req_started", "text": json.dumps({"request": "…"})}]))  # still in flight
    if history: (td / "api_conversation_history.json").write_text(history)


def test_cline_and_roo_tasks(isolated, monkeypatch):
    cl, ro = isolated / "Code/saoudrizwan.claude-dev/tasks", isolated / "Code/rooveterinaryinc.roo-cline/tasks"
    ui_task(cl, "t1", [(1790856000000, {"tokensIn": 100, "tokensOut": 20, "cacheReads": 5, "cacheWrites": 10},
                        {"modelInfo": {"modelId": "claude-sonnet-4", "providerId": "anthropic"}})])
    ui_task(ro, "t2", [(1789022955199, {"tokensIn": 40, "tokensOut": 15, "cacheReads": 7, "cacheWrites": 3, "apiProtocol": "openai"}, {})],
            history='[{"content": "<environment_details><model>kimi-k3</model></environment_details>"}]')
    monkeypatch.setattr(config, "CONFIG", {})
    sources.configure()
    sources.PATHS.update(cl=[cl], ro=[ro])
    (k, v), = rows("cl").usage.items()
    assert k[3] == "claude-sonnet-4" and v == [100, 20, 5, 10, 0]
    live = rows("ro")
    (k, v), = live.usage.items()
    assert k[3] == "kimi-k3" and v == [30, 15, 7, 3, 0]
    assert live.sess[("ro", "t2")]["title"] == "Build the thing"


def test_zed_threads_json(isolated):
    db = isolated / "threads.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE threads(id, summary, updated_at, data_type, data, created_at, folder_paths)")
    data = {"title": "Zed thread", "model": {"provider": "zed.dev", "model": "claude-sonnet-4-5"},
            "request_token_usage": {"m1": {"input_tokens": 120, "output_tokens": 40, "cache_read_input_tokens": 300},
                                    "m2": {"input_tokens": 10, "output_tokens": 5}},
            "cumulative_token_usage": {"input_tokens": 999, "output_tokens": 999}}
    con.execute("INSERT INTO threads VALUES('z1','Zed thread','2026-05-01T12:30:00Z','json',?,'2026-05-01T12:00:00Z','/w/site')",
                (json.dumps(data).encode(),))
    con.execute("INSERT INTO threads VALUES('z2','Shared','2026-05-01T12:30:00Z','json',?,'2026-05-01T12:00:00Z','')",
                (json.dumps({**data, "imported": True}).encode(),))
    con.commit(); con.close()
    use_paths(zed=db)
    live = rows("zd")
    (k, v), = live.usage.items()
    assert k[1] == "z1" and v == [130, 45, 300, 0, 0] and live.sess[("zd", "z1")]["project"] == "site"


def test_aider_analytics_log(isolated):
    log = isolated / "aider.jsonl"
    wjsonl(log, [{"event": "launched", "properties": {}, "time": 1790000000},
                 {"event": "message_send", "properties": {"main_model": "gpt-4o", "prompt_tokens": 2310, "completion_tokens": 187}, "time": 1790000010},
                 {"event": "launched", "properties": {}, "time": 1790090000},
                 {"event": "message_send", "properties": {"main_model": "gpt-4o", "prompt_tokens": 10, "completion_tokens": 1}, "time": 1790090010}])
    use_paths(aider_log=log)
    live = rows("ad")
    assert len({k[1] for k in live.usage}) == 2
    assert sum(v[0] for v in live.usage.values()) == 2320 and all(k[4] == "openai" for k in live.usage)
