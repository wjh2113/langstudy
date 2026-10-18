"""CosyVoice silence tightening. Run: python tests/test_tts_silence.py"""
import array
import asyncio
import math
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("GATEWAY_API_KEY", "")
os.environ.setdefault("LLM_API_KEY", "")

from app import config, tts  # noqa: E402
from app.tts_silence import KEEP_MS, STOP_KEEP_MS, has_internal_stop, shorten_silence, tighten_mp3  # noqa: E402

RATE = 16000


def _tone(ms: int, amp: int = 8000) -> array.array:
    n = RATE * ms // 1000
    out = array.array("h")
    for i in range(n):
        out.append(int(amp * math.sin(2 * math.pi * 220 * i / RATE)))
    return out


def _silence(ms: int) -> array.array:
    return array.array("h", [0] * (RATE * ms // 1000))


def _longest_internal_silence_ms(samples: array.array) -> int:
    frame = RATE // 100
    flags = []
    for i in range(0, len(samples), frame):
        chunk = samples[i : i + frame]
        acc = sum(s * s for s in chunk) / len(chunk)
        flags.append(math.sqrt(acc) < 400)
    while flags and flags[0]:
        flags.pop(0)
    while flags and flags[-1]:
        flags.pop()
    best = cur = 0
    for flag in flags:
        if flag:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best * 10


def test_short_pause_stays():
    samples = _tone(250) + _silence(80) + _tone(250)
    assert shorten_silence(samples, RATE) is samples


def test_long_pause_shrinks_to_a_breath():
    samples = _tone(250) + _silence(450) + _tone(250)
    out = shorten_silence(samples, RATE)
    assert out is not samples
    gap = _longest_internal_silence_ms(out)
    assert gap <= KEEP_MS + 30
    assert gap >= 60


def test_pause_after_a_question_keeps_a_short_breath():
    """A stop between two sentences keeps a short breath, not a 0.5s CosyVoice stall."""
    samples = _tone(400) + _silence(500) + _tone(400) + _silence(240) + _tone(300)
    out = shorten_silence(samples, RATE, preserve_stops=True)
    gap = _longest_internal_silence_ms(out)
    assert gap <= STOP_KEEP_MS + 30
    assert gap >= KEEP_MS
    assert has_internal_stop("What kind of dishes, and why? Describe one dish.")
    assert not has_internal_stop("Hi, can we get a table for two, please?")


def test_quiet_clip_is_left_alone():
    samples = array.array("h", [30] * RATE)
    assert shorten_silence(samples, RATE) is samples


def test_tighten_mp3_roundtrip():
    import lameenc

    raw_pcm = _tone(250) + _silence(450) + _tone(250)
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(64)
    encoder.set_in_sample_rate(RATE)
    encoder.set_channels(1)
    encoder.set_quality(2)
    raw = encoder.encode(raw_pcm.tobytes()) + encoder.flush()
    assert _longest_internal_silence_ms(_decode(raw)) >= 350
    tight = tighten_mp3(raw)
    assert tight != raw
    assert _longest_internal_silence_ms(_decode(tight)) <= KEEP_MS + 40
    short = _encode(_tone(200) + _silence(80) + _tone(200))
    assert tighten_mp3(short) is short
    assert tighten_mp3(b"not-an-mp3") == b"not-an-mp3"


def test_gateway_audio_is_tightened_once():
    config.TTS_CACHE_DIR = Path(tempfile.mkdtemp())
    calls = {"n": 0}
    raw = _encode(_tone(200) + _silence(500) + _tone(200))

    async def fake_gateway(text, voice, rate):
        calls["n"] += 1
        return raw

    tts._gateway = fake_gateway
    orig = config.tts_uses_gateway
    config.tts_uses_gateway = lambda: True

    async def run():
        first = await tts.synthesize("Hi there", "en", 0, 1.0, "default")
        second = await tts.synthesize("Hi there", "en", 0, 1.0, "default")
        assert first == second
        assert _longest_internal_silence_ms(_decode(first)) <= KEEP_MS + 40

    try:
        asyncio.run(run())
    finally:
        config.tts_uses_gateway = orig
    assert calls["n"] == 1


def _encode(samples: array.array) -> bytes:
    import lameenc

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(64)
    encoder.set_in_sample_rate(RATE)
    encoder.set_channels(1)
    encoder.set_quality(2)
    return encoder.encode(samples.tobytes()) + encoder.flush()


def _decode(data: bytes) -> array.array:
    from app.tts_silence import _decode_mp3

    samples, _ = _decode_mp3(data)
    return samples


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
