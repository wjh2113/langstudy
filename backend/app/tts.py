"""Text-to-speech, cached on disk.

Default: the AIapiMgr gateway (capability `tts`, CosyVoice2). Without a gateway
key, or with TTS_PROVIDER=edge, Microsoft Edge neural voices (edge-tts) are used.
"""
import asyncio
import hashlib

from . import config
from .languages import get_language


class TTSError(RuntimeError):
    pass


def _rate_str(rate: float) -> str:
    pct = round((rate - 1.0) * 100)
    return f"{pct:+d}%"


async def _edge(text: str, voice: str, rate: float) -> bytes:
    try:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice, rate=_rate_str(rate))
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
    except Exception as e:
        raise TTSError(f"语音合成失败：{e}") from e
    return b"".join(chunks)


async def _gateway(text: str, voice: str, rate: float) -> bytes:
    from .gateway import GatewayError, tts

    try:
        return await asyncio.to_thread(tts, text, voice, rate)
    except GatewayError as e:
        raise TTSError(str(e)) from e


async def synthesize(text: str, language: str, voice_index: int = 0, rate: float = 1.0) -> bytes:
    if not config.TTS_ENABLED:
        raise TTSError("服务端语音合成已关闭")
    text = text.strip()[:2000]
    if not text:
        raise TTSError("没有可朗读的文字")
    rate = max(0.5, min(rate, 1.5))
    if config.tts_uses_gateway():
        voices, provider = config.GATEWAY_TTS_VOICES or [""], "gateway"
    else:
        voices, provider = get_language(language)["voices"], "edge"
    voice = voices[voice_index % len(voices)]

    key = hashlib.sha1(f"{provider}|{voice}|{rate:.2f}|{text}".encode()).hexdigest()
    path = config.TTS_CACHE_DIR / f"{key}.mp3"
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    audio = await (_gateway(text, voice, rate) if provider == "gateway" else _edge(text, voice, rate))
    if not audio:
        raise TTSError("语音合成没有返回音频")
    path.write_bytes(audio)
    return audio
