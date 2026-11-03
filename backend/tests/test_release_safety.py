import asyncio
import io
import sqlite3
import threading
from starlette.datastructures import UploadFile
import pytest
from app import config, db, tts
from app.routers import admin


@pytest.fixture
def existing(tmp_path):
    config.DB_PATH = tmp_path / 'safety.db'
    db.init()
    user = db.create_admin('admin', 'hash')
    content = {'language': 'en', 'level': 'beginner', 'mode': 'questions',
               'topic': 'Interview', 'title': 'old', 'questions': [{'text': 'Hello?'}]}
    sid = db.create_session(content, user['id'])
    return user, content, sid


def test_replacement_rolls_back_on_insert_failure(existing):
    user, content, sid = existing
    with db._conn() as c:
        c.execute("CREATE TRIGGER fail_new BEFORE INSERT ON sessions BEGIN SELECT RAISE(ABORT, 'failed'); END")
    with pytest.raises(sqlite3.IntegrityError):
        db.replace_imported_session({**content, 'title': 'new'}, user['id'], None)
    assert db.get_session(sid)['content']['title'] == 'old'


def test_replacement_commits_notes_and_removes_old(existing):
    user, content, sid = existing
    notes = {'patterns': [], 'vocabulary': [{'word': 'hello'}]}
    new, removed = db.replace_imported_session({**content, 'title': 'new'}, user['id'], notes)
    assert removed == [sid] and db.get_session(sid) is None
    assert db.get_session(new)['content']['title'] == 'new'
    assert db.get_notes(new)['notes']['vocabulary'] == notes['vocabulary']


def test_import_completion_failure_preserves_old_and_audio(existing, monkeypatch):
    user, content, sid = existing
    monkeypatch.setattr(admin, 'read_upload', lambda *a: ['text'])
    monkeypatch.setattr(admin, 'parse_documents', lambda *a: ([{'content': content, 'notes': None}], []))
    def fail(*a):
        raise RuntimeError('completion failed')
    monkeypatch.setattr(admin, 'complete_imported', fail)
    cleared = []
    monkeypatch.setattr(admin, '_clear_session_audio', cleared.append)
    with pytest.raises(RuntimeError, match='completion failed'):
        asyncio.run(admin.api_import(UploadFile(io.BytesIO(b'text'), filename='a.md'), user))
    assert db.get_session(sid) is not None
    assert cleared == []


def test_audio_warmup_does_not_block_caller(monkeypatch):
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    monkeypatch.setattr(config, 'demo_mode', lambda: False)
    monkeypatch.setattr(config, 'TTS_ENABLED', True)
    async def slow(content):
        entered.set()
        await asyncio.to_thread(release.wait, 3)
        done.set()
    monkeypatch.setattr(tts, 'warm_default_audio', slow)
    try:
        assert tts.schedule_audio_warm({'language': 'en'})
        assert entered.wait(2)
        assert not done.is_set()
    finally:
        release.set()
        assert done.wait(2)


def test_synthesis_shared_between_event_loops(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(config, 'TTS_CACHE_DIR', tmp_path)
    monkeypatch.setattr(config, 'TTS_ENABLED', True)
    monkeypatch.setattr(config, 'tts_uses_gateway', lambda: False)
    calls = []
    entered, release = threading.Event(), threading.Event()
    async def edge(*args):
        calls.append(args)
        entered.set()
        await asyncio.to_thread(release.wait, 2)
        return b'fake-mp3'
    monkeypatch.setattr(tts, '_edge', edge)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(asyncio.run, tts.synthesize('A shared sentence.', 'en'))
        assert entered.wait(1)
        b = pool.submit(asyncio.run, tts.synthesize('A shared sentence.', 'en'))
        release.set()
        assert a.result(timeout=3) == b.result(timeout=3) == b'fake-mp3'
    assert len(calls) == 1
