"""The one place the app talks to AI services.

Every model / speech call goes through here, so retries, idempotency keys,
timeouts, JSON repair, per-user daily limits and usage accounting are handled
once instead of in each feature module:

    with ai.scope(user, session_id):          # who the calls are for
        data = ai.chat_json(SYSTEM, prompt, task="evaluate", fast=True)

Retries with a stable idempotency key happen in gateway._post; broken JSON is
repaired locally and only re-asked once (llm.parse_json / chat_json below).
"""
import contextvars
import time
from contextlib import contextmanager
from datetime import datetime

from . import config, db
from .llm import LLMError, parse_json, raw_chat


class QuotaError(LLMError):
    """The user has used up today's AI calls (AI_DAILY_LIMIT)."""


_scope: contextvars.ContextVar = contextvars.ContextVar("ai_scope", default=None)


@contextmanager
def scope(user: dict | None = None, session_id: str | None = None):
    """Attribute AI calls made inside this block to a user (and practice session)."""
    token = _scope.set({"user_id": (user or {}).get("id"), "role": (user or {}).get("role"), "session_id": session_id})
    try:
        yield
    finally:
        _scope.reset(token)


def _ctx() -> dict:
    return _scope.get() or {}


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%dT00:00:00")


def calls_today(user_id: int) -> int:
    with db._conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM ai_usage WHERE user_id=? AND created_at>=? AND task NOT IN ('tts','stt','pronounce')",
            (user_id, _today()),
        ).fetchone()[0]


def check_quota():
    ctx = _ctx()
    if not config.AI_DAILY_LIMIT or not ctx.get("user_id") or ctx.get("role") == "admin":
        return
    if calls_today(ctx["user_id"]) >= config.AI_DAILY_LIMIT:
        raise QuotaError(f"今天的 AI 调用次数已用完（每天 {config.AI_DAILY_LIMIT} 次），明天再来吧")


def record(task: str, capability: str, ok: bool, usage: dict | None = None, chars: int | None = None,
           ms: int | None = None, error: str = ""):
    ctx, usage = _ctx(), usage or {}
    try:
        with db._conn() as c:
            c.execute(
                """INSERT INTO ai_usage (user_id, session_id, task, capability, ok, prompt_tokens, completion_tokens,
                   total_tokens, credits, chars, ms, error, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ctx.get("user_id"), ctx.get("session_id"), task, capability, int(ok), usage.get("prompt_tokens"),
                 usage.get("completion_tokens"), usage.get("total_tokens"), usage.get("credits"), chars, ms,
                 error[:300] or None, datetime.now().isoformat(timespec="seconds")),
            )
    except Exception:  # accounting must never break the feature
        pass


def _capability(fast: bool) -> str:
    if config.gateway_enabled():
        return config.GATEWAY_CAP_FAST if fast else config.GATEWAY_CAP_CHAT
    return config.LLM_MODEL


def _call(system: str, user: str, temperature: float, fast: bool, task: str) -> str:
    cap = _capability(fast)
    started = time.monotonic()
    try:
        text, usage = raw_chat(system, user, temperature, fast)
    except LLMError as e:
        record(task, cap, False, ms=int((time.monotonic() - started) * 1000), error=str(e))
        raise
    record(task, cap, True, usage, chars=len(system) + len(user), ms=int((time.monotonic() - started) * 1000))
    return text


def chat_json(system: str, user: str, temperature: float = 0.7, fast: bool = False, task: str = "chat") -> dict:
    """Ask the model for a JSON object. Broken JSON is repaired locally first;
    only if that fails is the model asked again (once, as a new billed call)."""
    check_quota()
    try:
        return parse_json(_call(system, user, temperature, fast, task))
    except LLMError as e:
        if isinstance(e, QuotaError) or "JSON" not in str(e):
            raise
    return parse_json(_call(system, user, max(0.2, temperature - 0.3), fast, task + ":retry"))


@contextmanager
def track(task: str, capability: str, chars: int | None = None):
    """Account a speech call (tts / stt / pronounce). The block may set `meta["usage"]`."""
    meta = {"usage": {}}
    started = time.monotonic()
    try:
        yield meta
    except Exception as e:
        record(task, capability, False, chars=chars, ms=int((time.monotonic() - started) * 1000), error=str(e))
        raise
    record(task, capability, True, meta["usage"], chars=chars, ms=int((time.monotonic() - started) * 1000))


def usage_summary(days: int = 30) -> list:
    """Per user: calls, tokens and credits today and over the last `days` days (admin view)."""
    since = datetime.fromtimestamp(time.time() - days * 86400).strftime("%Y-%m-%dT00:00:00")
    with db._conn() as c:
        rows = c.execute(
            """SELECT u.id, u.username,
                      SUM(a.created_at >= ?) AS calls_today,
                      COUNT(a.id) AS calls,
                      COALESCE(SUM(a.total_tokens), 0) AS tokens,
                      SUM(a.credits) AS credits,
                      SUM(CASE WHEN a.created_at >= ? THEN a.credits END) AS credits_today
               FROM users u LEFT JOIN ai_usage a ON a.user_id=u.id AND a.created_at >= ?
               GROUP BY u.id ORDER BY calls DESC""",
            (_today(), _today(), since),
        ).fetchall()
        tasks = c.execute(
            "SELECT task, COUNT(*) AS n, COALESCE(SUM(total_tokens), 0) AS tokens, SUM(credits) AS credits "
            "FROM ai_usage WHERE created_at >= ? GROUP BY task ORDER BY n DESC", (since,)).fetchall()
    return {
        "days": days,
        "dailyLimit": config.AI_DAILY_LIMIT,
        "users": [{"id": r["id"], "username": r["username"], "callsToday": r["calls_today"] or 0, "calls": r["calls"],
                   "tokens": r["tokens"], "credits": r["credits"], "creditsToday": r["credits_today"]} for r in rows],
        "tasks": [{"task": r["task"], "calls": r["n"], "tokens": r["tokens"], "credits": r["credits"]} for r in tasks],
    }
