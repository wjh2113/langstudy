"""/api/auth: first-run setup, login, invite registration, logout, password change."""
from fastapi import APIRouter, Depends, Request, Response

from .. import auth, db, ratelimit
from ..deps import bad, client_ip, cookie_secure, current_user, locked, login_response, request_token
from ..schemas import Credentials, LoginOut, MeOut, PasswordReq, RegisterReq

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=MeOut)
def api_me(request: Request):
    return {"user": auth.user_for_token(request_token(request)), "setupRequired": db.count_users() == 0}


@router.post("/setup", response_model=LoginOut)
def api_setup(req: Credentials, request: Request, response: Response):
    """Create the first account, which becomes the administrator."""
    if db.count_users() > 0:
        bad("管理员已经创建过了，请直接登录", 409)
    try:
        username = auth.check_credentials(req.username, req.password)
    except auth.AuthError as e:
        bad(e)
    try:
        admin = db.create_admin(username, auth.hash_password(req.password))
    except ValueError as e:  # someone else finished setup a moment earlier
        bad(e, 409)
    return login_response(response, admin, request)


@router.post("/login", response_model=LoginOut)
def api_login(req: Credentials, request: Request, response: Response):
    ip, account = client_ip(request), req.username.strip()
    try:
        ratelimit.check(ip=ip, account=account)
    except ratelimit.Locked as e:
        locked(e)
    try:
        user = auth.login(req.username, req.password)
    except auth.AuthError as e:
        ratelimit.fail(ip=ip, account=account)
        bad(e, 401)
    ratelimit.clear(account=account)
    return login_response(response, user, request)


@router.get("/invite/{code}")
def api_check_invite(code: str, request: Request):
    ip = client_ip(request)
    try:
        ratelimit.check(invite=ip)
    except ratelimit.Locked as e:
        locked(e)
    problem = db.check_invite(auth.normalize_code(code))
    if problem:
        ratelimit.fail(invite=ip)
    return {"valid": not problem, "message": problem}


@router.post("/register", response_model=LoginOut)
def api_register(req: RegisterReq, request: Request, response: Response):
    ip = client_ip(request)
    try:
        ratelimit.check(ip=ip, invite=ip)
    except ratelimit.Locked as e:
        locked(e)
    try:
        username = auth.check_credentials(req.username, req.password)
    except auth.AuthError as e:
        bad(e)
    code = auth.normalize_code(req.inviteCode)
    try:
        user = db.register_with_invite(username, auth.hash_password(req.password), code)
    except ValueError as e:
        if db.check_invite(code):  # a bad invite code counts as a guess; a taken username does not
            ratelimit.fail(ip=ip, invite=ip)
        bad(e)
    return login_response(response, user, request)


@router.post("/logout")
def api_logout(request: Request, response: Response):
    auth.revoke_token(request_token(request))
    response.delete_cookie(auth.COOKIE, path="/", samesite="lax", secure=cookie_secure(request))
    return {"ok": True}


@router.post("/password")
def api_change_password(req: PasswordReq, request: Request, user: dict = Depends(current_user)):
    ip = client_ip(request)
    try:
        ratelimit.check(ip=ip, account=user["username"])
    except ratelimit.Locked as e:
        locked(e)
    try:
        auth.login(user["username"], req.oldPassword)
    except auth.AuthError:
        ratelimit.fail(ip=ip, account=user["username"])
        bad("原密码不对")
    if len(req.newPassword) < 8:
        bad("新密码至少 8 位")
    db.set_password(user["id"], auth.hash_password(req.newPassword))
    return {"ok": True}
