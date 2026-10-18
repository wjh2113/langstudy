"""Practice sessions: list / open / delete, autosave & resume, reuse, study notes, recordings, share links."""
import re
import secrets
import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from .. import config, db, jobs
from ..notes import generate_notes
from ..deps import MAX_AUDIO, bad, current_user, own_session
from ..schemas import JobRef, PreviousOut, ProgressReq, SessionOut, SessionSummary, ShareOut, StartedSession, TopicSummary

router = APIRouter(prefix="/api", tags=["sessions"])

AUDIO_DIR = config.DATA_DIR / "audio"
_AUDIO_NAME = re.compile(r"[A-Za-z0-9_-]{1,40}\.(webm|mp4|ogg)")
_MIME = {"webm": "audio/webm", "mp4": "audio/mp4", "ogg": "audio/ogg"}


def audio_dir(sid: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{12}", sid):
        bad("练习记录不存在", 404)
    return AUDIO_DIR / sid


def _audio_file(sid: str, name: str) -> FileResponse:
    if not _AUDIO_NAME.fullmatch(name):
        bad("录音不存在", 404)
    path = audio_dir(sid) / name
    if not path.is_file():
        bad("录音不存在或已过保留期", 404)
    return FileResponse(path, media_type=_MIME[name.rsplit(".", 1)[1]])


def _public(s: dict) -> dict:
    s = dict(s)
    s.pop("userId", None)
    return s


@router.get("/sessions", response_model=List[SessionSummary])
def api_sessions(all: bool = False, user: dict = Depends(current_user)):
    if all and user["role"] == "admin":
        return db.list_sessions(None)
    return db.list_sessions(user["id"])


@router.get("/topics", response_model=List[TopicSummary])
def api_topics(user: dict = Depends(current_user)):
    """Distinct practice topics for this user, newest touch first."""
    return db.list_topics(user["id"])


@router.delete("/topics")
def api_delete_topic(language: str, level: str, mode: str, topic: str, user: dict = Depends(current_user)):
    """Delete every practice under language + level + mode + topic for this user."""
    topic = (topic or "").strip()
    if not topic or not language or not level or not mode:
        bad("缺少话题、语言、级别或形式")
    ids = db.delete_sessions_by_topic(user["id"], language, level, mode, topic)
    for sid in ids:
        shutil.rmtree(audio_dir(sid), ignore_errors=True)
    return {"ok": True, "deleted": len(ids)}


@router.get("/sessions/previous", response_model=PreviousOut)
def api_previous(language: str, level: str, mode: str, topic: str, user: dict = Depends(current_user)):
    """Latest earlier session with the same language/level/mode/topic, so its material can be reused."""
    return {"previous": db.previous_session(user["id"], language, level, mode, topic.strip()[:200])}


@router.get("/sessions/{sid}", response_model=SessionOut)
def api_session(sid: str, user: dict = Depends(current_user)):
    return _public(own_session(sid, user))


@router.delete("/sessions/{sid}")
def api_delete_session(sid: str, user: dict = Depends(current_user)):
    own_session(sid, user)
    db.delete_session(sid)
    shutil.rmtree(audio_dir(sid), ignore_errors=True)
    return {"ok": True}


@router.put("/sessions/{sid}/progress")
def api_save_progress(sid: str, req: ProgressReq, user: dict = Depends(current_user)):
    """Autosave: called after every answer so a refresh or closed tab resumes where you were."""
    s = own_session(sid, user)
    if s["userId"] != user["id"]:
        bad("只能保存自己的练习", 403)
    try:
        saved_at = db.save_progress(sid, [t.model_dump() for t in req.turns], req.state)
    except ValueError as e:
        bad(e, 409)
    return {"savedAt": saved_at}


@router.post("/sessions/{sid}/repeat", response_model=StartedSession)
def api_repeat(sid: str, user: dict = Depends(current_user)):
    """Practise the same material again (no model call; study notes are copied too)."""
    old = own_session(sid, user)
    return {"id": db.repeat_session(sid, user["id"]), "content": old["content"]}


# ------------------------------------------------------------ study notes
@router.get("/notes")
def api_notes_list(user: dict = Depends(current_user)):
    return db.list_notes(user["id"])


@router.get("/sessions/{sid}/notes")
def api_get_notes(sid: str, user: dict = Depends(current_user)):
    own_session(sid, user)
    return db.get_notes(sid) or {"notes": None, "generatedAt": None}


@router.post("/sessions/{sid}/notes", response_model=JobRef)
def api_generate_notes(sid: str, user: dict = Depends(current_user)):
    """Generate (or regenerate, replacing the saved copy) the topic's study notes; poll /api/jobs/{jobId}."""
    session = own_session(sid, user)

    def work():
        notes = generate_notes(session["content"])
        return {"notes": notes, "generatedAt": db.save_notes(sid, notes)}

    return {"jobId": jobs.submit("notes", user, work, session_id=sid)}


@router.get("/progress/{language}")
def api_progress(language: str, user: dict = Depends(current_user)):
    return db.dimension_history(user["id"], language)


# ------------------------------------------------------------- recordings
@router.post("/sessions/{sid}/audio")
async def api_upload_audio(sid: str, key: str = Form(...), audio: UploadFile = File(...),
                           user: dict = Depends(current_user)):
    """Keep a recording with the session so it can be replayed (and re-assessed) later."""
    own_session(sid, user)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", key):
        bad("录音编号不合法")
    data = await audio.read()
    if not data or len(data) > MAX_AUDIO:
        bad("录音为空或太大")
    ctype = audio.content_type or ""
    ext = "mp4" if "mp4" in ctype else "ogg" if "ogg" in ctype else "webm"
    folder = audio_dir(sid)
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob(f"{key}.*"):  # re-recorded with another format
        old.unlink(missing_ok=True)
    (folder / f"{key}.{ext}").write_bytes(data)
    return {"url": f"/api/sessions/{sid}/audio/{key}.{ext}"}


@router.get("/sessions/{sid}/audio/{name}")
def api_get_audio(sid: str, name: str, user: dict = Depends(current_user)):
    own_session(sid, user)
    return _audio_file(sid, name)


# ----------------------------------------------------------- share links
@router.post("/sessions/{sid}/share", response_model=ShareOut)
def api_share(sid: str, user: dict = Depends(current_user)):
    """A read-only link to the report that works without logging in. Calling again keeps the same link."""
    s = own_session(sid, user)
    if not s["report"]:
        bad("评完分才能分享报告")
    token = s["shareToken"] or secrets.token_urlsafe(12)
    if not s["shareToken"]:
        db.set_share_token(sid, token)
    return {"token": token, "url": f"/share/{token}"}


@router.delete("/sessions/{sid}/share", response_model=ShareOut)
def api_unshare(sid: str, user: dict = Depends(current_user)):
    own_session(sid, user)
    db.set_share_token(sid, None)
    return {"token": None, "url": None}


def _shared(token: str) -> dict:
    s = db.session_by_share_token(token) if re.fullmatch(r"[A-Za-z0-9_-]{8,40}", token or "") else None
    if not s:
        bad("分享链接不存在或已关闭", 404)
    return s


@router.get("/share/{token}")
def api_shared_report(token: str):
    s = _shared(token)
    owner = db.get_user(s["userId"]) if s["userId"] else None
    return {"createdAt": s["createdAt"], "content": s["content"], "report": s["report"],
            "owner": owner["username"] if owner else ""}


@router.get("/share/{token}/audio/{name}")
def api_shared_audio(token: str, name: str):
    s = _shared(token)
    return _audio_file(s["id"], name)
