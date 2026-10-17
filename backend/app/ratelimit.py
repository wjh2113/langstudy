"""Brute-force protection for login, registration and invite codes.

Failed attempts are counted per IP address and per account (or per IP for
invite codes). Too many failures in the window locks that key for a while:

- one account: 5 wrong passwords in 15 minutes -> locked 5 minutes (any IP)
- one IP:      20 failed logins/registrations in 15 minutes -> locked 15 minutes
- one IP:      10 wrong invite codes in 15 minutes -> locked 15 minutes
"""
import math
import time

from . import db

WINDOW = 15 * 60
RULES = {  # scope: (max failures in WINDOW, lock seconds after the last failure)
    "account": (5, 5 * 60),
    "ip": (20, 15 * 60),
    "invite": (10, 15 * 60),
}


class Locked(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, int(retry_after))
        minutes = max(1, math.ceil(self.retry_after / 60))
        super().__init__(f"尝试次数太多，请 {minutes} 分钟后再试")


def _norm(scope: str, key: str) -> str:
    return (key or "").strip().lower()[:100]


def retry_after(scope: str, key: str, now: float | None = None) -> int:
    """Seconds until `key` may try again (0 = not locked)."""
    limit, lock = RULES[scope]
    now = now or time.time()
    with db._conn() as c:
        rows = c.execute(
            "SELECT at FROM auth_failures WHERE scope=? AND key=? AND at>? ORDER BY at DESC LIMIT ?",
            (scope, _norm(scope, key), now - WINDOW, limit),
        ).fetchall()
    if len(rows) < limit:
        return 0
    return max(0, int(rows[0]["at"] + lock - now))


def check(**keys):
    """Raise Locked if any of the given keys is locked, e.g. check(ip="1.2.3.4", account="alice")."""
    wait = max((retry_after(scope, key) for scope, key in keys.items() if key), default=0)
    if wait:
        raise Locked(wait)


def fail(**keys):
    now = time.time()
    with db._conn() as c:
        c.executemany("INSERT INTO auth_failures (scope, key, at) VALUES (?, ?, ?)",
                      [(scope, _norm(scope, key), now) for scope, key in keys.items() if key])


def clear(**keys):
    """A successful login resets that account's counter."""
    with db._conn() as c:
        for scope, key in keys.items():
            if key:
                c.execute("DELETE FROM auth_failures WHERE scope=? AND key=?", (scope, _norm(scope, key)))


def prune(now: float | None = None):
    with db._conn() as c:
        c.execute("DELETE FROM auth_failures WHERE at < ?", ((now or time.time()) - 86400,))
