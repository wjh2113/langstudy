"""SQLite storage: users, login tokens, invite codes, practice sessions and reports."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta

from . import config


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _conn():
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def _immediate():
    """Write transaction that takes the lock before any check, so two requests can't both pass it."""
    conn = sqlite3.connect(config.DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def init():
    boot = sqlite3.connect(config.DB_PATH, timeout=10, isolation_level=None)
    boot.execute("PRAGMA journal_mode=WAL")
    boot.close()
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',          -- admin | user
                disabled INTEGER NOT NULL DEFAULT 0,
                invited_by INTEGER,
                invite_code TEXT,
                created_at TEXT NOT NULL,
                last_login_at TEXT
            );
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS invites (
                code TEXT PRIMARY KEY,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                max_uses INTEGER NOT NULL DEFAULT 1,
                uses INTEGER NOT NULL DEFAULT 0,
                note TEXT,
                revoked INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                language TEXT, level TEXT, mode TEXT, topic TEXT, title TEXT,
                content TEXT NOT NULL,
                turns TEXT,
                report TEXT,
                overall INTEGER
            );
            """
        )
        cols = {r["name"] for r in c.execute("PRAGMA table_info(sessions)")}
        if "user_id" not in cols:  # upgrade from the single-user version
            c.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER")


# ------------------------------------------------------------------ users
def _user(row):
    if not row:
        return None
    return {
        "id": row["id"], "username": row["username"], "role": row["role"],
        "disabled": bool(row["disabled"]), "createdAt": row["created_at"], "lastLoginAt": row["last_login_at"],
    }


def count_users() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def create_admin(username: str, password_hash: str) -> dict:
    """First account. Claims practice records made before accounts existed."""
    with _immediate() as c:
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            raise ValueError("管理员已经创建过了，请直接登录")
        cur = c.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
            (username, password_hash, _now()),
        )
        c.execute("UPDATE sessions SET user_id=? WHERE user_id IS NULL", (cur.lastrowid,))
        return _user(c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone())


def register_with_invite(username: str, password_hash: str, code: str) -> dict:
    """Create a user and consume one use of the invite in one locked transaction."""
    with _immediate() as c:
        inv = c.execute("SELECT * FROM invites WHERE code=?", (code,)).fetchone()
        problem = invite_problem(inv)
        if problem:
            raise ValueError(problem)
        if c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            raise ValueError("这个用户名已经被注册了")
        now = _now()
        spent = c.execute(
            """UPDATE invites SET uses = uses + 1
               WHERE code=? AND revoked=0 AND uses < max_uses
                 AND (expires_at IS NULL OR expires_at >= ?)""",
            (code, now),
        )
        if spent.rowcount != 1:
            inv = c.execute("SELECT * FROM invites WHERE code=?", (code,)).fetchone()
            raise ValueError(invite_problem(inv) or "这个邀请码已经用完了")
        cur = c.execute(
            "INSERT INTO users (username, password_hash, role, invited_by, invite_code, created_at) VALUES (?, ?, 'user', ?, ?, ?)",
            (username, password_hash, inv["created_by"], code, now),
        )
        return _user(c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone())


def get_user(user_id: int):
    with _conn() as c:
        return _user(c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())


def get_login(username: str):
    """User row including the password hash, for login."""
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        return None
    return {**_user(row), "passwordHash": row["password_hash"]}


def touch_login(user_id: int):
    with _conn() as c:
        c.execute("UPDATE users SET last_login_at=? WHERE id=?", (_now(), user_id))


def set_password(user_id: int, password_hash: str):
    with _conn() as c:
        c.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, user_id))
        c.execute("DELETE FROM auth_tokens WHERE user_id=?", (user_id,))


def set_disabled(user_id: int, disabled: bool):
    with _conn() as c:
        c.execute("UPDATE users SET disabled=? WHERE id=?", (int(disabled), user_id))
        if disabled:
            c.execute("DELETE FROM auth_tokens WHERE user_id=?", (user_id,))


def list_users():
    with _conn() as c:
        rows = c.execute(
            """SELECT u.*, inv.username AS inviter,
                      (SELECT COUNT(*) FROM sessions s WHERE s.user_id=u.id) AS practice_count,
                      (SELECT MAX(created_at) FROM sessions s WHERE s.user_id=u.id) AS last_practice_at
               FROM users u LEFT JOIN users inv ON inv.id=u.invited_by
               ORDER BY u.id"""
        ).fetchall()
    return [
        {**_user(r), "invitedBy": r["inviter"], "inviteCode": r["invite_code"],
         "practiceCount": r["practice_count"], "lastPracticeAt": r["last_practice_at"]}
        for r in rows
    ]


# ----------------------------------------------------------------- tokens
def save_token(token_hash: str, user_id: int, days: int):
    expires = (datetime.now() + timedelta(days=days)).isoformat(timespec="seconds")
    with _conn() as c:
        c.execute("DELETE FROM auth_tokens WHERE expires_at < ?", (_now(),))
        c.execute("INSERT INTO auth_tokens VALUES (?, ?, ?, ?)", (token_hash, user_id, _now(), expires))


def user_for_token(token_hash: str):
    with _conn() as c:
        row = c.execute(
            "SELECT u.* FROM auth_tokens t JOIN users u ON u.id=t.user_id WHERE t.token_hash=? AND t.expires_at > ?",
            (token_hash, _now()),
        ).fetchone()
    user = _user(row)
    return None if not user or user["disabled"] else user


def delete_token(token_hash: str):
    with _conn() as c:
        c.execute("DELETE FROM auth_tokens WHERE token_hash=?", (token_hash,))


# ---------------------------------------------------------------- invites
def invite_problem(inv) -> str:
    """Why an invite can't be used, or '' if it can."""
    if not inv:
        return "邀请码不存在，请检查是否输错"
    if inv["revoked"]:
        return "这个邀请码已被作废"
    if inv["expires_at"] and inv["expires_at"] < _now():
        return "这个邀请码已过期"
    if inv["uses"] >= inv["max_uses"]:
        return "这个邀请码已经用完了"
    return ""


def create_invite(code: str, created_by: int, max_uses: int, expires_days, note: str) -> dict:
    expires = (datetime.now() + timedelta(days=expires_days)).isoformat(timespec="seconds") if expires_days else None
    with _conn() as c:
        c.execute(
            "INSERT INTO invites (code, created_by, created_at, expires_at, max_uses, note) VALUES (?, ?, ?, ?, ?, ?)",
            (code, created_by, _now(), expires, max_uses, note),
        )
    return next(i for i in list_invites() if i["code"] == code)


def check_invite(code: str) -> str:
    with _conn() as c:
        return invite_problem(c.execute("SELECT * FROM invites WHERE code=?", (code,)).fetchone())


def list_invites():
    with _conn() as c:
        rows = c.execute(
            """SELECT i.*, (SELECT GROUP_CONCAT(username, '、') FROM users WHERE invite_code=i.code) AS used_by
               FROM invites i ORDER BY i.created_at DESC"""
        ).fetchall()
    out = []
    for r in rows:
        problem = invite_problem(r)
        status = "active" if not problem else "revoked" if r["revoked"] else "expired" if "过期" in problem else "used"
        out.append({
            "code": r["code"], "createdAt": r["created_at"], "expiresAt": r["expires_at"], "maxUses": r["max_uses"],
            "uses": r["uses"], "note": r["note"] or "", "status": status, "usedBy": r["used_by"] or "",
        })
    return out


def revoke_invite(code: str):
    with _conn() as c:
        c.execute("UPDATE invites SET revoked=1 WHERE code=?", (code,))


# --------------------------------------------------------------- sessions
def create_session(content: dict, user_id: int) -> str:
    sid = uuid.uuid4().hex[:12]
    with _conn() as c:
        c.execute(
            "INSERT INTO sessions (id, created_at, language, level, mode, topic, title, content, user_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (sid, _now(), content.get("language"), content.get("level"), content.get("mode"),
             content.get("topic"), content.get("title"), json.dumps(content, ensure_ascii=False), user_id),
        )
    return sid


def save_report(sid: str, turns: list, report: dict):
    with _conn() as c:
        c.execute(
            "UPDATE sessions SET turns=?, report=?, overall=? WHERE id=?",
            (json.dumps(turns, ensure_ascii=False), json.dumps(report, ensure_ascii=False), report.get("overall"), sid),
        )


def get_session(sid: str):
    with _conn() as c:
        row = c.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "userId": row["user_id"],
        "createdAt": row["created_at"],
        "content": json.loads(row["content"]),
        "turns": json.loads(row["turns"]) if row["turns"] else [],
        "report": json.loads(row["report"]) if row["report"] else None,
    }


def list_sessions(user_id=None, limit: int = 200):
    """One user's sessions, or everyone's when user_id is None (admin view)."""
    where, args = ("WHERE s.user_id=?", (user_id,)) if user_id is not None else ("", ())
    with _conn() as c:
        rows = c.execute(
            f"""SELECT s.id, s.created_at, s.language, s.level, s.mode, s.topic, s.title, s.overall,
                       s.report IS NOT NULL AS done, u.username
                FROM sessions s LEFT JOIN users u ON u.id=s.user_id {where}
                ORDER BY s.created_at DESC LIMIT ?""",
            (*args, limit),
        ).fetchall()
    return [
        {**{k: r[k] for k in ("id", "language", "level", "mode", "topic", "title", "overall", "username")},
         "createdAt": r["created_at"], "done": bool(r["done"])}
        for r in rows
    ]


def dimension_history(user_id: int, language: str, limit: int = 20):
    """Per-dimension scores of a user's recent finished sessions, oldest first (for trends)."""
    with _conn() as c:
        rows = c.execute(
            "SELECT created_at, report FROM sessions WHERE user_id=? AND language=? AND report IS NOT NULL "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, language, limit),
        ).fetchall()
    out = []
    for r in reversed(rows):
        rep = json.loads(r["report"])
        out.append({"createdAt": r["created_at"], "overall": rep.get("overall"),
                    "dims": {d["key"]: d["score"] for d in rep.get("dimensions", [])}})
    return out


def delete_session(sid: str):
    with _conn() as c:
        c.execute("DELETE FROM sessions WHERE id=?", (sid,))
