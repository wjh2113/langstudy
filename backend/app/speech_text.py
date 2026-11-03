"""把一句切成和前端 speechText.ts 相同的小段，提前合成时才能命中播放缓存。"""
import re

_ABBREV = re.compile(r"^(?:Mr|Mrs|Ms|Dr|Prof|St|Sr|Jr|vs|etc|e\.g|i\.e|U\.S|U\.K)\.?$", re.I)
_PHRASE = re.compile(
    r"\s(?=(?:and|but|or|so|because|when|while|where|which|who|whose|if|though|although|after|before|until|since|then|unless|whereas)\b)",
    re.I,
)
_ONLY_PUNCT = re.compile(r"^[。．.!！？?；;、，,\s'’\"”]+$")
_HAS_WORD = re.compile(r"[\w]", re.UNICODE)
_MIN_HEAD = 20
_MIN_TAIL = 12


def split_for_tts(text: str, max_len: int = 120, first_max: int = 60) -> list[str]:
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    if not raw:
        return []
    out: list[str] = []
    cur = ""

    def limit() -> int:
        return first_max if not out else max_len

    def push(piece: str):
        nonlocal cur
        piece = piece.strip()
        if not piece:
            return
        if _ONLY_PUNCT.match(piece):
            if out:
                out[-1] = f"{out[-1]}{piece}".strip()
            else:
                cur = f"{cur}{piece}"
            return
        out.append(piece)

    def phrase_cut(p: str, lim: int) -> int:
        best = -1
        for m in _PHRASE.finditer(p):
            at = m.start() + 1
            if at > lim:
                break
            if at >= _MIN_HEAD and len(p) - at >= _MIN_TAIL:
                best = at
        return best

    for part in _split_marks(raw):
        p = part if cur else part.lstrip()
        while len(p) > limit():
            if cur:
                push(cur)
                cur = ""
                p = p.lstrip()
                continue
            lim = limit()
            comma = max(_last(p, "，", lim), _last(p, ",", lim), _last(p, "、", lim))
            at = comma + 1 if comma >= 12 else lim
            phrase = phrase_cut(p, lim) if comma < 12 else -1
            if phrase > 0:
                at = phrase
            elif comma < 12 and len(p) <= max_len:
                break
            if comma < 12 and phrase <= 0:
                space = _last(p, " ", lim)
                while space >= 12:
                    left = p[:space].strip().split(" ")[-1]
                    if not _ABBREV.match(left):
                        break
                    space = _last(p, " ", space - 1)
                if space >= 12:
                    at = space + 1
            push(p[:at])
            p = p[at:].lstrip()
        if not p:
            continue
        if len(p) > limit() and not cur:
            push(p)
            continue
        if _ONLY_PUNCT.match(p):
            if cur:
                cur += p
            elif out:
                out[-1] = f"{out[-1]}{p}".strip()
            else:
                cur = p
            continue
        if cur and len(cur + p) > limit():
            push(cur)
            cur = p.lstrip()
        else:
            cur += p
    if cur.strip():
        push(cur)
    return [s for s in out if _HAS_WORD.search(s)]


def _last(text: str, ch: str, from_index: int) -> int:
    """与 JavaScript lastIndexOf 一样，from_index 这一位也算。"""
    return text.rfind(ch, 0, from_index + 1)


def _split_marks(text: str) -> list[str]:
    out = []
    start = 0
    for i, ch in enumerate(text):
        if ch in "。！？!?；;":
            out.append(text[start:i + 1])
            start = i + 1
            continue
        if ch == "." and _sentence_dot(text, i):
            out.append(text[start:i + 1])
            start = i + 1
    if start < len(text):
        out.append(text[start:])
    return out or [text]


def _sentence_dot(text: str, i: int) -> bool:
    nxt = text[i + 1] if i + 1 < len(text) else ""
    if nxt and nxt not in " \n":
        return False
    after = text[i + 1:].lstrip()
    if not after:
        return True
    if not re.match(r'^[A-Z“"「]', after):
        return False
    before = text[:i].rstrip()
    word = before.split(" ")[-1] if before else ""
    return not _ABBREV.match(word)
