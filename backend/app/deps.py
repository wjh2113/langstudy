"""Shared request helpers: errors, current user, ownership checks, client IP."""
from fastapi import Depends, HTTPException, Request, Response

from . import auth, config, db
from .ratelimit import Locked

MAX_AUDIO = 25 * 1024 * 1024


def bad(e, code: int = 400, headers: dict | None = None):
    raise HTTPException(status_code=code, detail=str(e), headers=headers)


def locked(e: Locked):
    bad(e, 429, {"Retry-After": str(e.retry_after)})


def client_ip(request: Request) -> str:
    if config.TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


def request_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get(auth.COOKIE, "")


def current_user(request: Request) -> dict:
    user = auth.user_for_token(request_token(request))
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def admin_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以这样做")
    return user


def cookie_secure(request: Request) -> bool:
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme).split(",")[0].strip().lower()
    return proto == "https"


def login_response(response: Response, user: dict, request: Request) -> dict:
    token = auth.issue_token(user["id"])
    response.set_cookie(
        auth.COOKIE, token, max_age=auth.TOKEN_DAYS * 86400, httponly=True, samesite="lax", path="/",
        secure=cookie_secure(request),
    )
    return {"user": user}


def own_session(sid: str, user: dict) -> dict:
    s = db.get_session(sid)
    if not s or (s["userId"] != user["id"] and user["role"] != "admin"):
        bad("练习记录不存在", 404)
    return s
