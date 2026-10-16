"""Generate practice material (article / dialogue / questions) for a topic."""
from . import config, demo
from .languages import get_language, MODES
from .llm import chat_json, LLMError

SYSTEM = (
    "你是一名经验丰富的外语口语与听力教练，为中文母语的学习者编写练习材料。"
    "材料必须自然、地道、贴合真实场景，难度严格符合指定级别。"
    "只输出一个 JSON 对象，不要输出任何其他文字。"
)

SCHEMAS = {
    "article": """{
  "title": "目标语言标题",
  "titleTranslation": "中文标题",
  "sentences": [{"text": "目标语言的一句话", "translation": "中文翻译"}],
  "questions": [{"text": "关于这篇短文的听力理解问题（目标语言）", "translation": "中文翻译", "answerHint": "参考答案要点（目标语言，简短）"}]
}
要求：短文 %(sentences)s 句，连贯成文，逐句拆分到 sentences；questions 共 %(count)s 个，需要听懂短文才能回答，鼓励用完整句子口头作答。""",
    "dialogue": """{
  "title": "目标语言标题",
  "scene": "用中文描述场景（1-2 句）",
  "roles": [{"id": "A", "name": "角色名（目标语言）", "description": "中文说明"}, {"id": "B", "name": "...", "description": "..."}],
  "lines": [{"role": "A", "text": "台词（目标语言）", "translation": "中文翻译"}]
}
要求：两个角色交替发言，共 %(lines)s 句台词，从 A 开始；每句台词口语化、长度适中，适合学习者跟读和角色扮演。""",
    "questions": """{
  "title": "目标语言标题",
  "intro": "用中文简要说明这组问题的场景，例如“你正在参加一场软件工程师面试”",
  "questions": [{"text": "问题（目标语言）", "translation": "中文翻译", "tip": "中文答题提示：可以从哪些角度回答"}]
}
要求：共 %(count)s 个问题，由浅入深，像真实的对话/面试那样自然衔接，每个问题都需要学习者用多句话口头回答。""",
}


def build_prompt(language: str, level: str, mode: str, topic: str, count: int) -> str:
    lang = get_language(language)
    level_label = lang["levels"].get(level, lang["levels"]["intermediate"])
    schema = SCHEMAS[mode] % {
        "count": count,
        "sentences": {"beginner": "6-8", "intermediate": "8-10", "advanced": "10-12"}.get(level, "8-10"),
        "lines": {"beginner": "8", "intermediate": "10", "advanced": "12"}.get(level, "10"),
    }
    return (
        f"目标语言：{lang['english_name']}（{lang['name']}）\n"
        f"学习者级别：{level_label}\n"
        f"练习形式：{MODES[mode]}\n"
        f"话题：{topic}\n\n"
        f"请按以下 JSON 结构输出：\n{schema}"
    )


def _str(v) -> str:
    return str(v or "").strip()


def normalize(mode: str, data: dict) -> dict:
    """Validate and clean model output so the frontend can rely on the shape."""
    out = {"mode": mode, "title": _str(data.get("title")) or "Practice"}
    if mode == "article":
        out["titleTranslation"] = _str(data.get("titleTranslation"))
        out["sentences"] = [
            {"text": _str(s.get("text")), "translation": _str(s.get("translation"))}
            for s in data.get("sentences") or []
            if isinstance(s, dict) and _str(s.get("text"))
        ]
        out["questions"] = [
            {"text": _str(q.get("text")), "translation": _str(q.get("translation")), "answerHint": _str(q.get("answerHint"))}
            for q in data.get("questions") or []
            if isinstance(q, dict) and _str(q.get("text"))
        ]
        if not out["sentences"] or not out["questions"]:
            raise LLMError("生成的短文内容不完整，请重试")
    elif mode == "dialogue":
        out["scene"] = _str(data.get("scene"))
        roles = [r for r in data.get("roles") or [] if isinstance(r, dict)]
        if len(roles) < 2:
            roles = [{"id": "A", "name": "A"}, {"id": "B", "name": "B"}]
        out["roles"] = [
            {"id": ["A", "B"][i], "name": _str(r.get("name")) or ["A", "B"][i], "description": _str(r.get("description"))}
            for i, r in enumerate(roles[:2])
        ]
        orig_ids = [_str(r.get("id")) for r in roles[:2]]
        lines = []
        for i, line in enumerate(data.get("lines") or []):
            if not isinstance(line, dict) or not _str(line.get("text")):
                continue
            role = _str(line.get("role"))
            if role in orig_ids:
                role = ["A", "B"][orig_ids.index(role)]
            if role not in ("A", "B"):
                role = "A" if len(lines) % 2 == 0 else "B"
            lines.append({"role": role, "text": _str(line.get("text")), "translation": _str(line.get("translation"))})
        if len(lines) < 2:
            raise LLMError("生成的对话内容不完整，请重试")
        out["lines"] = lines
    elif mode == "questions":
        out["intro"] = _str(data.get("intro"))
        out["questions"] = [
            {"text": _str(q.get("text")), "translation": _str(q.get("translation")), "tip": _str(q.get("tip"))}
            for q in data.get("questions") or []
            if isinstance(q, dict) and _str(q.get("text"))
        ]
        if not out["questions"]:
            raise LLMError("生成的问题为空，请重试")
    return out


def generate(language: str, level: str, mode: str, topic: str, count: int = 5) -> dict:
    get_language(language)
    if mode not in MODES:
        raise ValueError(f"未知的练习形式：{mode}")
    topic = topic.strip()[:200]
    if not topic:
        raise ValueError("请输入话题")
    count = max(2, min(int(count or 5), 10))
    if config.demo_mode():
        data = demo.sample_content(language, mode, topic)
    else:
        data = chat_json(SYSTEM, build_prompt(language, level, mode, topic, count), temperature=0.8)
    content = normalize(mode, data)
    content.update({"language": language, "level": level, "topic": topic})
    return content
