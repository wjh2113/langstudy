"""Study notes for a practice topic: vocabulary, grammar points and sentence patterns."""
from . import config
from .languages import MODES, get_language
from .llm import LLMError, chat_json

SYSTEM = (
    "你是一名外语老师，为中文母语的学习者整理话题学习笔记。"
    "内容要紧扣给定话题和练习材料，难度符合学习者级别，讲解用中文，例句用目标语言。只输出一个 JSON 对象。"
)

COUNTS = {"beginner": (8, 3, 4), "intermediate": (12, 4, 5), "advanced": (15, 5, 6)}


def material_text(content: dict) -> str:
    """Flatten the practice material into plain text for the prompt."""
    mode = content.get("mode")
    if mode == "article":
        parts = [s["text"] for s in content.get("sentences", [])] + [q["text"] for q in content.get("questions", [])]
    elif mode == "dialogue":
        parts = [f"{l['role']}: {l['text']}" for l in content.get("lines", [])]
    else:
        parts = [q["text"] for q in content.get("questions", [])]
    return "\n".join(parts)[:6000]


def build_prompt(content: dict) -> str:
    language = content.get("language", "en")
    lang = get_language(language)
    level = content.get("level", "intermediate")
    words, grammar, patterns = COUNTS.get(level, COUNTS["intermediate"])
    reading = "日语单词在 reading 写假名读音" if language == "ja" else "英语单词在 reading 写美式音标，如 /ˈmiːtɪŋ/"
    return f"""目标语言：{lang['english_name']}，学习者级别：{lang['levels'].get(level, level)}
话题：{content.get('topic', '')}（练习形式：{MODES.get(content.get('mode'), '')}，标题：{content.get('title', '')}）

练习材料：
{material_text(content)}

请整理这个话题的学习笔记：
- vocabulary：{words} 个单词或短语，优先选材料里出现的，再补充这个话题常用、值得掌握的；{reading}
- grammar：{grammar} 个语法点，结合材料里的句子讲清楚用法和常见错误
- patterns：{patterns} 个这个话题里最实用的句型（带可替换部分，如 "I'm responsible for + 名词/动名词"），学完能直接用在口语里

输出 JSON：
{{
  "summary": "一句话中文说明这个话题要掌握什么",
  "vocabulary": [{{"word": "", "reading": "", "pos": "词性（中文，如 名词）", "meaning": "中文释义", "example": "例句", "exampleTranslation": "例句中文"}}],
  "grammar": [{{"point": "语法点名称", "explanation": "中文讲解（2-3 句）", "examples": [{{"text": "例句", "translation": "中文"}}], "pitfall": "中文：常见错误，没有可留空"}}],
  "patterns": [{{"pattern": "句型", "usage": "中文：什么时候用", "examples": [{{"text": "例句", "translation": "中文"}}]}}]
}}"""


def _s(v) -> str:
    return str(v or "").strip()


def _examples(items) -> list:
    out = []
    for e in items or []:
        if isinstance(e, str) and e.strip():
            out.append({"text": e.strip(), "translation": ""})
        elif isinstance(e, dict) and _s(e.get("text")):
            out.append({"text": _s(e.get("text")), "translation": _s(e.get("translation"))})
    return out[:4]


def normalize(data: dict) -> dict:
    vocab = [
        {k: _s(v.get(k)) for k in ("word", "reading", "pos", "meaning", "example", "exampleTranslation")}
        for v in data.get("vocabulary") or [] if isinstance(v, dict) and _s(v.get("word"))
    ]
    grammar = [
        {"point": _s(g.get("point")), "explanation": _s(g.get("explanation")),
         "examples": _examples(g.get("examples")), "pitfall": _s(g.get("pitfall"))}
        for g in data.get("grammar") or [] if isinstance(g, dict) and _s(g.get("point"))
    ]
    patterns = [
        {"pattern": _s(p.get("pattern")), "usage": _s(p.get("usage")), "examples": _examples(p.get("examples"))}
        for p in data.get("patterns") or [] if isinstance(p, dict) and _s(p.get("pattern"))
    ]
    if not (vocab or grammar or patterns):
        raise LLMError("没有生成学习笔记，请重试")
    return {"summary": _s(data.get("summary")), "vocabulary": vocab[:20], "grammar": grammar[:8], "patterns": patterns[:8]}


def generate_notes(content: dict) -> dict:
    if config.demo_mode():
        from .demo import sample_notes

        return normalize(sample_notes(content.get("language", "en")))
    return normalize(chat_json(SYSTEM, build_prompt(content), temperature=0.5))
