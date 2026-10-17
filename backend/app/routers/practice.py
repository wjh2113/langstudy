"""Practice flow: generate material, follow-ups, free chat, translation, grading, job polling."""
from fastapi import APIRouter, Depends

from .. import ai, db, jobs
from ..coach import recommend
from ..conversation import reply as chat_reply
from ..evaluate import evaluate
from ..followup import follow_up
from ..generate import generate
from ..llm import LLMError
from ..mistakes import collect_mistakes
from ..translate import translate_many
from ..deps import bad, current_user, own_session
from ..schemas import (ChatReplyOut, ChatReplyReq, EvaluateReq, FollowUpReq, GenerateReq, Job, JobRef,
                       SpokenText, TranslateOut, TranslateReq)

router = APIRouter(prefix="/api", tags=["practice"])


def _llm_errors(fn):
    """Run a quick (synchronous) model call, mapping errors to HTTP codes."""
    try:
        return fn()
    except ai.QuotaError as e:
        bad(e, 429)
    except ValueError as e:
        bad(e)
    except LLMError as e:
        bad(e, 502)


@router.post("/generate", response_model=JobRef)
def api_generate(req: GenerateReq, user: dict = Depends(current_user)):
    """Starts generating material; poll /api/jobs/{jobId}. The result is {id, content}."""
    def work():
        content = generate(req.language, req.level, req.mode, req.topic, req.count, req.focus)
        return {"id": db.create_session(content, user["id"]), "content": content}

    return {"jobId": jobs.submit("generate", user, work)}


@router.post("/evaluate", response_model=JobRef)
def api_evaluate(req: EvaluateReq, user: dict = Depends(current_user)):
    """Starts grading; poll /api/jobs/{jobId}. The result is the report."""
    session = own_session(req.sessionId, user)
    if session["report"]:
        bad("这个练习已经评过分了", 409)
    turns = [t.model_dump() for t in req.turns]
    if not turns:
        bad("还没有任何作答，先说几句再结束吧")

    def work():
        report = evaluate(session["content"], turns)
        db.save_report(req.sessionId, turns, report)
        report["cardsAdded"] = collect_mistakes(session["userId"], req.sessionId,
                                                session["content"].get("language", "en"), report)
        return report

    return {"jobId": jobs.submit("evaluate", user, work, session_id=req.sessionId)}


@router.get("/jobs/{job_id}", response_model=Job)
def api_job(job_id: str, user: dict = Depends(current_user)):
    job = jobs.get(job_id)
    if not job or (job["userId"] != user["id"] and user["role"] != "admin"):
        bad("任务不存在", 404)
    return job


@router.post("/followup", response_model=SpokenText)
def api_followup(req: FollowUpReq, user: dict = Depends(current_user)):
    session = own_session(req.sessionId, user)
    with ai.scope(user, req.sessionId):
        return _llm_errors(lambda: follow_up(session["content"], req.question, req.answer,
                                             [h.model_dump() for h in req.history]))


@router.post("/chat/reply", response_model=ChatReplyOut)
def api_chat_reply(req: ChatReplyReq, user: dict = Depends(current_user)):
    session = own_session(req.sessionId, user)
    with ai.scope(user, req.sessionId):
        return _llm_errors(lambda: chat_reply(session["content"], [t.model_dump() for t in req.history], req.summary))


@router.post("/translate", response_model=TranslateOut)
def api_translate(req: TranslateReq, user: dict = Depends(current_user)):
    """Chinese translations, fetched only when the learner asks for them (cached for everyone)."""
    with ai.scope(user):
        return {"translations": _llm_errors(lambda: translate_many(req.texts, req.language))}


@router.get("/coach/{language}")
def api_coach(language: str, user: dict = Depends(current_user)):
    return recommend(db.recent_results(user["id"], language))
