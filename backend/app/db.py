"""SQLite storage: users, login tokens, invite codes, practice sessions, answers and reports."""
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
    """Create / upgrade the schema (see migrations.py)."""
    from . import migrations

    conn = _conn()
    try:
        migrations.run(conn)
    finally:
        conn.close()


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


def previous_session(user_id: int, language: str, level: str, mode: str, topic: str):
    """The user's latest session with the same language, level, mode and topic (for reuse)."""
    with _conn() as c:
        r = c.execute(
            """SELECT id, created_at, title, overall, report IS NOT NULL AS done FROM sessions
               WHERE user_id=? AND language=? AND level=? AND mode=? AND lower(trim(topic))=lower(trim(?))
               ORDER BY created_at DESC LIMIT 1""",
            (user_id, language, level, mode, topic),
        ).fetchone()
    if not r:
        return None
    return {"id": r["id"], "createdAt": r["created_at"], "title": r["title"], "overall": r["overall"], "done": bool(r["done"])}


def repeat_session(sid: str, user_id: int) -> str:
    """A fresh attempt at an earlier session's material (and its study notes) — no model call."""
    old = get_session(sid)
    new_id = create_session(old["content"], user_id)
    with _conn() as c:
        c.execute("UPDATE sessions SET notes=(SELECT notes FROM sessions WHERE id=?), notes_at=(SELECT notes_at FROM sessions WHERE id=?) WHERE id=?",
                  (sid, sid, new_id))
    return new_id


def get_translations(keys: list) -> dict:
    if not keys:
        return {}
    with _conn() as c:
        rows = c.execute(f"SELECT key, translation FROM translations WHERE key IN ({','.join('?' * len(keys))})", keys).fetchall()
    return {r["key"]: r["translation"] for r in rows}


def save_translations(items: list):
    """items: (key, language, text, translation)"""
    with _conn() as c:
        c.executemany("INSERT OR REPLACE INTO translations (key, language, text, translation, created_at) VALUES (?,?,?,?,?)",
                      [(*i, _now()) for i in items])


def save_report(sid: str, turns: list, report: dict):
    now = _now()
    with _exclusive() as c:
        row = c.execute("SELECT user_id, language FROM sessions WHERE id=?", (sid,)).fetchone()
        _replace_turns(c, sid, row["user_id"], row["language"], turns, now)
        _grade_turns(c, sid, report)
        c.execute("UPDATE sessions SET turns=NULL, report=?, overall=?, state=NULL, updated_at=? WHERE id=?",
                  (json.dumps(report, ensure_ascii=False), report.get("overall"), now, sid))


def set_share_token(sid: str, token):
    with _conn() as c:
        c.execute("UPDATE sessions SET share_token=? WHERE id=?", (token, sid))


def session_by_share_token(token: str):
    with _conn() as c:
        row = c.execute("SELECT id FROM sessions WHERE share_token=? AND report IS NOT NULL", (token,)).fetchone()
    return get_session(row["id"]) if row else None


def mistake_stats(language=None, limit: int = 20) -> dict:
    """Across all users: how many answers were flagged, and the most frequent correction notes."""
    where, args = "WHERE ok IS NOT NULL AND kind NOT IN ('shadow','dictation')", []
    if language:
        where += " AND language=?"
        args.append(language)
    with _conn() as c:
        total, flagged = c.execute(f"SELECT COUNT(*), COALESCE(SUM(ok=0), 0) FROM turns {where}", args).fetchone()
        top = c.execute(
            f"SELECT notes, COUNT(*) AS n, COUNT(DISTINCT user_id) AS users FROM turns {where} AND ok=0 AND notes IS NOT NULL "
            "GROUP BY notes ORDER BY n DESC LIMIT ?", (*args, limit)).fetchall()
        by_kind = c.execute(
            f"SELECT kind, COUNT(*) AS n, COALESCE(SUM(ok=0), 0) AS bad FROM turns {where} GROUP BY kind", args).fetchall()
    return {
        "graded": total, "flagged": flagged,
        "topNotes": [{"notes": r["notes"], "count": r["n"], "users": r["users"]} for r in top],
        "byKind": [{"kind": r["kind"], "graded": r["n"], "flagged": r["bad"]} for r in by_kind],
    }


def get_session(sid: str):
    with _conn() as c:
        row = c.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        if not row:
            return None
        turn_rows = c.execute("SELECT data FROM turns WHERE session_id=? ORDER BY seq", (sid,)).fetchall()
    return {
        "id": row["id"],
        "userId": row["user_id"],
        "createdAt": row["created_at"],
        "content": json.loads(row["content"]),
        "turns": [json.loads(r["data"]) for r in turn_rows],
        "state": json.loads(row["state"]) if row["state"] else None,
        "report": json.loads(row["report"]) if row["report"] else None,
        "shareToken": row["share_token"],
    }


_TURN_COLS = ("session_id", "user_id", "seq", "turn_key", "language", "kind", "follow_up", "prompt", "reference",
              "answer", "input", "duration_sec", "plays", "text_hidden", "pron_score", "audio_url", "data",
              "created_at", "updated_at")


def _turn_row(sid: str, user_id, language: str, seq: int, t: dict, now: str) -> tuple:
    return (sid, user_id, seq, str(t.get("id") or f"t{seq}")[:60], language, t.get("kind"), int(bool(t.get("followUp"))),
            t.get("prompt"), t.get("reference"), t.get("answer"), t.get("input"), t.get("durationSec"), t.get("plays"),
            int(bool(t.get("textHidden"))), t.get("pronScore"), t.get("audioUrl"), json.dumps(t, ensure_ascii=False),
            now, now)


def _replace_turns(c, sid: str, user_id, language: str, turns: list, now: str):
    created = {r["turn_key"]: r["created_at"] for r in c.execute("SELECT turn_key, created_at FROM turns WHERE session_id=?", (sid,))}
    c.execute("DELETE FROM turns WHERE session_id=?", (sid,))
    rows = []
    for i, t in enumerate(turns):
        row = list(_turn_row(sid, user_id, language, i, t, now))
        row[-2] = created.get(row[3], now)
        rows.append(row)
    c.executemany(f"INSERT OR REPLACE INTO turns ({', '.join(_TURN_COLS)}) VALUES ({', '.join('?' * len(_TURN_COLS))})", rows)


def save_progress(sid: str, turns: list, state) -> str:
    """Autosave of an unfinished practice: its answers so far and the UI state needed to resume."""
    now = _now()
    with _exclusive() as c:
        row = c.execute("SELECT user_id, language, report FROM sessions WHERE id=?", (sid,)).fetchone()
        if row["report"]:
            raise ValueError("这个练习已经评过分了")
        _replace_turns(c, sid, row["user_id"], row["language"], turns, now)
        c.execute("UPDATE sessions SET state=?, updated_at=? WHERE id=?",
                  (json.dumps(state, ensure_ascii=False) if state is not None else None, now, sid))
    return now


def _grade_turns(c, sid: str, report: dict):
    for it in report.get("items", []):
        key = it.get("key")
        if not key:
            continue
        ok = it.get("ok")
        if it.get("kind") == "dictation":
            ok = it.get("correct")
        c.execute("UPDATE turns SET ok=?, corrected=?, better=?, notes=? WHERE session_id=? AND turn_key=?",
                  (None if ok is None else int(bool(ok)), it.get("corrected") or None, it.get("better") or None,
                   it.get("notes") or None, sid, key))


def list_sessions(user_id=None, limit: int = 200):
    """One user's sessions, or everyone's when user_id is None (admin view)."""
    where, args = ("WHERE s.user_id=?", (user_id,)) if user_id is not None else ("", ())
    with _conn() as c:
        rows = c.execute(
            f"""SELECT s.id, s.created_at, s.language, s.level, s.mode, s.topic, s.title, s.overall,
                       s.report IS NOT NULL AS done, s.notes IS NOT NULL AS has_notes, u.username, s.updated_at,
                       (SELECT COUNT(*) FROM turns t WHERE t.session_id=s.id) AS answered
                FROM sessions s LEFT JOIN users u ON u.id=s.user_id {where}
                ORDER BY s.created_at DESC LIMIT ?""",
            (*args, limit),
        ).fetchall()
    return [
        {**{k: r[k] for k in ("id", "language", "level", "mode", "topic", "title", "overall", "username")},
         "createdAt": r["created_at"], "updatedAt": r["updated_at"], "done": bool(r["done"]),
         "hasNotes": bool(r["has_notes"]), "answered": r["answered"]}
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


def create_course(user_id: int, title: str, topic: str, language: str, source_name: str, items: list) -> str:
    cid = uuid.uuid4().hex[:12]
    with _conn() as c:
        c.execute(
            "INSERT INTO courses (id, user_id, title, topic, language, source_name, created_at, items) VALUES (?,?,?,?,?,?,?,?)",
            (cid, user_id, title, topic, language, source_name, _now(), json.dumps(items, ensure_ascii=False)),
        )
    return cid


def get_course(cid: str):
    with _conn() as c:
        r = c.execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone()
    if not r:
        return None
    return {
        "id": r["id"], "userId": r["user_id"], "title": r["title"], "topic": r["topic"],
        "language": r["language"], "sourceName": r["source_name"] or "", "createdAt": r["created_at"],
        "items": json.loads(r["items"]),
    }
