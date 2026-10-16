"""Core logic tests (no network). Run: python -m pytest tests  或  python tests/test_core.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["LLM_API_KEY"] = ""  # force demo mode for generate tests
os.environ["GATEWAY_API_KEY"] = ""  # never call the real gateway from tests

from app import config, evaluate as ev, followup as fu, generate as gen  # noqa: E402
from app.llm import parse_json  # noqa: E402


def test_parse_json_variants():
    assert parse_json('{"a": 1}') == {"a": 1}
    assert parse_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert parse_json('好的，结果如下：{"a": 3} 希望有帮助') == {"a": 3}


def test_demo_generate_all_modes():
    for lang in ("en", "ja"):
        for mode in ("article", "dialogue", "questions"):
            c = gen.generate(lang, "intermediate", mode, "面试", 4)
            assert c["mode"] == mode and c["language"] == lang and c["title"]


def test_normalize_dialogue_role_ids():
    data = {"roles": [{"id": "interviewer", "name": "I"}, {"id": "candidate", "name": "C"}],
            "lines": [{"role": "interviewer", "text": "Hi"}, {"role": "candidate", "text": "Hello"}, {"text": "x"}]}
    c = gen.normalize("dialogue", data)
    assert [l["role"] for l in c["lines"]] == ["A", "B", "A"]


def test_tokens_and_fillers():
    assert ev.tokens("Hello, World! It's me.", "en") == ["hello", "world", "it's", "me"]
    assert ev.tokens("コーヒーを、飲みます。", "ja") == list("こーひーを飲みます")
    assert ev.count_fillers("Um, I think, uh, you know, it's fine", "en") == 3
    assert ev.count_fillers("えっと、あのー、そうですね", "ja") == 2


def test_reference_diff():
    d = ev.reference_diff("I was nervous, but my manager welcomed me.", "I was nervous but manager welcome me", "en")
    missed = [t["t"] for t in d["tokens"] if not t["ok"]]
    assert missed == ["my", "welcomed"]
    assert 0.6 < d["similarity"] < 0.9
    d = ev.reference_diff("私は公園を散歩します。", "わたしは公園を散歩します", "ja")
    assert d["similarity"] > 0.6
    perfect = ev.reference_diff("Good morning.", "good morning", "en")
    assert perfect["similarity"] == 1.0


def test_rate_score():
    assert ev.rate_score(130, 100, 170) == 100
    assert ev.rate_score(50, 100, 170) < 40
    assert 50 <= ev.rate_score(250, 100, 170) < 100


CONTENT = {"mode": "questions", "language": "en", "level": "intermediate", "topic": "interview", "title": "T",
           "questions": [{"text": "Q1"}, {"text": "Q2"}]}


def test_evaluate_demo_text_only():
    turns = [{"kind": "answer", "prompt": "Q1", "answer": "I am a developer with five years of experience.", "input": "text", "plays": 1}]
    r = ev.evaluate(CONTENT, turns)
    dims = {d["key"]: d["score"] for d in r["dimensions"]}
    assert dims["pronunciation"] is None and dims["fluency"] is None
    assert r["overall"] is not None and len(r["items"]) == 1


def test_evaluate_with_fake_llm(monkeypatch=None):
    calls = {}

    def fake_chat_json(system, user, temperature=0.7):
        calls["prompt"] = user
        return {"scores": {"listening": 80, "pronunciation": 70, "fluency": 60, "grammar": 75, "vocabulary": 72, "content": 85},
                "comments": {"grammar": "时态有误"}, "summary": "不错", "strengths": ["a"], "improvements": ["b"],
                "items": [{"index": 0, "corrected": "c", "better": "b", "notes": "n"}],
                "vocabulary": [{"word": "resilient", "meaning": "有韧性的"}]}

    orig_demo, orig_chat = config.demo_mode, ev.chat_json
    config.demo_mode = lambda: False
    ev.chat_json = fake_chat_json
    try:
        turns = [
            {"kind": "answer", "prompt": "Q1", "answer": "um I worked as a developer for five years and I like it", "input": "voice",
             "durationSec": 6, "confidence": 0.9, "plays": 2, "textHidden": True},
            {"kind": "shadow", "reference": "Good morning everyone.", "answer": "good morning everyone", "input": "voice", "durationSec": 2},
            {"kind": "answer", "prompt": "Q2", "answer": "", "input": "text"},  # empty -> dropped
        ]
        r = ev.evaluate(CONTENT, turns)
    finally:
        config.demo_mode, ev.chat_json = orig_demo, orig_chat
    assert "语速" in calls["prompt"] and "口头禅" in calls["prompt"]
    assert len(r["items"]) == 2 and r["items"][1]["diff"]
    dims = {d["key"]: d["score"] for d in r["dimensions"]}
    assert all(v is not None for v in dims.values())
    assert 0 <= r["overall"] <= 100
    assert r["stats"]["fillers"] == 1 and r["stats"]["voiceTurns"] == 2


def test_followup_demo_and_prompt():
    c = {"language": "ja", "level": "intermediate", "topic": "面接", "intro": "日企面试"}
    r = fu.follow_up(c, "自己紹介をお願いします。", "王です。エンジニアです。")
    assert r["text"] and r["translation"]
    try:
        fu.follow_up(c, "Q", "  ")
        assert False, "empty answer should fail"
    except ValueError:
        pass
    p = fu.build_prompt(c, "Q2", "A2", [{"q": "Q1", "a": "A1"}])
    assert "Q1" in p and "A2" in p and "JLPT N3" in p


def test_followup_with_fake_llm():
    orig_demo, orig_chat = config.demo_mode, fu.chat_json
    config.demo_mode = lambda: False
    fu.chat_json = lambda s, u, temperature=0.7, fast=False: {"text": "Which part did you enjoy most?", "translation": "你最喜欢哪部分？"}
    try:
        r = fu.follow_up({"language": "en", "level": "beginner", "topic": "t"}, "Q", "I like my job")
    finally:
        config.demo_mode, fu.chat_json = orig_demo, orig_chat
    assert r == {"text": "Which part did you enjoy most?", "translation": "你最喜欢哪部分？"}


def test_evaluate_labels_followup():
    calls = {}
    orig_demo, orig_chat = config.demo_mode, ev.chat_json
    config.demo_mode = lambda: False
    ev.chat_json = lambda s, u, temperature=0.3: calls.setdefault("p", u) and {"scores": {}}
    try:
        r = ev.evaluate(CONTENT, [{"kind": "answer", "prompt": "Q1", "answer": "a b c", "input": "text"},
                                  {"kind": "answer", "prompt": "Why?", "answer": "because", "input": "text", "followUp": True}])
    finally:
        config.demo_mode, ev.chat_json = orig_demo, orig_chat
    assert "回答追问" in calls["p"] and r["items"][1]["followUp"] is True


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
