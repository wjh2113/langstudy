"""Text-to-speech, cached on disk.

Default: Microsoft Edge neural voices (edge-tts, free). With TTS_PROVIDER=gateway
the AIapiMgr gateway (capability `tts`, CosyVoice2, billed per call) is used.
The cache is capped at TTS_CACHE_MAX_MB; the least recently played files go first.
"""
import asyncio
import hashlib
import os
import threading

from . import config
from .languages import get_accent, get_language
from .tts_silence import tighten_mp3


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
    from . import ai
    from .gateway import GatewayError, tts

    def run():
        with ai.track("tts", config.GATEWAY_CAP_TTS, chars=len(text)):
            return tts(text, voice, rate)

    try:
        return await asyncio.to_thread(run)  # to_thread carries the caller's AI scope along
    except GatewayError as e:
        raise TTSError(str(e)) from e


_prune_lock = threading.Lock()
_writes_since_prune = 0
PRUNE_EVERY = 20  # check the cache size every N new files
_synth_locks: dict[str, asyncio.Lock] = {}


def prune_cache(max_bytes: int | None = None) -> int:
    """Delete least-recently-used cache files until the cache is under 90% of its cap. Returns files removed."""
    max_bytes = (config.TTS_CACHE_MAX_MB * 1024 * 1024) if max_bytes is None else max_bytes
    if max_bytes <= 0:
        return 0
    with _prune_lock:
        files = []
        total = 0
        with os.scandir(config.TTS_CACHE_DIR) as it:
            for e in it:
                if e.is_file() and e.name.endswith(".mp3"):
                    st = e.stat()
                    files.append((st.st_mtime, st.st_size, e.path))
                    total += st.st_size
        if total <= max_bytes:
            return 0
        removed, target = 0, max_bytes * 0.9
        for _, size, path in sorted(files):  # oldest use first
            if total <= target:
                break
            try:
                os.remove(path)
            except OSError:
                continue
            total -= size
            removed += 1
        return removed


def _touch(path):
    try:
        os.utime(path)  # mark as recently used for the LRU cleanup
    except OSError:
        pass


async def synthesize(text: str, language: str, voice_index: int = 0, rate: float = 1.0, accent: str = "default") -> bytes:
    if not config.TTS_ENABLED:
        raise TTSError("服务端语音合成已关闭")
    text = text.strip()[:2000]
    if not text:
        raise TTSError("没有可朗读的文字")
    rate = max(0.5, min(rate, 1.5))
    accent_voices, _ = get_accent(language, accent)
    if accent_voices:  # a specific accent: always Edge regional voices
        voices, provider = accent_voices, "edge"
    elif config.tts_uses_gateway():
        voices, provider = config.GATEWAY_TTS_VOICES or [""], "gateway"
    else:
        voices, provider = get_language(language)["voices"], "edge"
    voice = voices[voice_index % len(voices)]

    # gap180: mid-word stalls collapse; a short breath after ? . ! stays.
    # vcn2: 讯飞 alex/anna gender map was swapped; bust old wrong-gender clips.
    gap = "|gap180|vcn2" if provider == "gateway" else ""
    key = hashlib.sha1(f"{provider}|{voice}|{rate:.2f}|{text}{gap}".encode()).hexdigest()
    path = config.TTS_CACHE_DIR / f"{key}.mp3"
    hit = _read_cached(path)
    if hit is not None:
        return hit
    # Two clicks on the same sentence share one synthesis, same as 小树学堂.
    lock = _synth_locks.setdefault(key, asyncio.Lock())
    try:
        async with lock:
            hit = _read_cached(path)
            if hit is not None:
                return hit
            audio = await (_gateway(text, voice, rate) if provider == "gateway" else _edge(text, voice, rate))
            if not audio:
                raise TTSError("语音合成没有返回音频")
            if provider == "gateway":
                audio = await asyncio.to_thread(tighten_mp3, audio, text)
            tmp = path.with_suffix(".part")
            tmp.write_bytes(audio)
            os.replace(tmp, path)
            global _writes_since_prune
            _writes_since_prune += 1
            if _writes_since_prune >= PRUNE_EVERY:
                _writes_since_prune = 0
                await asyncio.to_thread(prune_cache)
            return audio
    finally:
        if not lock.locked():
            _synth_locks.pop(key, None)


def _read_cached(path) -> bytes | None:
    if path.exists() and path.stat().st_size > 0:
        _touch(path)
        return path.read_bytes()
    return None
