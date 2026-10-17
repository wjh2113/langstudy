"""Background jobs for slow model calls (generate / evaluate / notes).

The request returns a job id at once; the work runs on a small thread pool and
the frontend polls GET /api/jobs/{id}. Status lives in the database, so any
worker process can answer the poll. Submitting the same kind of job for the
same session while one is still running returns the running job instead of
starting (and paying for) a second one.
"""
import json
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from . import ai, config, db
from .llm import LLMError

_pool = ThreadPoolExecutor(max_workers=max(1, config.JOB_WORKERS), thread_name_prefix="job")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _set(job_id: str, **fields):
    fields["updated_at"] = _now()
    with db._conn() as c:
        c.execute(f"UPDATE jobs SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?", (*fields.values(), job_id))


def _run(job_id: str, user: dict, session_id, fn):
    _set(job_id, status="running")
    try:
        with ai.scope(user, session_id):
            result = fn()
    except (ValueError, LLMError) as e:
        _set(job_id, status="error", error=str(e))
    except Exception as e:  # pragma: no cover - unexpected bug: keep the message short for the user
        traceback.print_exc()
        _set(job_id, status="error", error=f"处理失败：{e}")
    else:
        _set(job_id, status="done", result=json.dumps(result, ensure_ascii=False))


def submit(kind: str, user: dict, fn, session_id: str | None = None, run_inline: bool = False) -> str:
    """Queue `fn()` and return the job id. `fn` runs with the user's AI scope."""
    with db._exclusive() as c:
        if session_id:
            row = c.execute(
                "SELECT id FROM jobs WHERE user_id=? AND kind=? AND session_id=? AND status IN ('pending','running')",
                (user["id"], kind, session_id),
            ).fetchone()
            if row:
                return row["id"]
        job_id = uuid.uuid4().hex
        now = _now()
        c.execute("INSERT INTO jobs (id, user_id, session_id, kind, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                  (job_id, user["id"], session_id, kind, "pending", now, now))
    if run_inline:
        _run(job_id, user, session_id, fn)
    else:
        _pool.submit(_run, job_id, user, session_id, fn)
    return job_id


def get(job_id: str):
    with db._conn() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not r:
        return None
    out = {"id": r["id"], "kind": r["kind"], "status": r["status"], "userId": r["user_id"],
           "sessionId": r["session_id"], "createdAt": r["created_at"]}
    if r["status"] == "done":
        out["result"] = json.loads(r["result"]) if r["result"] else None
    if r["status"] == "error":
        out["error"] = r["error"] or "处理失败"
    # a job far past the model timeout is not coming back (e.g. the worker died)
    limit = timedelta(seconds=config.AI_TIMEOUT_SEC * 3 + 60)
    if r["status"] in ("pending", "running") and datetime.fromisoformat(r["updated_at"]) < datetime.now() - limit:
        _set(r["id"], status="error", error="处理超时，请重试")
        out.update(status="error", error="处理超时，请重试")
    return out


def recover():
    """On startup: jobs left pending/running by a previous process will never finish."""
    with db._conn() as c:
        c.execute("UPDATE jobs SET status='error', error='服务重启了，请重试', updated_at=? WHERE status IN ('pending','running')",
                  (_now(),))


def prune(days: int = 2):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    with db._conn() as c:
        c.execute("DELETE FROM jobs WHERE updated_at < ?", (cutoff,))
