"""Mistake deck: corrected sentences from reports become cards to practise again."""
from . import db
from .evaluate import tokens


def collect_mistakes(user_id: int, sid: str, language: str, report: dict) -> int:
    """Put corrected sentences from a report into the learner's mistake deck."""
    added = 0
    for it in report.get("items", []):
        corrected, answer = (it.get("corrected") or "").strip(), (it.get("answer") or "").strip()
        if not corrected or it.get("kind") in ("shadow", "dictation"):
            continue
        if tokens(corrected, language) == tokens(answer, language):
            continue  # nothing was wrong
        better = (it.get("better") or "").strip()
        _, created = db.add_card(
            user_id, language, "sentence", corrected[:500], meaning=it.get("notes") or "",
            example=better if better and better != corrected else "", extra=answer, source_session=sid,
        )
        added += int(created)
    return added
