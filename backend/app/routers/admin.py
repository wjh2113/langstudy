"""/api/admin: invites, users, AI usage and answer statistics (administrator only)."""
import re
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile

from .. import ai, auth, config, db
from ..deps import admin_user, bad
from ..import_pack import PROMPT, parse_documents, read_upload
from ..llm import LLMError
from ..schemas import InviteReq, UserPatch


def _clear_session_audio(sid: str) -> None:
    if re.fullmatch(r"[0-9a-f]{12}", sid or ""):
        shutil.rmtree(config.DATA_DIR / "audio" / sid, ignore_errors=True)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/invites")
def api_invites(_: dict = Depends(admin_user)):
    return db.list_invites()


@router.post("/invites")
def api_create_invite(req: InviteReq, admin: dict = Depends(admin_user)):
    max_uses = max(1, min(req.maxUses, 100))
    days = max(1, min(req.expiresDays, 365)) if req.expiresDays else None
    return db.create_invite(auth.new_invite_code(), admin["id"], max_uses, days, req.note.strip()[:100])


@router.delete("/invites/{code}")
def api_revoke_invite(code: str, _: dict = Depends(admin_user)):
    db.revoke_invite(code)
    return {"ok": True}


@router.get("/users")
def api_users(_: dict = Depends(admin_user)):
    return db.list_users()


@router.patch("/users/{user_id}")
def api_patch_user(user_id: int, req: UserPatch, admin: dict = Depends(admin_user)):
    if user_id == admin["id"]:
        bad("不能停用你自己的管理员账号")
    if not db.get_user(user_id):
        bad("用户不存在", 404)
    if req.disabled is not None:
        db.set_disabled(user_id, req.disabled)
    return db.get_user(user_id)


@router.post("/users/{user_id}/reset-password")
def api_reset_password(user_id: int, admin: dict = Depends(admin_user)):
    if not db.get_user(user_id):
        bad("用户不存在", 404)
    password = auth.temp_password()
    db.set_password(user_id, auth.hash_password(password))
    return {"password": password}


@router.get("/import-prompt")
def api_import_prompt(_: dict = Depends(admin_user)):
    """The instructions an administrator pastes into another model."""
    return {"prompt": PROMPT}


@router.post("/import")
async def api_import(file: UploadFile = File(...), admin: dict = Depends(admin_user)):
    """Turn a Markdown file or a zip of them into practice sessions on this admin account."""
    data = await file.read()
    try:
        texts = read_upload(file.filename or "", data)
        ready, errors = parse_documents(texts)
    except (LLMError, UnicodeError) as e:
        bad(str(e) if str(e) else "文件不是 UTF-8 文本")
    if not ready:
        bad("；".join(errors) or "没有可以导入的话题")
    imported = []
    replaced = 0
    for item in ready:
        content = item["content"]
        # Same language + topic + level + mode → replace earlier imports/practices.
        old_ids = db.delete_sessions_by_topic(
            admin["id"], content["language"], content["level"], content["mode"], content["topic"],
        )
        for oid in old_ids:
            _clear_session_audio(oid)
        replaced += len(old_ids)
        sid = db.create_session(content, admin["id"])
        if item["notes"]:
            db.save_notes(sid, item["notes"])
        imported.append({
            "id": sid, "topic": content["topic"], "mode": content["mode"],
            "title": content["title"], "hasNotes": bool(item["notes"]),
            "replaced": len(old_ids),
        })
    return {"imported": imported, "replaced": replaced, "errors": errors}


@router.get("/usage")
def api_usage(days: int = 30, _: dict = Depends(admin_user)):
    """AI calls, tokens and credits per user (today and the last `days` days)."""
    return ai.usage_summary(max(1, min(days, 365)))


@router.get("/stats/mistakes")
def api_mistake_stats(language: Optional[str] = None, _: dict = Depends(admin_user)):
    """Across all users: share of answers with problems and the most common correction notes."""
    return db.mistake_stats(language)
