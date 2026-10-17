"""Accounts, invites and gateway client tests (no network). Run: python tests/test_accounts_gateway.py"""
import os
import sys
import tempfile
import threading
import types
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["GATEWAY_API_KEY"] = ""  # never call the real gateway from tests
os.environ["LLM_API_KEY"] = ""

from app import auth, config, db  # noqa: E402


def fresh_db():
    config.DB_PATH = Path(tempfile.mkdtemp()) / "t.db"
    db.init()


def test_password_hashing():
    h = auth.hash_password("correct horse")
    assert auth.verify_password("correct horse", h)
    assert not auth.verify_password("wrong", h)
    assert not auth.verify_password("x", "garbage")


def test_setup_login_tokens_and_legacy_sessions():
    fresh_db()
    legacy = db.create_session({"title": "old"}, None)  # made before accounts existed
    assert db.count_users() == 0
    admin = db.create_admin("eric", auth.hash_password("password1"))
    assert admin["role"] == "admin"
    assert db.get_session(legacy)["userId"] == admin["id"]
    user = auth.login("ERIC", "password1")  # usernames are case-insensitive
    token = auth.issue_token(user["id"])
    assert auth.user_for_token(token)["username"] == "eric"
    auth.revoke_token(token)
    assert auth.user_for_token(token) is None
    for bad in [("eric", "nope"), ("ghost", "password1")]:
        try:
            auth.login(*bad)
            assert False
        except auth.AuthError:
            pass


def test_invites_register_and_limits():
    fresh_db()
    admin = db.create_admin("admin", auth.hash_password("password1"))
    inv = db.create_invite(auth.new_invite_code(), admin["id"], 2, 7, "朋友")
    assert inv["status"] == "active" and len(inv["code"]) == 9
    code = inv["code"]
    u1 = db.register_with_invite("amy", auth.hash_password("password2"), auth.normalize_code(code.lower().replace("-", "")))
    assert u1["role"] == "user"
    try:
        db.register_with_invite("AMY", auth.hash_password("password2"), code)
        assert False, "duplicate username"
    except ValueError as e:
        assert "已经被注册" in str(e)
    db.register_with_invite("bob", auth.hash_password("password3"), code)
    try:
        db.register_with_invite("cat", auth.hash_password("password4"), code)
        assert False, "invite used up"
    except ValueError as e:
        assert "用完" in str(e)
    listed = db.list_invites()[0]
    assert listed["status"] == "used" and listed["uses"] == 2 and "amy" in listed["usedBy"]
    inv2 = db.create_invite(auth.new_invite_code(), admin["id"], 1, None, "")
    db.revoke_invite(inv2["code"])
    assert "作废" in db.check_invite(inv2["code"])
    assert "不存在" in db.check_invite("ZZZZ-ZZZZ")


def test_disable_user_and_session_isolation():
    fresh_db()
    admin = db.create_admin("admin", auth.hash_password("password1"))
    code = db.create_invite(auth.new_invite_code(), admin["id"], 1, 7, "")["code"]
    amy = db.register_with_invite("amy", auth.hash_password("password2"), code)
    token = auth.issue_token(amy["id"])
    db.create_session({"title": "amy's"}, amy["id"])
    db.create_session({"title": "admin's"}, admin["id"])
    assert [s["title"] for s in db.list_sessions(amy["id"])] == ["amy's"]
    assert len(db.list_sessions(None)) == 2
    users = {u["username"]: u for u in db.list_users()}
    assert users["amy"]["practiceCount"] == 1 and users["amy"]["invitedBy"] == "admin"
    db.set_disabled(amy["id"], True)
    assert auth.user_for_token(token) is None
    try:
        auth.login("amy", "password2")
        assert False
    except auth.AuthError as e:
        assert "停用" in str(e)


def test_only_one_admin_even_raced():
    fresh_db()
    wins, errors = [], []

    def go(name):
        try:
            wins.append(db.create_admin(name, auth.hash_password("password1"))["username"])
        except ValueError as e:
            errors.append(str(e))

    threads = [threading.Thread(target=go, args=(name,)) for name in ("ada", "bea")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(wins) == 1 and len(errors) == 1
    assert "已经创建" in errors[0]
    assert db.count_users() == 1


def test_invite_cannot_be_overused():
    fresh_db()
    admin = db.create_admin("admin", auth.hash_password("password1"))
    code = db.create_invite(auth.new_invite_code(), admin["id"], 1, 7, "")["code"]
    errors = []

    def go(name):
        try:
            db.register_with_invite(name, auth.hash_password("password2"), code)
        except ValueError as e:
            errors.append(str(e))

    threads = [threading.Thread(target=go, args=(name,)) for name in ("amy", "bob")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    users = [u for u in db.list_users() if u["role"] == "user"]
    assert len(users) == 1 and len(errors) == 1
    assert "用完" in errors[0]


def test_frontend_file_stays_inside_dist():
    config.DB_PATH = Path(tempfile.mkdtemp()) / "spa.db"
    import app.main as main

    root = Path(tempfile.mkdtemp())
    (root / "index.html").write_text("home", encoding="utf-8")
    (root / "app.js").write_text("js", encoding="utf-8")
    secret = root.parent / "secret.txt"
    secret.write_text("nope", encoding="utf-8")
    main.DIST = root
    assert main.frontend_file("app.js") == (root / "app.js").resolve()
    assert main.frontend_file("../secret.txt").name == "index.html"
    assert main.frontend_file("app/../../secret.txt").name == "index.html"
    assert main.frontend_file("").name == "index.html"


def test_credential_rules():
    for name, pw in [("a", "password1"), ("ok_name", "short"), ("bad name!", "password1")]:
        try:
            auth.check_credentials(name, pw)
            assert False, (name, pw)
        except auth.AuthError:
            pass
    assert auth.check_credentials(" 小明 ", "password1") == "小明"


# ------------------------------------------------------------ gateway client
class FakeResp:
    def __init__(self, status=200, json_body=None, content=b"", ctype="application/json"):
        self.status_code, self._json, self.content = status, json_body, content
        self.headers = {"content-type": ctype}
        self.text = str(json_body)

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


def install_fake_httpx(responder):
    calls = []
    fake = types.ModuleType("httpx")

    class HTTPError(Exception):
        pass

    def post(url, timeout=None, **kw):
        calls.append({"url": url, **kw})
        return responder(url, kw)

    class TimeoutException(HTTPError):
        pass

    class NetworkError(HTTPError):
        pass

    fake.post, fake.HTTPError, fake.Response = post, HTTPError, FakeResp
    fake.TimeoutException, fake.NetworkError = TimeoutException, NetworkError
    sys.modules["httpx"] = fake
    import importlib

    import app

    sys.modules.pop("app.gateway", None)
    if hasattr(app, "gateway"):
        delattr(app, "gateway")
    return importlib.import_module("app.gateway"), calls


def test_gateway_requests():
    config.GATEWAY_API_KEY, config.GATEWAY_URL, config.GATEWAY_TENANT = "aam_test", "https://gw.example/", "langstudy"

    def responder(url, kw):
        if url.endswith("/api/ai/chat"):
            return FakeResp(json_body={"choices": [{"message": {"content": '```json\n{"ok": 1}\n```'}}]})
        if url.endswith("/api/ai/transcribe"):
            return FakeResp(json_body={"text": " hello there "})
        if url.endswith("/api/ai/tts"):
            return FakeResp(content=b"ID3audio", ctype="audio/mpeg")
        if url.endswith("/api/ai/pronounce"):
            return FakeResp(json_body={"score": 82, "transcript": "hi", "issues": [{"quote": "a", "note": "b"}], "note": "ok"})

    gw, calls = install_fake_httpx(responder)
    from app import ai

    assert ai.chat_json("sys", "user", fast=True) == {"ok": 1}
    chat = calls[-1]
    assert chat["url"] == "https://gw.example/api/ai/chat"
    assert chat["headers"]["Authorization"] == "Bearer aam_test"
    assert chat["json"]["capability"] == "fast-chat" and chat["json"]["tenantId"] == "langstudy"
    assert chat["json"]["messages"][0]["role"] == "system" and chat["json"]["stream"] is False

    assert gw.transcribe(b"abc", "a.webm", "audio/webm", "ja") == "hello there"
    t = calls[-1]
    assert t["files"]["file"][0] == "a.webm" and t["data"]["capability"] == "speech" and t["data"]["language"] == "ja"
    assert "Content-Type" not in t["headers"]  # multipart: let the client set the boundary

    assert gw.tts("Hello", "FunAudioLLM/CosyVoice2-0.5B:anna", 1.2) == b"ID3audio"
    body = calls[-1]["json"]
    assert body["input"] == "Hello" and body["response_format"] == "mp3" and body["speed"] == 1.2 and body["capability"] == "tts"

    r = gw.pronounce(b"abc", "a.webm", "audio/webm", "Good morning.", "en")
    assert r["score"] == 82.0 and r["issues"][0]["note"] == "b"
    p = calls[-1]["data"]
    assert p["capability"] == "pronunciation" and p["text"] == "Good morning." and p["language"] == "en"


def test_gateway_errors():
    config.GATEWAY_API_KEY = "aam_test"
    gw, _ = install_fake_httpx(lambda url, kw: FakeResp(status=402, json_body={"detail": "insufficient points"}))
    try:
        gw.chat([{"role": "user", "content": "x"}], "fast-chat")
        assert False
    except gw.GatewayError as e:
        assert "积分不足" in str(e) and "402" in str(e)


def test_evaluate_prefers_pronunciation_assessment():
    from app import evaluate as ev

    orig = config.demo_mode
    config.demo_mode = lambda: True
    try:
        content = {"mode": "article", "language": "en", "level": "intermediate", "sentences": [], "questions": []}
        turns = [{"kind": "shadow", "reference": "Good morning everyone.", "answer": "good morning everyone",
                  "input": "voice", "durationSec": 2, "pronScore": 64, "pronNote": "元音偏短"}]
        r = ev.evaluate(content, turns)
    finally:
        config.demo_mode = orig
    dims = {d["key"]: d["score"] for d in r["dimensions"]}
    assert dims["pronunciation"] == 64  # demo judgement echoes objective score
    assert r["stats"]["pronSource"] == "assessment" and r["items"][0]["pronNote"] == "元音偏短"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
