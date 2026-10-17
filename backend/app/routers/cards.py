"""/api/cards: wordbook, pattern and mistake cards with spaced-repetition review."""
from typing import Optional

from fastapi import APIRouter, Depends

from .. import db, srs
from ..deps import bad, current_user
from ..schemas import CardReq, ReviewReq

router = APIRouter(prefix="/api/cards", tags=["cards"])


def _own_card(card_id: int, user: dict) -> dict:
    card = db.get_card(card_id)
    if not card or card["userId"] != user["id"]:
        bad("卡片不存在", 404)
    return card


@router.get("")
def api_cards(language: Optional[str] = None, kind: Optional[str] = None, due: bool = False,
              user: dict = Depends(current_user)):
    return db.list_cards(user["id"], language, kind, due)


@router.get("/summary")
def api_cards_summary(user: dict = Depends(current_user)):
    return db.card_summary(user["id"])


@router.post("")
def api_add_card(req: CardReq, user: dict = Depends(current_user)):
    if not req.front.strip():
        bad("卡片内容不完整")
    card, created = db.add_card(
        user["id"], req.language, req.kind, req.front[:500], reading=req.reading, meaning=req.meaning,
        example=req.example, example_translation=req.exampleTranslation, extra=req.extra, source_session=req.sourceSession,
    )
    return {"card": card, "created": created}


@router.post("/{card_id}/review")
def api_review_card(card_id: int, req: ReviewReq, user: dict = Depends(current_user)):
    card = _own_card(card_id, user)
    try:
        interval, ease, reps, lapsed = srs.schedule(card["intervalDays"], card["ease"], card["reps"], req.grade)
    except ValueError as e:
        bad(e)
    db.save_review(card_id, interval, ease, reps, lapsed, srs.due_at(interval))
    return {"intervalDays": interval, "dueAt": srs.due_at(interval)}


@router.delete("/{card_id}")
def api_delete_card(card_id: int, user: dict = Depends(current_user)):
    _own_card(card_id, user)
    db.delete_card(card_id)
    return {"ok": True}
