"""Topic key replace/delete. Run: python tests/test_topic_replace.py"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("GATEWAY_API_KEY", "")
os.environ.setdefault("LLM_API_KEY", "")

from app import config, db  # noqa: E402


def _user():
    config.DB_PATH = Path(tempfile.mkdtemp()) / "replace.db"
    db.init()
    return db.create_admin("replacer", "password1")["id"]


def _session(uid, topic="面试", level="intermediate", mode="questions", language="en"):
    return db.create_session({
        "language": language, "level": level, "mode": mode, "topic": topic, "title": topic,
        "questions": [{"text": "Q?", "translation": "问？"}],
    }, uid)


def test_delete_sessions_by_topic():
    uid = _user()
    a = _session(uid, "面试")
    b = _session(uid, "面试")
    c = _session(uid, "面试", mode="dialogue")
    d = _session(uid, "餐厅")
    deleted = db.delete_sessions_by_topic(uid, "en", "intermediate", "questions", "面试")
    assert set(deleted) == {a, b}
    left = {s["id"] for s in db.list_sessions(uid)}
    assert left == {c, d}


def test_import_key_is_case_insensitive_topic():
    uid = _user()
    old = _session(uid, "Restaurant")
    deleted = db.delete_sessions_by_topic(uid, "en", "intermediate", "questions", "restaurant")
    assert deleted == [old]


if __name__ == "__main__":
    test_delete_sessions_by_topic()
    print("ok test_delete_sessions_by_topic")
    test_import_key_is_case_insensitive_topic()
    print("ok test_import_key_is_case_insensitive_topic")
