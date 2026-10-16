"""LangStudy API. Run: uvicorn app.main:app --reload --port 8000"""
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth, config, db
from .evaluate import evaluate
from .followup import follow_up
from .generate import generate
from .languages import public_languages
from .llm import LLMError
from .stt import STTError, transcribe
from .tts import TTSError, synthesize

app = FastAPI(title="LangStudy")
db.init()

MAX_AUDIO = 25 * 1024 * 1024


def _bad(e, code: int = 400):
    raise HTTPException(status_code=code, detail=str(e))


# ------------------------------------------------------------------ auth
def _token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get(auth.COOKIE, "")


def current_user(request: Request) -> dict:
    user = auth.user_for_token(_token(request))
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def admin_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以这样做")
    return user


def _cookie_secure(request: Request) -> bool:
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme).split(",")[0].strip().lower()
    return proto == "https"


def _login_response(response: Response, user: dict, request: Request) -> dict:
    token = auth.issue_token(user["id"])
    response.set_cookie(
        auth.COOKIE, token, max_age=auth.TOKEN_DAYS * 86400, httponly=True, samesite="lax", path="/",
        secure=_cookie_secure(request),
    )
    return {"user": user}


def _own_session(sid: str, user: dict) -> dict:
    s = db.get_session(sid)
    if not s or (s["userId"] != user["id"] and user["role"] != "admin"):
        _bad("练习记录不存在", 404)
    return s


class Credentials(BaseModel):
    username: str
    password: str


class RegisterReq(Credentials):
    inviteCode: str


class PasswordReq(BaseModel):
    oldPassword: str
    newPassword: str


@app.get("/api/auth/me")
def api_me(request: Request):
    return {"user": auth.user_for_token(_token(request)), "setupRequired": db.count_users() == 0}


@app.post("/api/auth/setup")
def api_setup(req: Credentials, request: Request, response: Response):
    """Create the first account, which becomes the administrator."""
    try:
        username = auth.check_credentials(req.username, req.password)
        user = db.create_admin(username, auth.hash_password(req.password))
    except auth.AuthError as e:
        _bad(e)
    except ValueError as e:
        _bad(e, 409)
    return _login_response(response, user, request)


@app.post("/api/auth/login")
def api_login(req: Credentials, request: Request, response: Response):
    try:
        user = auth.login(req.username, req.password)
    except auth.AuthError as e:
        _bad(e, 401)
    return _login_response(response, user, request)


@app.get("/api/auth/invite/{code}")
def api_check_invite(code: str):
    problem = db.check_invite(auth.normalize_code(code))
    return {"valid": not problem, "message": problem}


@app.post("/api/auth/register")
def api_register(req: RegisterReq, request: Request, response: Response):
    try:
        username = auth.check_credentials(req.username, req.password)
        user = db.register_with_invite(username, auth.hash_password(req.password), auth.normalize_code(req.inviteCode))
    except auth.AuthError as e:
        _bad(e)
    except ValueError as e:
        _bad(e)
    return _login_response(response, user, request)


@app.post("/api/auth/logout")
def api_logout(request: Request, response: Response):
    auth.revoke_token(_token(request))
    response.delete_cookie(auth.COOKIE, path="/", samesite="lax", secure=_cookie_secure(request))
    return {"ok": True}


@app.post("/api/auth/password")
def api_change_password(req: PasswordReq, user: dict = Depends(current_user)):
    try:
        auth.login(user["username"], req.oldPassword)
    except auth.AuthError:
        _bad("原密码不对")
    if len(req.newPassword) < 8:
        _bad("新密码至少 8 位")
    db.set_password(user["id"], auth.hash_password(req.newPassword))
    return {"ok": True}


# ----------------------------------------------------------------- admin
class InviteReq(BaseModel):
    maxUses: int = 1
    expiresDays: Optional[int] = 7
    note: str = ""


class UserPatch(BaseModel):
    disabled: Optional[bool] = None


@app.get("/api/admin/invites")
def api_invites(_: dict = Depends(admin_user)):
    return db.list_invites()


@app.post("/api/admin/invites")
def api_create_invite(req: InviteReq, admin: dict = Depends(admin_user)):
    max_uses = max(1, min(req.maxUses, 100))
    days = max(1, min(req.expiresDays, 365)) if req.expiresDays else None
    return db.create_invite(auth.new_invite_code(), admin["id"], max_uses, days, req.note.strip()[:100])


@app.delete("/api/admin/invites/{code}")
def api_revoke_invite(code: str, _: dict = Depends(admin_user)):
    db.revoke_invite(code)
    return {"ok": True}


@app.get("/api/admin/users")
def api_users(_: dict = Depends(admin_user)):
    return db.list_users()


@app.patch("/api/admin/users/{user_id}")
def api_patch_user(user_id: int, req: UserPatch, admin: dict = Depends(admin_user)):
    if user_id == admin["id"]:
        _bad("不能停用你自己的管理员账号")
    if not db.get_user(user_id):
        _bad("用户不存在", 404)
    if req.disabled is not None:
        db.set_disabled(user_id, req.disabled)
    return db.get_user(user_id)


@app.post("/api/admin/users/{user_id}/reset-password")
def api_reset_password(user_id: int, admin: dict = Depends(admin_user)):
    if not db.get_user(user_id):
        _bad("用户不存在", 404)
    password = auth.temp_password()
    db.set_password(user_id, auth.hash_password(password))
    return {"password": password}


# -------------------------------------------------------------- practice
class GenerateReq(BaseModel):
    language: str = "en"
    level: str = "intermediate"
    mode: str = "questions"
    topic: str
    count: int = 5


class TTSReq(BaseModel):
    text: str
    language: str = "en"
    voiceIndex: int = 0
    rate: float = 1.0


class Turn(BaseModel):
    kind: str = "answer"  # shadow | answer | line
    prompt: str = ""
    reference: str = ""
    freeResponse: bool = False
    answer: str = ""
    input: str = "text"  # voice | text
    durationSec: float = 0
    confidence: Optional[float] = None
    plays: int = 0
    textHidden: bool = False
    followUp: bool = False  # answer to an AI follow-up question
    pronScore: Optional[float] = None  # gateway pronunciation score (reading a script)
    pronNote: str = ""
    pronIssues: List[dict] = Field(default_factory=list)


class QA(BaseModel):
    q: str = ""
    a: str = ""


class FollowUpReq(BaseModel):
    sessionId: str
    question: str
    answer: str
    history: List[QA] = Field(default_factory=list)


class EvaluateReq(BaseModel):
    sessionId: str
    turns: List[Turn] = Field(default_factory=list)


@app.get("/api/config")
def get_config(_: dict = Depends(current_user)):
    return {
        "languages": public_languages(),
        "demoMode": config.demo_mode(),
        "model": None if config.demo_mode() else config.model_label(),
        "sttServer": config.stt_server_enabled(),
        "ttsServer": config.TTS_ENABLED,
        "pronounceServer": config.gateway_enabled(),
    }


@app.post("/api/generate")
def api_generate(req: GenerateReq, user: dict = Depends(current_user)):
    try:
        content = generate(req.language, req.level, req.mode, req.topic, req.count)
    except ValueError as e:
        _bad(e)
    except LLMError as e:
        _bad(e, 502)
    return {"id": db.create_session(content, user["id"]), "content": content}


@app.post("/api/followup")
def api_followup(req: FollowUpReq, user: dict = Depends(current_user)):
    session = _own_session(req.sessionId, user)
    try:
        return follow_up(session["content"], req.question, req.answer, [h.model_dump() for h in req.history])
    except ValueError as e:
        _bad(e)
    except LLMError as e:
        _bad(e, 502)


@app.post("/api/tts")
async def api_tts(req: TTSReq, _: dict = Depends(current_user)):
    try:
        audio = await synthesize(req.text, req.language, req.voiceIndex, req.rate)
    except (ValueError, TTSError) as e:
        _bad(e, 502)
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"})


@app.post("/api/stt")
async def api_stt(audio: UploadFile = File(...), language: str = Form("en"), _: dict = Depends(current_user)):
    data = await audio.read()
    if len(data) > MAX_AUDIO:
        _bad("录音太长了，请分段作答")
    try:
        text = transcribe(data, audio.filename or "speech.webm", language, audio.content_type or "")
    except STTError as e:
        _bad(e, 502)
    return {"text": text}


@app.post("/api/pronounce")
async def api_pronounce(audio: UploadFile = File(...), text: str = Form(...), language: str = Form("en"),
                        _: dict = Depends(current_user)):
    """Score a recording against the script the learner was reading (gateway `pronunciation`)."""
    if not config.gateway_enabled():
        _bad("未配置网关，发音评测不可用", 404)
    data = await audio.read()
    if len(data) > MAX_AUDIO:
        _bad("录音太长了")
    if not text.strip() or len(text) > 8000:
        _bad("参考文本为空或太长")
    from .gateway import GatewayError, pronounce

    try:
        return pronounce(data, audio.filename or "speech.webm", audio.content_type or "", text.strip(), language)
    except GatewayError as e:
        _bad(e, 502)


@app.post("/api/evaluate")
def api_evaluate(req: EvaluateReq, user: dict = Depends(current_user)):
    session = _own_session(req.sessionId, user)
    turns = [t.model_dump() for t in req.turns]
    try:
        report = evaluate(session["content"], turns)
    except ValueError as e:
        _bad(e)
    except LLMError as e:
        _bad(e, 502)
    db.save_report(req.sessionId, turns, report)
    return report


@app.get("/api/sessions")
def api_sessions(all: bool = False, user: dict = Depends(current_user)):
    if all and user["role"] == "admin":
        return db.list_sessions(None)
    return db.list_sessions(user["id"])


@app.get("/api/sessions/{sid}")
def api_session(sid: str, user: dict = Depends(current_user)):
    s = _own_session(sid, user)
    s.pop("userId", None)
    return s


@app.delete("/api/sessions/{sid}")
def api_delete_session(sid: str, user: dict = Depends(current_user)):
    _own_session(sid, user)
    db.delete_session(sid)
    return {"ok": True}


@app.get("/api/progress/{language}")
def api_progress(language: str, user: dict = Depends(current_user)):
    return db.dimension_history(user["id"], language)


@app.get("/api/health")
def api_health():
    return {"ok": True}


# Serve the built frontend (frontend/dist) when present, so one process is enough.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def frontend_file(path: str) -> Path:
    """A file inside the built frontend, or index.html. Never resolves outside DIST."""
    root = DIST.resolve()
    rel = (path or "").replace("\\", "/").lstrip("/")
    candidate = (root / rel).resolve() if rel else root / "index.html"
    try:
        candidate.relative_to(root)
    except ValueError:
        candidate = root / "index.html"
    if rel and candidate.is_file():
        return candidate
    return root / "index.html"


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="接口不存在")
        return FileResponse(frontend_file(path))
