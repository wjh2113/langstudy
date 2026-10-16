"""Free chat, dictation, coaching, spaced repetition, mistake deck. Run: python tests/test_practice_extras.py"""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["GATEWAY_API_KEY"] = ""  # never call the real gateway from tests
os.environ["LLM_API_KEY"] = ""

from app import coach, config, conversation, db, evaluate as ev, generate as gen, mistakes, srs  # noqa: E402


def fresh_db():
    config.DB_PATH = Path(tempfile.mkdtemp()) / "t.db"
    db.init()
    return db.create_admin("eric", "x")["id"]


# ------------------------------------------------------------- generation
def test_demo_chat_and_dictation():
    for lang in ("en", "ja"):
        chat = gen.generate(lang, "intermediate", "chat", "闲聊")
        assert chat["opening"] and chat["aiRole"]["name"] and chat["goal"]
        d = gen.generate(lang, "intermediate", "dictation", "早晨")
        assert all(b in s["text"] for s in d["sentences"] for b in s["blanks"])


def test_dictation_blanks_must_appear_in_text():
    out = gen.normalize("dictation", {"sentences": [
        {"text": "I take the train.", "blanks": ["train", "bus", "train"]},
        {"text": "No blanks here.", "blanks": ["missing"]},
    ]})
    assert out["sentences"][0]["blanks"] == ["train"] and out["sentences"][1]["blanks"] == []
    try:
        gen.normalize("dictation", {"sentences": [{"text": "x", "blanks": ["y"]}]})
        assert False
    except gen.LLMError:
        pass


def test_focus_picks_mode_topic_and_prompt():
    c = gen.generate("en", "beginner", "", "", focus="fluency")
    assert c["mode"] == "questions" and c["topic"] in gen.AUTO_TOPICS["en"] and c["focus"]["name"] == "口语流利度"
    assert gen.generate("ja", "beginner", "", "", focus="listening")["mode"] == "dictation"
    p = gen.build_prompt("en", "beginner", "questions", "面试", 4, "grammar")
    assert "专项训练：语法准确性" in p
    try:
        gen.generate("en", "beginner", "questions", "")
        assert False, "topic still required without a focus"
    except ValueError:
        pass


# ------------------------------------------------------------ conversation
CHAT = {"mode": "chat", "language": "en", "level": "beginner", "scene": "s", "goal": "g",
        "aiRole": {"name": "Alex", "description": ""}, "userRole": {"name": "You", "description": ""}}


def test_chat_reply_demo_and_rules():
    r = conversation.reply(CHAT, [{"role": "ai", "text": "Hi!"}, {"role": "user", "text": "Hello"}])
    assert r["text"] and r["end"] is False
    hist = [{"role": "ai", "text": "Hi"}]
    for _ in range(4):
        hist += [{"role": "user", "text": "ok"}, {"role": "ai", "text": "..."}]
    assert conversation.reply(CHAT, hist[:-1])["end"] is True  # demo script runs out
    for bad in ([], [{"role": "ai", "text": "Hi"}]):
        try:
            conversation.reply(CHAT, bad)
            assert False
        except ValueError:
            pass


def test_chat_prompt_wraps_up_long_conversations():
    hist = [{"role": "ai", "text": "Q"}]
    for i in range(conversation.MAX_USER_TURNS):
        hist += [{"role": "user", "text": f"a{i}"}, {"role": "ai", "text": "q"}]
    p = conversation.build_prompt(CHAT, hist[:-1])
    assert "收尾告别" in p and "Alex" in p


# -------------------------------------------------------------- evaluation
def test_dictation_only_report():
    content = {"mode": "dictation", "language": "en", "level": "beginner"}
    turns = [
        {"kind": "dictation", "prompt": "I wake up at six thirty.", "reference": "six thirty", "answer": "Six-Thirty"},
        {"kind": "dictation", "prompt": "I take the train.", "reference": "train", "answer": "trian"},
        {"kind": "dictation", "prompt": "x", "reference": "office", "answer": ""},  # left blank
    ]
    r = ev.evaluate(content, turns)
    assert r["overall"] == 33 and [i["correct"] for i in r["items"]] == [True, False, False]
    dims = {d["key"]: d["score"] for d in r["dimensions"]}
    assert dims["listening"] == 33 and dims["grammar"] is None
    assert ev.dictation_correct("ろくじはん", "六時半", "ja") is False
    assert ev.dictation_correct("コーヒー", "こーひー", "ja") is True


def test_mixed_dictation_blends_listening_and_keeps_audio_and_shadow():
    content = {"mode": "article", "language": "en", "level": "beginner", "sentences": [], "questions": []}
    turns = [
        {"kind": "dictation", "reference": "train", "answer": "train"},
        {"kind": "shadow", "reference": "Good morning.", "answer": "good morning", "input": "voice", "durationSec": 2,
         "shadowSync": True, "lagSec": 0.4, "durationRatio": 1.1, "audioUrl": "/api/sessions/abc/audio/s0.webm"},
        {"kind": "answer", "prompt": "Q", "answer": "I like it", "input": "text", "plays": 1},
    ]
    r = ev.evaluate(content, turns)
    assert r["stats"]["dictationAccuracy"] == 100
    shadow = next(i for i in r["items"] if i["kind"] == "shadow")
    assert shadow["audioUrl"].endswith("s0.webm") and shadow["metrics"]["lagSec"] == 0.4
    assert r["items"][-1]["kind"] == "dictation"


# ------------------------------------------------------------------- coach
def test_coach_recommendations():
    assert coach.recommend([])["level"] is None
    up = coach.recommend([{"level": "intermediate", "overall": 90, "dims": {"fluency": 70, "grammar": 90}},
                          {"level": "intermediate", "overall": 86, "dims": {"fluency": 66, "grammar": 92}}])
    assert up["level"] == "advanced" and up["change"] == 1
    assert up["weakest"] == {"key": "fluency", "name": "口语流利度", "score": 68, "mode": "questions"}
    down = coach.recommend([{"level": "intermediate", "overall": 50, "dims": {}}, {"level": "intermediate", "overall": 55, "dims": {}}])
    assert down["level"] == "beginner" and down["change"] == -1
    one = coach.recommend([{"level": "beginner", "overall": 99, "dims": {"listening": 95}}])
    assert one["change"] == 0 and "再做 1 次" in one["reason"] and one["weakest"] is None
    top = coach.recommend([{"level": "advanced", "overall": 95, "dims": {}}] * 3)
    assert top["level"] == "advanced" and top["change"] == 0


# --------------------------------------------------------------------- srs
def test_srs_schedule():
    i, e, r, lapsed = srs.schedule(0, 2.5, 0, "good")
    assert (i, r, lapsed) == (1, 1, False)
    i, e, r, _ = srs.schedule(i, e, r, "good")
    assert i == 3 and r == 2
    i2, e2, r2, _ = srs.schedule(i, e, r, "easy")
    assert i2 > i * e and e2 > e
    i3, e3, r3, lapsed = srs.schedule(i2, e2, r2, "again")
    assert r3 == 0 and lapsed and i3 < 0.01 and e3 < e2
    try:
        srs.schedule(1, 2.5, 1, "perfect")
        assert False
    except ValueError:
        pass


def test_cards_storage_due_and_review():
    uid = fresh_db()
    c1, created = db.add_card(uid, "en", "word", "confident", meaning="自信的", reading="/ˈkɑːnfɪdənt/")
    assert created and c1["meaning"] == "自信的"
    _, again = db.add_card(uid, "en", "word", "confident", meaning="dup")
    assert not again  # no duplicates
    db.add_card(uid, "ja", "pattern", "〜たり〜たりする")
    assert len(db.list_cards(uid, "en", due_only=True)) == 1
    summary = db.card_summary(uid)
    assert summary["en"]["due"] == 1 and summary["ja"]["kinds"]["pattern"]["total"] == 1
    interval, ease, reps, lapsed = srs.schedule(c1["intervalDays"], 2.5, 0, "good")
    db.save_review(c1["id"], interval, ease, reps, lapsed, srs.due_at(interval))
    assert db.list_cards(uid, "en", due_only=True) == []
    assert db.get_card(c1["id"])["reps"] == 1
    assert srs.due_at(1, datetime(2026, 1, 1)) == (datetime(2026, 1, 1) + timedelta(days=1)).isoformat(timespec="seconds")
    db.delete_card(c1["id"])
    assert db.get_card(c1["id"]) is None


def test_mistake_deck_from_report():
    uid = fresh_db()
    report = {"items": [
        {"kind": "answer", "answer": "I want grow with team.", "corrected": "I want to grow with the team.",
         "better": "I'd love to grow with your team.", "notes": "want 后面要加 to"},
        {"kind": "answer", "answer": "It is fine.", "corrected": "It is fine.", "better": "", "notes": "很好"},
        {"kind": "shadow", "answer": "x", "corrected": "y"},
        {"kind": "line", "answer": "Thank", "corrected": "", "notes": ""},
    ]}
    assert mistakes.collect_mistakes(uid, "abc123abc123", "en", report) == 1
    card = db.list_cards(uid, "en", "sentence")[0]
    assert card["front"] == "I want to grow with the team." and card["extra"] == "I want grow with team."
    assert card["example"] == "I'd love to grow with your team." and "to" in card["meaning"]
    assert mistakes.collect_mistakes(uid, "abc123abc123", "en", report) == 0  # already in the deck


def test_recent_results_for_coach():
    uid = fresh_db()
    sid = db.create_session({"language": "en", "level": "beginner", "mode": "questions"}, uid)
    db.save_report(sid, [], {"overall": 77, "dimensions": [{"key": "fluency", "score": 60}]})
    assert db.recent_results(uid, "en") == [{"level": "beginner", "overall": 77, "dims": {"fluency": 60}}]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
