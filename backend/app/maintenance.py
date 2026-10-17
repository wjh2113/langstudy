"""Housekeeping that keeps the disk and tables from growing forever.

Runs once at startup and then every few hours on a daemon thread:
- TTS cache: trimmed to TTS_CACHE_MAX_MB, least recently played first
- practice recordings: deleted after AUDIO_RETENTION_DAYS (deleting a practice deletes them at once)
- finished jobs, old failed-login records and expired login tokens
"""
import shutil
import threading
import time

from . import config, db, jobs, ratelimit, tts

AUDIO_DIR = config.DATA_DIR / "audio"
INTERVAL = 6 * 3600


def prune_recordings(days: int | None = None, now: float | None = None) -> int:
    days = config.AUDIO_RETENTION_DAYS if days is None else days
    if days <= 0 or not AUDIO_DIR.exists():
        return 0
    cutoff = (now or time.time()) - days * 86400
    removed = 0
    for folder in AUDIO_DIR.iterdir():
        if not folder.is_dir():
            continue
        for f in folder.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:
                pass
        try:
            if not any(folder.iterdir()):
                shutil.rmtree(folder, ignore_errors=True)
        except OSError:
            pass
    return removed


def run_once() -> dict:
    out = {}
    for name, fn in (("ttsCache", tts.prune_cache), ("recordings", prune_recordings),
                     ("jobs", jobs.prune), ("authFailures", ratelimit.prune), ("tokens", _prune_tokens)):
        try:
            out[name] = fn()
        except Exception as e:  # never let housekeeping take the app down
            out[name] = f"error: {e}"
    return out


def _prune_tokens():
    with db._conn() as c:
        c.execute("DELETE FROM auth_tokens WHERE expires_at < ?", (db._now(),))


def start():
    def loop():
        while True:
            run_once()
            time.sleep(INTERVAL)

    threading.Thread(target=loop, name="maintenance", daemon=True).start()
