"""Study notes + accent tests (no network). Run: python tests/test_notes_accents.py"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["GATEWAY_API_KEY"] = ""  # never call the real gateway from tests
os.environ["LLM_API_KEY"] = ""

from app import config, db, languages, notes, tts  # noqa: E402

CONTENT = {"mode": "dialogue", "language": "en", "level": "beginner", "topic": "点餐", "title": "At a Café",
           "lines": [{"role": "A", "text": "What can I get you?"}, {"role": "B", "text": "A latte, please."}]}


def test_prompt_and_normalize():
    p = notes.build_prompt(CONTENT)
    assert "A: What can I get you?" in p and "8 个单词" in p and "音标" in p
    jp = notes.build_prompt({**CONTENT, "language": "ja", "level": "advanced"})
    assert "假名" in jp and "15 个单词" in jp
    n = notes.normalize({
        "summary": " s ", "vocabulary": [{"word": "latte", "meaning": "拿铁"}, {"meaning": "no word"}],
        "grammar": [{"point": "Could I", "examples": ["Could I have tea?", {"text": "x", "translation": "y"}]}],
        "patterns": [{"pattern": "Can I get + 名词", "examples": []}],
    })
    assert n["summary"] == "s" and len(n["vocabulary"]) == 1 and n["vocabulary"][0]["reading"] == ""
    assert n["grammar"][0]["examples"] == [{"text": "Could I have tea?", "translation": ""}, {"text": "x", "translation": "y"}]
    try:
        notes.normalize({"vocabulary": []})
        assert False
    except notes.LLMError:
        pass


def test_demo_notes_and_storage():
    config.DB_PATH = Path(tempfile.mkdtemp()) / "t.db"
    db.init()
    uid = db.create_admin("eric", "x")["id"]
    sid = db.create_session(CONTENT, uid)
    assert db.get_notes(sid) is None
    n = notes.generate_notes(CONTENT)
    assert n["vocabulary"] and n["grammar"] and n["patterns"]
    at = db.save_notes(sid, n)
    saved = db.get_notes(sid)
    assert saved["generatedAt"] == at and saved["notes"]["summary"] == n["summary"]
    listed = db.list_notes(uid)
    assert listed[0]["id"] == sid and listed[0]["counts"]["vocabulary"] == len(n["vocabulary"])
    assert db.list_sessions(uid)[0]["hasNotes"] is True
    db.save_notes(sid, {**n, "summary": "regenerated"})  # regenerate replaces
    assert db.get_notes(sid)["notes"]["summary"] == "regenerated"


def test_notes_with_fake_llm():
    orig_demo, orig_chat = config.demo_mode, notes.chat_json
    config.demo_mode = lambda: False
    notes.chat_json = lambda s, u, temperature=0.5, **kw: {"vocabulary": [{"word": "menu", "meaning": "菜单"}]}
    try:
        assert notes.generate_notes(CONTENT)["vocabulary"][0]["word"] == "menu"
    finally:
        config.demo_mode, notes.chat_json = orig_demo, orig_chat


def test_accent_table():
    pub = {l["code"]: l for l in languages.public_languages()}
    keys = [a["key"] for a in pub["en"]["accents"]]
    assert keys[0] == "default" and {"us", "gb", "in", "jp", "au"} <= set(keys)
    assert next(a for a in pub["en"]["accents"] if a["key"] == "jp")["simulated"] is True
    assert languages.get_accent("en", "in") == (["en-IN-NeerjaNeural", "en-IN-PrabhatNeural"], "en-IN")
    assert languages.get_accent("en", "nonsense")[0] is None  # unknown -> default
    assert languages.get_accent("ja", "tokyo")[0][0] == "ja-JP-NanamiNeural"


def test_synthesize_picks_voice_by_accent():
    config.TTS_CACHE_DIR = Path(tempfile.mkdtemp())
    used = []

    async def fake_edge(text, voice, rate):
        used.append(("edge", voice))
        return b"mp3"

    async def fake_gateway(text, voice, rate):
        used.append(("gateway", voice))
        return b"mp3"

    tts._edge, tts._gateway = fake_edge, fake_gateway
    orig = config.tts_uses_gateway
    config.tts_uses_gateway = lambda: True
    try:
        asyncio.run(tts.synthesize("Hello", "en", 1, 1.0, "in"))
        asyncio.run(tts.synthesize("Hello", "en", 0, 1.0, "default"))
        asyncio.run(tts.synthesize("Hello", "en", 1, 1.0, "in"))  # cached, no new call
    finally:
        config.tts_uses_gateway = orig
    assert used == [("edge", "en-IN-PrabhatNeural"), ("gateway", config.GATEWAY_TTS_VOICES[0])]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
