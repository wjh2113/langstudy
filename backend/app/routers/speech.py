"""Speech: text-to-speech, speech recognition and (on demand) pronunciation assessment."""
from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from .. import ai, config
from ..deps import MAX_AUDIO, bad, current_user, own_session
from ..schemas import TTSReq
from ..stt import STTError, transcribe
from ..tts import TTSError, synthesize
from .sessions import _AUDIO_NAME, audio_dir

router = APIRouter(prefix="/api", tags=["speech"])


@router.post("/tts")
async def api_tts(req: TTSReq, user: dict = Depends(current_user)):
    try:
        with ai.scope(user):
            audio = await synthesize(req.text, req.language, req.voiceIndex, req.rate, req.accent)
    except (ValueError, TTSError) as e:
        bad(e, 502)
    return Response(content=bytes(audio), media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.post("/stt")
async def api_stt(audio: UploadFile = File(...), language: str = Form("en"), user: dict = Depends(current_user)):
    data = await audio.read()
    if len(data) > MAX_AUDIO:
        bad("录音太长了，请分段作答")
    try:
        with ai.scope(user):
            text = transcribe(data, audio.filename or "speech.webm", language, audio.content_type or "")
    except STTError as e:
        bad(e, 502)
    return {"text": text}


@router.post("/pronounce")
async def api_pronounce(text: str = Form(...), language: str = Form("en"), audio: UploadFile | None = File(None),
                        sessionId: str = Form(""), audioName: str = Form(""), user: dict = Depends(current_user)):
    """Score a recording against the script it was reading (gateway `pronunciation`, billed per call,
    so the frontend only calls it when the learner taps 评测发音). Send the audio, or the name of a
    recording already saved with the session."""
    if not config.gateway_enabled():
        bad("未配置网关，发音评测不可用", 404)
    if audio is not None:
        data, filename, mime = await audio.read(), audio.filename or "speech.webm", audio.content_type or ""
    elif sessionId and audioName:
        own_session(sessionId, user)
        if not _AUDIO_NAME.fullmatch(audioName) or not (audio_dir(sessionId) / audioName).is_file():
            bad("录音不存在或已过保留期", 404)
        data, filename = (audio_dir(sessionId) / audioName).read_bytes(), audioName
        mime = {"webm": "audio/webm", "mp4": "audio/mp4", "ogg": "audio/ogg"}[audioName.rsplit(".", 1)[1]]
    else:
        bad("没有录音")
    if not data or len(data) > MAX_AUDIO:
        bad("录音为空或太长了")
    if not text.strip() or len(text) > 8000:
        bad("参考文本为空或太长")
    from ..gateway import GatewayError, pronounce

    try:
        with ai.scope(user, sessionId or None), ai.track("pronounce", config.GATEWAY_CAP_PRONOUNCE, chars=len(data)):
            return pronounce(data, filename, mime, text.strip(), language)
    except GatewayError as e:
        bad(e, 502)
