"""Optional server-side speech recognition via an OpenAI-compatible
/audio/transcriptions endpoint (OpenAI whisper-1, SiliconFlow SenseVoice, Groq...)."""
from . import config


class STTError(RuntimeError):
    pass


def transcribe(audio: bytes, filename: str, language: str, mime: str = "") -> str:
    if config.gateway_enabled():
        from . import ai
        from .gateway import GatewayError, transcribe as gw_transcribe

        try:
            with ai.track("stt", config.GATEWAY_CAP_SPEECH, chars=len(audio)):
                return gw_transcribe(audio, filename, mime, language)
        except GatewayError as e:
            raise STTError(str(e)) from e
    if not config.stt_server_enabled():
        raise STTError("未配置服务端语音识别（STT_BASE_URL / STT_API_KEY）")
    try:
        from openai import OpenAI

        client = OpenAI(base_url=config.STT_BASE_URL, api_key=config.STT_API_KEY, timeout=60)
        result = client.audio.transcriptions.create(
            model=config.STT_MODEL, file=(filename, audio), language=language
        )
    except Exception as e:
        raise STTError(f"语音识别失败：{e}") from e
    return (getattr(result, "text", "") or "").strip()
