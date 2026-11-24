import sqlite3

from conftest import make_opencode, ms, use_paths

from toktop import config, history


def test_history_never_goes_down_when_an_app_forgets(tmp_path):
    db = tmp_path / "opencode.db"
    make_opencode(db, [("s1", "t", "/p/a", "m", "prov", 100, 10, 0, 0, 0, ms("2026-02-01")),
                       ("s2", "t", "/p/b", "m", "prov", 50, 5, 0, 0, 0, ms("2026-02-02"))])
    use_paths(opencode=db)
    found, errors = history.sync()
    assert found == {"oc"} and not errors

    con = sqlite3.connect(db)  # the app deletes a session and lowers another
    con.execute("DELETE FROM session_v2 WHERE id='s2'")
    con.execute("UPDATE session_v2 SET tokens_input=1 WHERE id='s1'")
    con.commit()
    con.close()
    history.sync()

    rows, sess, meta = history.load_history()
    assert sorted((r[1], r[5]) for r in rows) == [("s1", 100), ("s2", 50)]
    assert "last_sync" in meta and "seen_oc" in meta


def test_deleted_app_keeps_its_history(tmp_path):
    db = tmp_path / "opencode.db"
    make_opencode(db, [("s1", "t", "/p/a", "m", "prov", 100, 10, 0, 0, 0, ms("2026-02-01"))])
    use_paths(opencode=db)
    history.sync()
    db.unlink()
    use_paths(opencode=db)
    found, _ = history.sync(rebuild=True)  # rebuild only wipes apps that are still installed
    assert "oc" not in found
    rows, _, _ = history.load_history()
    assert len(rows) == 1


def test_openbot_migration_is_idempotent():
    con = history.hist_connect()
    con.execute("DELETE FROM meta WHERE k='mig_openbot'")
    con.execute("INSERT INTO usage VALUES('cc','x','2026-01-01','m','p',1,1,1,0,0)")
    con.execute("INSERT INTO sessions VALUES('cc','x','', 'OpenBot · Editor', NULL, NULL)")
    con.commit()
    history.migrate(con)
    history.migrate(con)
    assert con.execute("SELECT src FROM usage").fetchall() == [("ob",)]
    assert con.execute("SELECT src, project FROM sessions").fetchall() == [("ob", "Editor")]
    con.close()


def test_offline_sync_reads_nothing(tmp_path):
    db = tmp_path / "opencode.db"
    make_opencode(db, [("s1", "t", "/p/a", "m", "prov", 100, 10, 0, 0, 0, ms("2026-02-01"))])
    use_paths(opencode=db)
    config.OFFLINE = True
    found, _ = history.sync()
    assert found == set()
    assert history.load_history()[0] == []
