"""Study notes for a practice topic: vocabulary, grammar points and sentence patterns."""
from . import config
from .languages import MODES, get_language
from .ai import chat_json
from .llm import LLMError
from .note_quality import PATTERN_RULE, clean_notes

SYSTEM = (
    "你是一名外语老师，为中文母语的学习者整理话题学习笔记。"
    "内容要紧扣给定话题和练习材料，难度符合学习者级别，讲解用中文，例句用目标语言。只输出一个 JSON 对象。"
)

# 单词、语法、句型。入门 8/5/6，中级 15/10/12，高级 20/12/15。
COUNTS = {"beginner": (8, 5, 6), "intermediate": (15, 10, 12), "advanced": (20, 12, 15)}


def material_text(content: dict) -> str:
    """Flatten the practice material into plain text for the prompt."""
    mode = content.get("mode")
    if mode == "article":
        parts = [s["text"] for s in content.get("sentences", [])] + [q["text"] for q in content.get("questions", [])]
    elif mode == "dialogue":
        parts = [f"{l['role']}: {l['text']}" for l in content.get("lines", [])]
    elif mode == "dictation":
        # 精听没有 questions，单词和句型要对照被挖空的句子
        parts = [s.get("text", "") for s in content.get("sentences", []) if isinstance(s, dict)]
    elif mode == "chat":
        # 自由对话只有场景和开场，笔记仍要扣住这次对话的设定
        parts = [content.get("scene") or "", content.get("goal") or ""]
        for key in ("aiRole", "userRole"):
            role = content.get(key) or {}
            if isinstance(role, dict) and (role.get("name") or role.get("description")):
                parts.append(f"{role.get('name', '')}：{role.get('description', '')}")
        parts.append(content.get("opening") or "")
    else:
        parts = [q["text"] for q in content.get("questions", [])]
    return "\n".join(p for p in parts if p)[:6000]


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

{PATTERN_RULE}

请整理这个话题的学习笔记：
- vocabulary：大约 {words} 个单词或短语，优先选材料里出现的，再补充这个话题常用、值得掌握的；{reading}。可以略少，不要为了凑数硬编
- grammar：大约 {grammar} 个语法点，结合材料里的句子讲清楚用法和常见错误。可以略少
- patterns：大约 {patterns} 个这个话题里最实用的句型（带可替换部分，如 "I'm responsible for + 名词/动名词"），学完能直接用在口语里。可以略少，不要为了凑数硬编

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
    return clean_notes({"summary": _s(data.get("summary")), "vocabulary": vocab, "grammar": grammar, "patterns": patterns})


def generate_notes(content: dict) -> dict:
    if config.demo_mode():
        from .demo import sample_notes

        return normalize(sample_notes(content.get("language", "en")))
    return normalize(chat_json(SYSTEM, build_prompt(content), temperature=0.5, fast=True, task="notes"))
