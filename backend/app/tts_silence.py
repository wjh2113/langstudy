"""Shorten unnatural pauses inside a CosyVoice MP3.

The gateway voice leaves several tenths of a second of silence in the middle of
one sentence. Playback then sounds like it stalls. Collapse only those gaps.
A stop after ? or . is the sentence itself breathing, same as 小树学堂, so that
one stays.
"""
import array
import logging
import math

log = logging.getLogger(__name__)

MAX_GAP_MS = 180
KEEP_MS = 120
# A hole this long, in a line that actually has a sentence break, is the pause
# after that break — not the mid-word stall.
STOP_MS = 360
STOP_CAP_MS = 700
SAMPLE_RATE = 16000


def has_internal_stop(text: str) -> bool:
    """True when a sentence ending sits in the middle, so the voice should pause there."""
    t = " ".join((text or "").split())
    if not t:
        return False
    t = t.rstrip('”"\'』」）)]')
    if t.endswith(("...", "…")):
        t = t.rstrip(".…")
    elif t and t[-1] in "。！？!?；;":
        t = t[:-1]
    elif t.endswith(".") and not t.endswith(".."):
        t = t[:-1]
    return any(ch in t for ch in "。！？!?；") or ". " in t or t.endswith(".")


def tighten_mp3(data: bytes, text: str = "", *, max_gap_ms: int = MAX_GAP_MS, keep_ms: int = KEEP_MS) -> bytes:
    """Return MP3 bytes with mid-sentence silences longer than max_gap_ms cut down to keep_ms.

    A pause at an internal ? . or ! is left in place. Invalid audio, or audio
    that has no long gap, is returned unchanged.
    """
    if not data:
        return data
    try:
        samples, rate = _decode_mp3(data)
        tightened = shorten_silence(samples, rate, max_gap_ms, keep_ms, preserve_stops=has_internal_stop(text))
        if tightened is samples:
            return data
        encoded = _encode_mp3(tightened, rate)
        if len(encoded) < 64:
            return data
        return encoded
    except Exception as e:
        log.warning("tts silence tighten skipped: %s", e)
        return data


def shorten_silence(
    samples: array.array,
    sample_rate: int,
    max_gap_ms: int = MAX_GAP_MS,
    keep_ms: int = KEEP_MS,
    preserve_stops: bool = False,
) -> array.array:
    """Drop the middle of a mid-word silence. Same object if nothing changed."""
    if sample_rate <= 0 or len(samples) < sample_rate // 10:
        return samples
    frame = max(1, sample_rate // 100)  # 10 ms
    rms = []
    for i in range(0, len(samples), frame):
        chunk = samples[i : i + frame]
        acc = 0
        for s in chunk:
            acc += s * s
        rms.append(math.sqrt(acc / len(chunk)))
    loud = [v for v in rms if v >= 200]
    if len(loud) < 5:
        return samples
    loud.sort()
    speech = loud[len(loud) // 2]
    thresh = max(80.0, speech * 0.08)
    silent = [v < thresh for v in rms]
    keep_frames = max(1, round(keep_ms / 10))
    max_frames = max(keep_frames, round(max_gap_ms / 10))
    stop_frames = max(max_frames, round(STOP_MS / 10))
    cap_frames = max(stop_frames, round(STOP_CAP_MS / 10))
    out = array.array("h")
    i = 0
    changed = False
    while i < len(silent):
        if not silent[i]:
            out.extend(samples[i * frame : (i + 1) * frame])
            i += 1
            continue
        j = i
        while j < len(silent) and silent[j]:
            j += 1
        run = j - i
        internal = i > 0 and j < len(silent)
        if preserve_stops and internal and run >= stop_frames:
            take = min(run, cap_frames)
        else:
            take = run if run <= max_frames else keep_frames
        if take < run:
            changed = True
        start = i + (run - take) // 2
        out.extend(samples[start * frame : min(len(samples), (start + take) * frame)])
        i = j
    return out if changed else samples


def _decode_mp3(data: bytes) -> tuple[array.array, int]:
    import miniaudio

    output_format = miniaudio.SampleFormat.SIGNED16
    nchannels = 1
    buf = miniaudio.ffi.from_buffer(data)
    with miniaudio.ffi.new("ma_uint64 *") as frames, miniaudio.ffi.new("void **") as memory:
        decoder_config = miniaudio.lib.ma_decoder_config_init(output_format.value, nchannels, SAMPLE_RATE)
        result = miniaudio.lib.ma_decode_memory(
            buf, len(data), miniaudio.ffi.addressof(decoder_config), frames, memory
        )
        if result != miniaudio.lib.MA_SUCCESS:
            raise RuntimeError(f"mp3 decode failed ({result})")
        samples = array.array("h")
        samples.frombytes(miniaudio.ffi.buffer(memory[0], frames[0] * nchannels * 2))
        miniaudio.lib.ma_free(memory[0], miniaudio.ffi.NULL)
        return samples, SAMPLE_RATE


def _encode_mp3(samples: array.array, sample_rate: int) -> bytes:
    import lameenc

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(64)
    encoder.set_in_sample_rate(sample_rate)
    encoder.set_channels(1)
    encoder.set_quality(2)
    return encoder.encode(samples.tobytes()) + encoder.flush()
