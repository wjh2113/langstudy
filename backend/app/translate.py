"""On-demand Chinese translation of target-language sentences.

Practice material is generated without translations; a sentence is translated
only when the learner asks (显示翻译 / 盲听揭开). Results are cached in the
database, and all misses in one request go to the fast model in a single call.
"""
import hashlib

from . import config, db
from .languages import get_language
from .ai import chat_json
from .llm import LLMError

MAX_TEXTS = 40
MAX_LEN = 600

SYSTEM = "你是专业翻译，把外语句子译成自然、准确的简体中文。只输出一个 JSON 对象。"


def _key(text: str, language: str) -> str:
    return hashlib.sha1(f"{language}|{text}".encode()).hexdigest()


def _demo_lookup() -> dict:
    from . import demo

    found = {}

    def walk(v):
        if isinstance(v, dict):
            t, tr = v.get("text"), v.get("translation")
            if isinstance(t, str) and isinstance(tr, str) and tr:
                found[t] = tr
            if isinstance(v.get("opening"), str) and v.get("openingTranslation"):
                found[v["opening"]] = v["openingTranslation"]
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            if len(v) == 2 and all(isinstance(x, str) for x in v):
                found[v[0]] = v[1]
            for x in v:
                walk(x)

    walk(demo.SAMPLES)
    walk(demo.DEMO_REPLIES)
    from .followup import DEMO_FOLLOWUPS

    walk(DEMO_FOLLOWUPS)
    return found


def translate_many(texts: list, language: str) -> list:
    get_language(language)
    texts = [str(t or "").strip()[:MAX_LEN] for t in texts][:MAX_TEXTS]
    keys = [_key(t, language) for t in texts]
    cached = db.get_translations(list({k for k, t in zip(keys, texts) if t}))
    missing = list(dict.fromkeys(t for k, t in zip(keys, texts) if t and k not in cached))
    if missing:
        if config.demo_mode():
            table = _demo_lookup()
            fresh = {t: table.get(t, "（演示模式：示例翻译）") for t in missing}
        else:
            lang = get_language(language)
            numbered = "\n".join(f"{i}. {t}" for i, t in enumerate(missing))
            data = chat_json(
                SYSTEM,
                f"把下面 {len(missing)} 句{lang['name']}逐句译成中文，按编号顺序输出：\n{numbered}\n\n"
                '输出 JSON：{"translations": ["第 0 句的中文", "..."]}',
                temperature=0.2, fast=True, task="translate",
            )
            out = data.get("translations") if isinstance(data.get("translations"), list) else []
            if len(out) < len(missing):
                raise LLMError("翻译结果不完整，请重试")
            fresh = {t: str(tr or "").strip() for t, tr in zip(missing, out)}
        db.save_translations([(_key(t, language), language, t, tr) for t, tr in fresh.items() if tr])
        cached.update({_key(t, language): tr for t, tr in fresh.items()})
    return [cached.get(k, "") if t else "" for k, t in zip(keys, texts)]
