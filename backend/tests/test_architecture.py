"""Migrations, autosave, rate limiting, jobs, AI accounting, token savers, disk cleanup, API flow.
Run: python tests/test_architecture.py   (the API test needs fastapi installed)"""
import json
import os
import sqlite3
import sys
import tempfile
import time
import types
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["GATEWAY_API_KEY"] = ""
os.environ["LLM_API_KEY"] = ""

from app import (ai, config, conversation, db, evaluate as ev, jobs, llm, maintenance, migrations,  # noqa: E402
                 ratelimit, translate, tts)


def fresh_db():
    config.DB_PATH = Path(tempfile.mkdtemp()) / "t.db"
    db.init()


# ------------------------------------------------------------ migrations
def test_migrations_upgrade_old_database():
    """A database from before migrations (answers as a JSON blob) is upgraded in place."""
    config.DB_PATH = Path(tempfile.mkdtemp()) / "old.db"
    c = sqlite3.connect(config.DB_PATH)
    c.executescript("""
        CREATE TABLE sessions (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, language TEXT, level TEXT, mode TEXT,
            topic TEXT, title TEXT, content TEXT NOT NULL, turns TEXT, report TEXT, overall INTEGER);
    """)
    turns = [{"id": "q0", "kind": "answer", "prompt": "Q", "answer": "I goes"}]
    report = {"overall": 70, "items": [{"corrected": "I go", "notes": "主谓一致"}]}
    c.execute("INSERT INTO sessions VALUES ('aaaaaaaaaaaa','2026-01-01T00:00:00','en','beginner','questions','t','T','{}',?,?,70)",
              (json.dumps(turns), json.dumps(report)))
    c.commit()
    c.close()
    db.init()
    db.init()  # idempotent
    with db._conn() as conn:
        versions = [r[0] for r in conn.execute("SELECT version FROM schema_version ORDER BY version")]
        row = conn.execute("SELECT turn_key, answer, corrected, notes FROM turns").fetchone()
    assert versions == [n for n, _ in migrations.MIGRATIONS]
    assert tuple(row) == ("q0", "I goes", "I go", "主谓一致")
    s = db.get_session("aaaaaaaaaaaa")
    assert s["turns"] == turns and s["report"]["overall"] == 70


def test_migration_failure_rolls_back():
    config.DB_PATH = Path(tempfile.mkdtemp()) / "m.db"
    db.init()

    def broken(c):
        c.execute("CREATE TABLE half_done (x)")
        raise RuntimeError("boom")

    migrations.MIGRATIONS.append((999, broken))
    try:
        conn = db._conn()
        try:
            migrations.run(conn)
            assert False
        except RuntimeError:
            pass
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='half_done'").fetchone()
        assert migrations.current_version(conn) == migrations.MIGRATIONS[-2][0]
        conn.close()
    finally:
        migrations.MIGRATIONS.pop()


# --------------------------------------------------------- autosave/turns
def test_progress_autosave_resume_and_grading():
    fresh_db()
    sid = db.create_session({"language": "en", "mode": "questions", "title": "T"}, None)
    t1 = [{"id": "q0", "kind": "answer", "answer": "hello"}]
    db.save_progress(sid, t1, {"index": 1})
    t2 = t1 + [{"id": "q1", "kind": "answer", "answer": "I has a cat", "input": "voice"}]
    db.save_progress(sid, t2, {"index": 2, "chat": [{"role": "ai", "text": "hi"}]})
    s = db.get_session(sid)
    assert [t["id"] for t in s["turns"]] == ["q0", "q1"] and s["state"]["index"] == 2
    assert db.list_sessions(None)[0]["answered"] == 2
    db.save_report(sid, t2, {"overall": 80, "items": [{"key": "q0", "ok": True}, {"key": "q1", "ok": False,
                                                                                   "corrected": "I have a cat", "notes": "have/has"}]})
    s = db.get_session(sid)
    assert s["state"] is None and s["report"]["overall"] == 80
    try:
        db.save_progress(sid, t2, None)
        assert False, "finished sessions are read-only"
    except ValueError:
        pass
    stats = db.mistake_stats("en")
    assert stats["graded"] == 2 and stats["flagged"] == 1 and stats["topNotes"][0]["notes"] == "have/has"
    db.delete_session(sid)
    with db._conn() as c:
        assert c.execute("SELECT COUNT(*) FROM turns").fetchone()[0] == 0  # cascade


def test_evaluate_items_carry_keys_and_ok_flags():
    orig_demo, orig_chat = config.demo_mode, ev.chat_json
    config.demo_mode = lambda: False
    seen = {}

    def fake(system, user, temperature=0.3, fast=False, task=""):
        seen.update(prompt=user, fast=fast, task=task)
        return {"scores": {"grammar": 70}, "items": [{"index": 1, "corrected": "I have a cat", "notes": "has→have"}],
                "vocabulary": [{"word": w} for w in "abcdef"]}

    ev.chat_json = fake
    try:
        content = {"language": "en", "level": "beginner", "mode": "article", "topic": "t",
                   "sentences": [{"text": "THE WHOLE ARTICLE TEXT"}]}
        turns = [{"id": "a", "kind": "answer", "prompt": "Q1", "answer": "Fine thanks"},
                 {"id": "b", "kind": "answer", "prompt": "Q2", "answer": "I has a cat"}]
        r = ev.evaluate(content, turns)
    finally:
        config.demo_mode, ev.chat_json = orig_demo, orig_chat
    assert "THE WHOLE ARTICLE TEXT" not in seen["prompt"]  # no full original text any more
    assert "只给 3 个" in seen["prompt"] and "没问题的不要列" in seen["prompt"]
    assert seen["fast"] is True and seen["task"] == "evaluate"  # short practice -> fast model
    assert [(i["key"], i["ok"]) for i in r["items"]] == [("a", True), ("b", False)]


def test_long_practice_uses_quality_model():
    turns = [{"answer": "word " * 60} for _ in range(4)]
    assert not ev.is_short(turns, "en")
    assert ev.is_short(turns[:2], "en")


# -------------------------------------------------------- token savers
def test_chat_sends_recent_rounds_plus_summary():
    content = {"language": "en", "level": "beginner", "scene": "cafe", "goal": "order",
               "aiRole": {"name": "Barista"}, "userRole": {"name": "Customer"}, "mode": "chat"}
    history = []
    for i in range(10):
        history += [{"role": "ai", "text": f"ai-{i}"}, {"role": "user", "text": f"user-{i}"}]
    p = conversation.build_prompt(content, history, "顾客点了拿铁")
    assert "ai-3" not in p and "user-3" not in p  # older rounds are not sent verbatim
    assert "ai-4" in p and "user-9" in p
    assert "顾客点了拿铁" in p and '"summary"' in p
    short = conversation.build_prompt(content, history[:4], "")
    assert "摘要" not in short and '"summary"' not in short


def test_translate_on_demand_is_cached_and_batched():
    fresh_db()
    calls = []
    orig_demo, orig_chat = config.demo_mode, translate.chat_json
    config.demo_mode = lambda: False
    translate.chat_json = lambda s, u, **kw: calls.append(u) or {"translations": ["你好", "谢谢"]}
    try:
        assert translate.translate_many(["Hello", "Thanks", "Hello"], "en") == ["你好", "谢谢", "你好"]
        assert len(calls) == 1 and calls[0].count("Hello") == 1  # one call, duplicates sent once
        assert translate.translate_many(["Thanks", ""], "en") == ["谢谢", ""]
        assert len(calls) == 1  # served from the cache
    finally:
        config.demo_mode, translate.chat_json = orig_demo, orig_chat


def test_generated_material_has_no_translations():
    from app import generate as gen

    for mode in ("article", "dialogue", "questions", "chat", "dictation"):
        c = gen.generate("en", "beginner", mode, "面试", 3)
        assert '"translation"' not in json.dumps(c) and "openingTranslation" not in c, mode
        assert "translation" not in gen.build_prompt("en", "beginner", mode, "t", 3).split("不需要中文翻译")[1]


def test_json_repair_before_retry():
    fresh_db()
    replies = iter(['好的 {"a": [1, 2,], "b": "cut', '{"ok": 1}'])
    orig = ai.raw_chat
    ai.raw_chat = lambda *a, **k: (next(replies), {})
    try:
        assert ai.chat_json("s", "u", task="t") == {"a": [1, 2], "b": "cut"}  # repaired, no second call
        assert next(replies) == '{"ok": 1}'
        replies2 = iter(["no json here at all", '{"ok": 2}'])
        ai.raw_chat = lambda *a, **k: (next(replies2), {})
        assert ai.chat_json("s", "u", task="t") == {"ok": 2}  # unrepairable -> asked once more
    finally:
        ai.raw_chat = orig


# ------------------------------------------------- AI accounting & limits
def test_usage_is_recorded_per_user_and_daily_limit():
    fresh_db()
    user = {"id": 7, "role": "user"}
    orig, orig_limit = ai.raw_chat, config.AI_DAILY_LIMIT
    ai.raw_chat = lambda *a, **k: ('{"x": 1}', {"total_tokens": 120, "credits": 0.5})
    config.AI_DAILY_LIMIT = 2
    try:
        with ai.scope(user, "sess"):
            ai.chat_json("s", "u", task="generate")
            ai.chat_json("s", "u", task="notes", fast=True)
            try:
                ai.chat_json("s", "u", task="chat")
                assert False, "over the daily limit"
            except ai.QuotaError:
                pass
        with ai.scope({"id": 1, "role": "admin"}):
            for _ in range(3):
                ai.chat_json("s", "u", task="chat")  # admins are not limited
    finally:
        ai.raw_chat, config.AI_DAILY_LIMIT = orig, orig_limit
    with db._conn() as c:
        rows = c.execute("SELECT user_id, session_id, task, total_tokens, credits FROM ai_usage WHERE user_id=7").fetchall()
    assert [tuple(r) for r in rows] == [(7, "sess", "generate", 120, 0.5), (7, "sess", "notes", 120, 0.5)]


def test_gateway_retries_with_same_idempotency_key():
    calls = []
    fake = types.ModuleType("httpx")

    class HTTPError(Exception):
        pass

    class TimeoutException(HTTPError):
        pass

    class NetworkError(HTTPError):
        pass

    class Resp:
        def __init__(self, status, body):
            self.status_code, self._body, self.headers, self.text = status, body, {"x-credits-charged": "1.5"}, ""

        def json(self):
            return self._body

    def post(url, timeout=None, headers=None, **kw):
        calls.append(headers)
        if len(calls) == 1:
            raise TimeoutException("timed out")
        if len(calls) == 2:
            return Resp(503, {"detail": "busy"})
        return Resp(200, {"choices": [{"message": {"content": "{}"}}], "usage": {"total_tokens": 9}})

    fake.post, fake.HTTPError, fake.TimeoutException, fake.NetworkError, fake.Response = post, HTTPError, TimeoutException, NetworkError, Resp
    real = sys.modules.get("httpx")
    sys.modules["httpx"] = fake
    sys.modules.pop("app.gateway", None)
    import importlib

    gw = importlib.import_module("app.gateway")
    gw.time.sleep = lambda s: None
    config.GATEWAY_API_KEY = "k"
    try:
        text, usage = gw.chat_full([{"role": "user", "content": "x"}], "fast-chat")
    finally:
        config.GATEWAY_API_KEY = ""
        if real:
            sys.modules["httpx"] = real
        sys.modules.pop("app.gateway", None)
    keys = {h[config.GATEWAY_IDEMPOTENCY_HEADER] for h in calls}
    assert len(calls) == 3 and len(keys) == 1  # three attempts, one idempotency key
    assert usage == {"total_tokens": 9, "credits": 1.5}


# --------------------------------------------------------- rate limiting
def test_account_and_ip_lockout():
    fresh_db()
    for _ in range(4):
        ratelimit.fail(ip="1.1.1.1", account="Alice")
    ratelimit.check(ip="1.1.1.1", account="alice")  # 4 failures: still allowed
    ratelimit.fail(ip="1.1.1.1", account="alice")
    try:
        ratelimit.check(account="ALICE")
        assert False
    except ratelimit.Locked as e:
        assert 0 < e.retry_after <= 300 and "分钟" in str(e)
    ratelimit.check(ip="2.2.2.2", account="bob")  # others unaffected
    assert ratelimit.retry_after("account", "alice", now=time.time() + 301) == 0  # lock expires
    ratelimit.clear(account="alice")
    ratelimit.check(account="alice")
    for _ in range(10):
        ratelimit.fail(invite="3.3.3.3")
    assert ratelimit.retry_after("invite", "3.3.3.3") > 0


# ------------------------------------------------------------------ jobs
def test_jobs_run_dedupe_and_errors():
    fresh_db()
    user = {"id": 1, "role": "user"}
    jid = jobs.submit("notes", user, lambda: {"ok": True}, session_id="s1", run_inline=True)
    assert jobs.get(jid)["status"] == "done" and jobs.get(jid)["result"] == {"ok": True}

    def boom():
        raise ValueError("模型挂了")

    jid = jobs.submit("evaluate", user, boom, session_id="s1", run_inline=True)
    assert jobs.get(jid)["status"] == "error" and jobs.get(jid)["error"] == "模型挂了"
    # a second submit while one is pending returns the same job
    with db._conn() as c:
        c.execute("INSERT INTO jobs VALUES ('pending1', 1, 's2', 'evaluate', 'pending', NULL, NULL, ?, ?)",
                  (db._now(), db._now()))
    assert jobs.submit("evaluate", user, lambda: 1, session_id="s2") == "pending1"
    jobs.recover()
    assert jobs.get("pending1")["status"] == "error"


def test_jobs_use_callers_ai_scope():
    fresh_db()
    seen = {}

    def work():
        seen.update(ai._ctx())
        return 1

    jid = jobs.submit("generate", {"id": 5, "role": "user"}, work, run_inline=True)
    assert jobs.get(jid)["status"] == "done" and seen["user_id"] == 5


# ------------------------------------------------------------------- disk
def test_tts_cache_lru_prune():
    config.TTS_CACHE_DIR = Path(tempfile.mkdtemp())
    now = time.time()
    for i in range(10):
        p = config.TTS_CACHE_DIR / f"{i}.mp3"
        p.write_bytes(b"x" * 1000)
        os.utime(p, (now - 1000 + i, now - 1000 + i))  # 0 is the least recently used
    removed = tts.prune_cache(max_bytes=5000)
    left = sorted(int(p.stem) for p in config.TTS_CACHE_DIR.glob("*.mp3"))
    assert removed == 6 and left == [6, 7, 8, 9]
    assert tts.prune_cache(max_bytes=5000) == 0


def test_recordings_retention():
    maintenance.AUDIO_DIR = Path(tempfile.mkdtemp())
    old_dir, new_dir = maintenance.AUDIO_DIR / "aaaaaaaaaaaa", maintenance.AUDIO_DIR / "bbbbbbbbbbbb"
    old_dir.mkdir()
    new_dir.mkdir()
    (old_dir / "q0.webm").write_bytes(b"1")
    (new_dir / "q0.webm").write_bytes(b"1")
    t = time.time() - 100 * 86400
    os.utime(old_dir / "q0.webm", (t, t))
    assert maintenance.prune_recordings(days=90) == 1
    assert not old_dir.exists() and (new_dir / "q0.webm").exists()
    assert maintenance.prune_recordings(days=0) == 0  # 0 = keep forever


# -------------------------------------------------------------- API flow
def test_api_flow():
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        print("skip test_api_flow (fastapi not installed)")
        return
    fresh_db()
    from app import main

    with TestClient(main.app) as c:
        assert c.post("/api/auth/setup", json={"username": "admin", "password": "password1"}).status_code == 200

        def wait(job_id):
            for _ in range(100):
                j = c.get(f"/api/jobs/{job_id}").json()
                if j["status"] in ("done", "error"):
                    return j
                time.sleep(0.05)
            raise AssertionError("job did not finish")

        job = c.post("/api/generate", json={"language": "en", "mode": "questions", "topic": "面试", "count": 3}).json()
        res = wait(job["jobId"])["result"]
        sid, q = res["id"], res["content"]["questions"][0]["text"]
        assert c.post("/api/translate", json={"texts": [q], "language": "en"}).json()["translations"][0]
        turns = [{"id": "q0", "kind": "answer", "prompt": q, "answer": "I am a developer"}]
        assert c.put(f"/api/sessions/{sid}/progress", json={"turns": turns, "state": {"index": 1}}).status_code == 200
        assert c.get(f"/api/sessions/{sid}").json()["state"] == {"index": 1}
        prev = c.get("/api/sessions/previous", params={"language": "en", "level": "intermediate",
                                                        "mode": "questions", "topic": " 面试 "}).json()["previous"]
        assert prev["id"] == sid
        rep = wait(c.post("/api/evaluate", json={"sessionId": sid, "turns": turns}).json()["jobId"])
        assert rep["status"] == "done" and rep["result"]["overall"] is not None
        assert c.post("/api/evaluate", json={"sessionId": sid, "turns": turns}).status_code == 409
        share = c.post(f"/api/sessions/{sid}/share").json()
        anon = TestClient(main.app)
        assert anon.get(f"/api/share/{share['token']}").json()["report"]["overall"] == rep["result"]["overall"]
        assert anon.get(f"/api/sessions/{sid}").status_code == 401
        c.delete(f"/api/sessions/{sid}/share")
        assert anon.get(f"/api/share/{share['token']}").status_code == 404
        again = c.post(f"/api/sessions/{sid}/repeat").json()
        assert again["id"] != sid and again["content"]["questions"][0]["text"] == q
        codes = [anon.post("/api/auth/login", json={"username": "admin", "password": "nope-nope"}).status_code
                 for _ in range(6)]
        assert codes[:5] == [401] * 5 and codes[5] == 429
        r = anon.post("/api/auth/login", json={"username": "admin", "password": "password1"})
        assert r.status_code == 429 and int(r.headers["retry-after"]) > 0  # locked even with the right password
        assert c.get("/api/admin/usage").status_code == 200


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
