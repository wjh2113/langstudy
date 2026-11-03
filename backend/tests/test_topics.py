"""Topic listing. Run: python tests/test_topics.py"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("GATEWAY_API_KEY", "")
os.environ.setdefault("LLM_API_KEY", "")

from app import config, db  # noqa: E402


def test_list_topics_groups_by_key():
    config.DB_PATH = Path(tempfile.mkdtemp()) / "topics.db"
    db.init()
    uid = db.create_admin("topicer", "password1")["id"]
    q = {"language": "en", "level": "intermediate", "mode": "questions", "intro": "", "questions": [{"text": "Q", "tip": ""}]}
    db.create_session({**q, "topic": "面试", "title": "A"}, uid)
    time.sleep(1.05)
    latest = db.create_session({**q, "topic": "面试", "title": "B"}, uid)
    db.create_session({**q, "level": "beginner", "topic": "点餐", "title": "C"}, uid)
    topics = db.list_topics(uid)
    assert len(topics) == 2
    interview = next(t for t in topics if t["topic"] == "面试")
    assert interview["id"] == latest and interview["attempts"] == 2 and interview["mine"] is True
    assert next(t for t in topics if t["topic"] == "点餐")["attempts"] == 1
    with db._conn() as c:
        c.execute("UPDATE sessions SET overall=88, report='{}' WHERE id=?", (latest,))
    db.create_invite("join", uid, 1, None, "")
    other = db.register_with_invite("learner", "password1", "join")["id"]
    seen = db.list_topics(other)
    shared = next(t for t in seen if t["topic"] == "面试")
    assert shared["mine"] is False and shared["overall"] is None and shared["done"] is False
    assert shared["ownerName"] == "topicer" and shared["attempts"] == 0
    copy_id = db.begin_shared_topic(shared["id"], other)
    assert copy_id != shared["id"]
    copied = db.get_session(copy_id)
    assert copied["userId"] == other and copied["turns"] == [] and copied["report"] is None
    again = db.list_topics(other)
    shared = next(t for t in again if t["topic"] == "面试")
    assert shared["practiceId"] == copy_id and shared["attempts"] == 1 and shared["mine"] is False
    assert db.session_ids_by_topic(other, "en", "intermediate", "questions", "面试") == []


if __name__ == "__main__":
    test_list_topics_groups_by_key()
    print("ok test_list_topics_groups_by_key")
