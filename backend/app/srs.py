"""Spaced repetition (a small SM-2 variant) for the word / pattern / sentence cards."""
from datetime import datetime, timedelta

GRADES = {"again": 0, "hard": 1, "good": 2, "easy": 3}


def schedule(interval: float, ease: float, reps: int, grade: str):
    """Return (new_interval_days, new_ease, new_reps, lapsed) after a review."""
    g = GRADES.get(grade)
    if g is None:
        raise ValueError("评分只能是 again / hard / good / easy")
    if g == 0:  # forgot: see it again in 10 minutes, ease drops
        return 10 / 1440, max(1.3, ease - 0.2), 0, True
    if reps == 0:
        new = {1: 1, 2: 1, 3: 3}[g]
    elif reps == 1:
        new = {1: 2, 2: 3, 3: 6}[g]
    else:
        new = interval * {1: 1.2, 2: ease, 3: ease * 1.3}[g]
    ease = max(1.3, ease + {1: -0.15, 2: 0.0, 3: 0.15}[g])
    return round(min(new, 365), 3), round(ease, 2), reps + 1, False


def due_at(interval_days: float, now: datetime | None = None) -> str:
    return ((now or datetime.now()) + timedelta(days=interval_days)).isoformat(timespec="seconds")
