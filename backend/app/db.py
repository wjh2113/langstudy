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
    return conn


@contextmanager
def _exclusive():
    """A write transaction that takes the database lock up front, so a check
    (e.g. "no admin yet", "invite has uses left") and the write that depends on it
    can't interleave with another request doing the same."""
    conn = _conn()
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
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
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                language TEXT NOT NULL,
                kind TEXT NOT NULL,                -- word | pattern | sentence
                front TEXT NOT NULL,               -- what to say / recognise (target language)
                reading TEXT, meaning TEXT, example TEXT, example_translation TEXT,
                extra TEXT,                        -- sentence cards: what the learner originally said
                source_session TEXT,
                created_at TEXT NOT NULL,
                due_at TEXT NOT NULL,
                interval_days REAL NOT NULL DEFAULT 0,
                ease REAL NOT NULL DEFAULT 2.5,
                reps INTEGER NOT NULL DEFAULT 0,
                lapses INTEGER NOT NULL DEFAULT 0,
                last_reviewed_at TEXT,
                UNIQUE (user_id, language, kind, front)
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
        if "notes" not in cols:  # study notes (vocabulary / grammar / patterns)
            c.execute("ALTER TABLE sessions ADD COLUMN notes TEXT")
            c.execute("ALTER TABLE sessions ADD COLUMN notes_at TEXT")


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
    with _exclusive() as c:
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            raise ValueError("管理员已经创建过了，请直接登录")
        cur = c.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
            (username, password_hash, _now()),
        )
        c.execute("UPDATE sessions SET user_id=? WHERE user_id IS NULL", (cur.lastrowid,))
        return _user(c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone())


def register_with_invite(username: str, password_hash: str, code: str) -> dict:
    """Create a user and consume one use of the invite in one transaction."""
    with _exclusive() as c:
        inv = c.execute("SELECT * FROM invites WHERE code=?", (code,)).fetchone()
        problem = invite_problem(inv)
        if problem:
            raise ValueError(problem)
        if c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            raise ValueError("这个用户名已经被注册了")
        cur = c.execute(
            "INSERT INTO users (username, password_hash, role, invited_by, invite_code, created_at) VALUES (?, ?, 'user', ?, ?, ?)",
            (username, password_hash, inv["created_by"], code, _now()),
        )
        c.execute("UPDATE invites SET uses = uses + 1 WHERE code=?", (code,))
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
                       s.report IS NOT NULL AS done, s.notes IS NOT NULL AS has_notes, u.username
                FROM sessions s LEFT JOIN users u ON u.id=s.user_id {where}
                ORDER BY s.created_at DESC LIMIT ?""",
            (*args, limit),
        ).fetchall()
    return [
        {**{k: r[k] for k in ("id", "language", "level", "mode", "topic", "title", "overall", "username")},
         "createdAt": r["created_at"], "done": bool(r["done"]), "hasNotes": bool(r["has_notes"])}
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


def save_notes(sid: str, notes: dict) -> str:
    at = _now()
    with _conn() as c:
        c.execute("UPDATE sessions SET notes=?, notes_at=? WHERE id=?", (json.dumps(notes, ensure_ascii=False), at, sid))
    return at


def get_notes(sid: str):
    with _conn() as c:
        row = c.execute("SELECT notes, notes_at FROM sessions WHERE id=?", (sid,)).fetchone()
    if not row or not row["notes"]:
        return None
    return {"notes": json.loads(row["notes"]), "generatedAt": row["notes_at"]}


def list_notes(user_id: int):
    """A user's sessions that have saved study notes, newest notes first."""
    with _conn() as c:
        rows = c.execute(
            "SELECT id, language, level, mode, topic, title, notes, notes_at, report IS NOT NULL AS done "
            "FROM sessions WHERE user_id=? AND notes IS NOT NULL ORDER BY notes_at DESC",
            (user_id,),
        ).fetchall()
    out = []
    for r in rows:
        n = json.loads(r["notes"])
        out.append({
            "id": r["id"], "language": r["language"], "level": r["level"], "mode": r["mode"], "topic": r["topic"],
            "title": r["title"], "generatedAt": r["notes_at"], "done": bool(r["done"]), "summary": n.get("summary", ""),
            "counts": {k: len(n.get(k, [])) for k in ("vocabulary", "grammar", "patterns")},
        })
    return out


def recent_results(user_id: int, language: str, limit: int = 10):
    """Newest-first finished sessions for coaching: level, overall and per-dimension scores."""
    with _conn() as c:
        rows = c.execute(
            "SELECT level, report FROM sessions WHERE user_id=? AND language=? AND report IS NOT NULL "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, language, limit),
        ).fetchall()
    out = []
    for r in rows:
        rep = json.loads(r["report"])
        out.append({"level": r["level"], "overall": rep.get("overall"),
                    "dims": {d["key"]: d["score"] for d in rep.get("dimensions", [])}})
    return out


# ------------------------------------------------------------------ cards
_CARD_FIELDS = ("reading", "meaning", "example", "example_translation", "extra", "source_session")


def _card(r):
    return {
        "id": r["id"], "language": r["language"], "kind": r["kind"], "front": r["front"],
        "reading": r["reading"] or "", "meaning": r["meaning"] or "", "example": r["example"] or "",
        "exampleTranslation": r["example_translation"] or "", "extra": r["extra"] or "",
        "sourceSession": r["source_session"], "createdAt": r["created_at"], "dueAt": r["due_at"],
        "intervalDays": r["interval_days"], "reps": r["reps"], "lapses": r["lapses"],
        "lastReviewedAt": r["last_reviewed_at"],
    }


def add_card(user_id: int, language: str, kind: str, front: str, **fields) -> tuple:
    """Insert a card; returns (card, created). An existing identical card is returned unchanged."""
    front = (front or "").strip()
    with _conn() as c:
        cur = c.execute(
            f"INSERT OR IGNORE INTO cards (user_id, language, kind, front, {', '.join(_CARD_FIELDS)}, created_at, due_at) "
            f"VALUES (?, ?, ?, ?, {', '.join('?' * len(_CARD_FIELDS))}, ?, ?)",
            (user_id, language, kind, front, *[(fields.get(f) or "").strip() or None for f in _CARD_FIELDS], _now(), _now()),
        )
        created = cur.rowcount == 1
        row = c.execute("SELECT * FROM cards WHERE user_id=? AND language=? AND kind=? AND front=?",
                        (user_id, language, kind, front)).fetchone()
    return _card(row), created


def list_cards(user_id: int, language=None, kind=None, due_only=False, limit: int = 500):
    where, args = ["user_id=?"], [user_id]
    if language:
        where.append("language=?"); args.append(language)
    if kind:
        where.append("kind=?"); args.append(kind)
    if due_only:
        where.append("due_at <= ?"); args.append(_now())
    order = "due_at ASC" if due_only else "created_at DESC"
    with _conn() as c:
        rows = c.execute(f"SELECT * FROM cards WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ?", (*args, limit)).fetchall()
    return [_card(r) for r in rows]


def card_summary(user_id: int) -> dict:
    with _conn() as c:
        rows = c.execute(
            "SELECT language, kind, COUNT(*) AS total, SUM(due_at <= ?) AS due FROM cards WHERE user_id=? GROUP BY language, kind",
            (_now(), user_id),
        ).fetchall()
    out = {}
    for r in rows:
        lang = out.setdefault(r["language"], {"due": 0, "total": 0, "kinds": {}})
        lang["due"] += r["due"] or 0
        lang["total"] += r["total"]
        lang["kinds"][r["kind"]] = {"due": r["due"] or 0, "total": r["total"]}
    return out


def get_card(card_id: int):
    with _conn() as c:
        r = c.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
    return ({**_card(r), "userId": r["user_id"], "ease": r["ease"]}) if r else None


def save_review(card_id: int, interval: float, ease: float, reps: int, lapsed: bool, due: str):
    with _conn() as c:
        c.execute(
            "UPDATE cards SET interval_days=?, ease=?, reps=?, lapses=lapses+?, due_at=?, last_reviewed_at=? WHERE id=?",
            (interval, ease, reps, int(lapsed), due, _now(), card_id),
        )


def delete_card(card_id: int):
    with _conn() as c:
        c.execute("DELETE FROM cards WHERE id=?", (card_id,))


def delete_session(sid: str):
    with _conn() as c:
        c.execute("DELETE FROM sessions WHERE id=?", (sid,))
