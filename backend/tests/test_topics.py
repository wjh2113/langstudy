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
    assert interview["id"] == latest and interview["attempts"] == 2
    assert next(t for t in topics if t["topic"] == "点餐")["attempts"] == 1


if __name__ == "__main__":
    test_list_topics_groups_by_key()
    print("ok test_list_topics_groups_by_key")
