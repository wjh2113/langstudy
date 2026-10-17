"""Schema migrations.

Each change to the database structure is a numbered step below. On startup the
steps that have not run yet are applied in order, each in its own transaction,
and recorded in `schema_version`. To change the schema, append a new step —
never edit one that has already shipped.
"""
import json
import sqlite3
from datetime import datetime


def _script(c, sql: str):
    """Run several statements inside the current transaction (executescript would commit first)."""
    for stmt in sql.split(";"):
        if stmt.strip():
            c.execute(stmt)


def _cols(c, table: str) -> set:
    return {r[1] for r in c.execute(f"PRAGMA table_info({table})")}


def m001_baseline(c):
    """Tables of the multi-user version. Safe on databases created before migrations existed."""
    _script(c, 
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
            front TEXT NOT NULL,
            reading TEXT, meaning TEXT, example TEXT, example_translation TEXT,
            extra TEXT,
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
    cols = _cols(c, "sessions")
    if "user_id" not in cols:
        c.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER")
    if "notes" not in cols:
        c.execute("ALTER TABLE sessions ADD COLUMN notes TEXT")
        c.execute("ALTER TABLE sessions ADD COLUMN notes_at TEXT")


def m002_translations(c):
    c.execute(
        """CREATE TABLE IF NOT EXISTS translations (
               key TEXT PRIMARY KEY, language TEXT NOT NULL, text TEXT NOT NULL,
               translation TEXT NOT NULL, created_at TEXT NOT NULL)"""
    )


def m003_turns_table(c):
    """One row per answer, so progress can be saved as you go and answers can be analysed."""
    _script(c, 
        """
        CREATE TABLE turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            user_id INTEGER,
            seq INTEGER NOT NULL,
            turn_key TEXT NOT NULL,           -- the frontend's id for this turn
            language TEXT,
            kind TEXT,                        -- answer | line | shadow | dictation | chat ...
            follow_up INTEGER NOT NULL DEFAULT 0,
            prompt TEXT, reference TEXT, answer TEXT,
            input TEXT,                       -- voice | text
            duration_sec REAL,
            plays INTEGER,
            text_hidden INTEGER,
            pron_score REAL,
            audio_url TEXT,
            ok INTEGER,                       -- graded: 1 fine, 0 had problems, NULL not graded
            corrected TEXT, better TEXT, notes TEXT,
            data TEXT NOT NULL,               -- the full turn as sent by the frontend
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (session_id, turn_key)
        );
        CREATE INDEX idx_turns_user ON turns(user_id);
        CREATE INDEX idx_turns_lang_kind ON turns(language, kind);
        """
    )
    c.execute("ALTER TABLE sessions ADD COLUMN state TEXT")  # practice UI state for resuming
    c.execute("ALTER TABLE sessions ADD COLUMN updated_at TEXT")
    # move answers saved as one JSON blob into rows
    now = datetime.now().isoformat(timespec="seconds")
    rows = c.execute("SELECT id, user_id, language, turns, report FROM sessions WHERE turns IS NOT NULL").fetchall()
    for sid, uid, lang, turns_json, report_json in rows:
        try:
            turns = json.loads(turns_json) or []
            items = (json.loads(report_json) or {}).get("items", []) if report_json else []
        except (TypeError, ValueError):
            continue
        for i, t in enumerate(turns):
            it = items[i] if i < len(items) else {}
            c.execute(
                """INSERT OR IGNORE INTO turns (session_id, user_id, seq, turn_key, language, kind, follow_up, prompt,
                   reference, answer, input, duration_sec, plays, text_hidden, pron_score, audio_url,
                   corrected, better, notes, data, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sid, uid, i, str(t.get("id") or f"t{i}"), lang, t.get("kind"), int(bool(t.get("followUp"))),
                 t.get("prompt"), t.get("reference"), t.get("answer"), t.get("input"), t.get("durationSec"),
                 t.get("plays"), int(bool(t.get("textHidden"))), t.get("pronScore"), t.get("audioUrl"),
                 it.get("corrected"), it.get("better"), it.get("notes"), json.dumps(t, ensure_ascii=False), now, now),
            )


def m004_ai_usage(c):
    """Every model / speech call: who, what for, tokens and credits (when the gateway reports them)."""
    _script(c, 
        """
        CREATE TABLE ai_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id TEXT,
            task TEXT NOT NULL,               -- generate | evaluate | followup | chat | notes | translate | tts | stt | pronounce
            capability TEXT,
            ok INTEGER NOT NULL,
            prompt_tokens INTEGER, completion_tokens INTEGER, total_tokens INTEGER,
            credits REAL,
            chars INTEGER,
            ms INTEGER,
            error TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX idx_ai_usage_user_day ON ai_usage(user_id, created_at);
        """
    )


def m005_auth_failures(c):
    _script(c, 
        """
        CREATE TABLE auth_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,              -- ip | account | invite
            key TEXT NOT NULL,
            at REAL NOT NULL                  -- unix time
        );
        CREATE INDEX idx_auth_failures ON auth_failures(scope, key, at);
        """
    )


def m006_jobs(c):
    _script(c, 
        """
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            session_id TEXT,
            kind TEXT NOT NULL,               -- generate | evaluate | notes
            status TEXT NOT NULL,             -- pending | running | done | error
            result TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_jobs_lookup ON jobs(user_id, kind, session_id, status);
        """
    )


def m007_share_links(c):
    c.execute("ALTER TABLE sessions ADD COLUMN share_token TEXT")
    c.execute("CREATE UNIQUE INDEX idx_sessions_share ON sessions(share_token) WHERE share_token IS NOT NULL")


MIGRATIONS = [
    (1, m001_baseline),
    (2, m002_translations),
    (3, m003_turns_table),
    (4, m004_ai_usage),
    (5, m005_auth_failures),
    (6, m006_jobs),
    (7, m007_share_links),
]


def current_version(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT)")
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return row[0] or 0


def run(conn: sqlite3.Connection) -> list:
    """Apply pending migrations; returns the versions applied."""
    conn.isolation_level = None
    applied = []
    conn.execute("BEGIN IMMEDIATE")  # one process migrates at a time
    try:
        version = current_version(conn)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    for number, step in MIGRATIONS:
        if number <= version:
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            if current_version(conn) >= number:  # another process got there first
                conn.execute("COMMIT")
                continue
            step(conn)
            conn.execute("INSERT INTO schema_version VALUES (?, ?, ?)",
                         (number, step.__name__, datetime.now().isoformat(timespec="seconds")))
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        applied.append(number)
    return applied
