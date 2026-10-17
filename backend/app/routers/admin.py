"""/api/admin: invites, users, AI usage and answer statistics (administrator only)."""
from typing import Optional

from fastapi import APIRouter, Depends

from .. import ai, auth, db
from ..deps import admin_user, bad
from ..schemas import InviteReq, UserPatch

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


@router.get("/usage")
def api_usage(days: int = 30, _: dict = Depends(admin_user)):
    """AI calls, tokens and credits per user (today and the last `days` days)."""
    return ai.usage_summary(max(1, min(days, 365)))


@router.get("/stats/mistakes")
def api_mistake_stats(language: Optional[str] = None, _: dict = Depends(admin_user)):
    """Across all users: share of answers with problems and the most common correction notes."""
    return db.mistake_stats(language)
