from conftest import claude_line, make_opencode, make_zcode, ms, use_paths

from toktop import sources


def test_opencode_one_row_per_session_and_skips_empty(tmp_path):
    db = tmp_path / "opencode.db"
    make_opencode(db, [
        ("s1", "Add tests", "/home/u/proj", "deepseek-v4.1-flash", "opencode-go", 100, 20, 1000, 0, 5, ms("2026-03-02")),
        ("s2", "empty", "/home/u/proj", "x", "y", 0, 0, 0, 0, 0, ms("2026-03-02")),
        ("s3", "bot", "/home/u/OpenBot/Agents/agent-1", "glm-5.3-flash", "zai", 1, 1, 1, 0, 0, ms("2026-03-03")),
    ])
    use_paths(opencode=db)
    live = sources.Live()
    sources.load_oc(live)
    assert live.usage[("oc", "s1", "2026-03-02", "deepseek-v4.1-flash", "opencode-go")] == [100, 20, 1000, 0, 5]
    assert not any(k[1] == "s2" for k in live.usage)
    assert ("ob", "s3", "2026-03-03", "glm-5.3-flash", "zai") in live.usage  # OpenBot sessions are their own source
    assert live.sess[("oc", "s1")]["project"] == "proj"
    assert {"oc", "ob"} <= live.found


def test_zcode_subtracts_cache_from_input(tmp_path):
    db = tmp_path / "z.sqlite"
    make_zcode(db, [("z1", ms("2026-03-05"), "glm-5.3-flash", "builtin:zai", 1100, 50, 1000, 0, 7)])
    use_paths(zcode=db)
    live = sources.Live()
    sources.load_zc(live)
    (key, val), = live.usage.items()
    assert key[0] == "zc" and key[4] == "zai"
    assert val == [100, 50, 1000, 0, 7]


def test_claude_dedupes_streamed_messages_and_reads_titles(tmp_path):
    proj = tmp_path / "projects" / "-home-u-app"
    proj.mkdir(parents=True)
    lines = [
        claude_line("m1", "c1", "2026-03-04T10:00:00Z", "/home/u/app"),
        claude_line("m1", "c1", "2026-03-04T10:00:01Z", "/home/u/app"),  # same message, streamed twice
        claude_line("m2", "c1", "2026-03-04T11:00:00Z", "/home/u/app", inp=1, out=1, cr=1),
        '{"type": "custom-title", "sessionId": "c1", "customTitle": "Refactor"}',
        claude_line("m3", "c2", "2026-03-04T12:00:00Z", "/tmp/openbot-pro"),
        "not json",
    ]
    (proj / "a.jsonl").write_text("\n".join(lines) + "\n")
    use_paths(claude=tmp_path / "projects")
    live = sources.Live()
    sources.load_cc(live)
    cc = [v for k, v in live.usage.items() if k[0] == "cc"]
    assert sum(v[0] for v in cc) == 11  # m1 once + m2
    assert live.sess[("cc", "c1")]["title"] == "Refactor"
    assert any(k[0] == "ob" and k[1] == "c2" for k in live.usage)


def test_missing_apps_are_ignored():
    live = sources.Live()
    for _, fn in sources.LOADERS:
        fn(live)
    assert not live.usage and not live.found


def test_is_openbot():
    assert sources.is_openbot("/Users/a/OpenBot/Agents/agent-x")
    assert sources.is_openbot("C:\\Temp\\openbot-profile-abc")
    assert not sources.is_openbot("/home/u/robot")
    assert not sources.is_openbot("")
