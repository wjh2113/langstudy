"""Generate practice material for a topic: article / dialogue / questions /
free chat setup / dictation (cloze). Optionally focused on a weak skill."""
import random

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
    "chat": """{
  "title": "目标语言标题",
  "scene": "用中文描述场景（1-2 句）",
  "aiRole": {"name": "AI 扮演的角色（目标语言）", "description": "中文说明"},
  "userRole": {"name": "学习者扮演的角色（目标语言）", "description": "中文说明"},
  "goal": "中文：学习者在这次对话里要完成什么（例如“说服面试官你适合这个岗位”）",
  "opening": "AI 的开场白（目标语言，1-2 句，以一个问题结尾）",
  "openingTranslation": "中文翻译"
}
要求：这是开放式自由对话的设定，之后 AI 会根据学习者的回答继续聊。""",
    "dictation": """{
  "title": "目标语言标题",
  "titleTranslation": "中文标题",
  "sentences": [{"text": "目标语言的一句话", "translation": "中文翻译", "blanks": ["要挖空的词，必须原样出现在 text 里"]}]
}
要求：短文 %(sentences)s 句，连贯成文；每句挑 1-2 个关键词挖空（实词、数字、容易听错的词，不挑冠词和标点），blanks 里的词必须与 text 中的写法完全一致。""",
}

# Weak-skill drills: dimension -> (name, suggested mode, extra instruction for the generator)
FOCUS = {
    "listening": ("听力理解", "dictation", "多用自然口语里的连读、弱读、缩略，信息密度略高，专门练听力细节。"),
    "pronunciation": ("发音清晰度", "article", "句子里多包含容易读错的音（英语如 th、r/l、v/w、长短元音、词尾辅音；日语如长音、促音、拗音、高低音调），适合逐句跟读。"),
    "fluency": ("口语流利度", "questions", "每个问题都要求学习者连续说一分钟左右，比如讲经历、讲步骤、讲一天的安排，练习说长句不停顿。"),
    "grammar": ("语法准确性", "questions", "问题要自然地引导学习者使用过去时、完成时、条件句、比较级、被动语态等常用结构（日语则引导て形、た形、敬语、条件形等）。"),
    "vocabulary": ("词汇运用", "questions", "问题要引导学习者使用这个话题里多样、具体的词汇和固定搭配，避免只用最基础的词。"),
    "content": ("内容与表达", "questions", "问题要求给出观点、理由和例子，练习有条理地表达（先说结论，再说原因和例子）。"),
}

AUTO_TOPICS = {
    "en": ["工作面试", "介绍你的家乡", "周末计划", "在餐厅点餐", "旅行中问路", "介绍你的工作", "最近看的一部电影", "健康的生活习惯", "网购退换货", "和同事讨论项目"],
    "ja": ["自我介绍", "周末做了什么", "在便利店购物", "介绍你的家乡", "日企面试", "预约餐厅", "最喜欢的季节", "坐电车问路", "介绍你的爱好", "和同事吃午饭"],
}


def build_prompt(language: str, level: str, mode: str, topic: str, count: int, focus: str = "") -> str:
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
        f"话题：{topic}\n"
        + (f"专项训练：{FOCUS[focus][0]}。{FOCUS[focus][2]}\n" if focus in FOCUS else "")
        + f"\n请按以下 JSON 结构输出：\n{schema}"
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
    elif mode == "chat":
        out["scene"] = _str(data.get("scene"))
        out["goal"] = _str(data.get("goal"))
        for key, default in (("aiRole", "Partner"), ("userRole", "You")):
            r = data.get(key) if isinstance(data.get(key), dict) else {}
            out[key] = {"name": _str(r.get("name")) or default, "description": _str(r.get("description"))}
        out["opening"] = _str(data.get("opening"))
        out["openingTranslation"] = _str(data.get("openingTranslation"))
        if not out["opening"]:
            raise LLMError("没有生成开场白，请重试")
    elif mode == "dictation":
        out["titleTranslation"] = _str(data.get("titleTranslation"))
        sentences = []
        for s in data.get("sentences") or []:
            if not isinstance(s, dict) or not _str(s.get("text")):
                continue
            text = _str(s.get("text"))
            blanks = []
            for b in s.get("blanks") or []:
                b = _str(b)
                if b and b in text and b not in blanks:  # must appear verbatim to be blanked
                    blanks.append(b)
            sentences.append({"text": text, "translation": _str(s.get("translation")), "blanks": blanks[:2]})
        if not any(s["blanks"] for s in sentences):
            raise LLMError("生成的填空内容不完整，请重试")
        out["sentences"] = sentences
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


def generate(language: str, level: str, mode: str, topic: str, count: int = 5, focus: str = "") -> dict:
    get_language(language)
    focus = focus if focus in FOCUS else ""
    if focus and not mode:
        mode = FOCUS[focus][1]
    if mode not in MODES:
        raise ValueError(f"未知的练习形式：{mode}")
    topic = (topic or "").strip()[:200]
    if not topic:
        if not focus:
            raise ValueError("请输入话题")
        topic = random.choice(AUTO_TOPICS[language])  # weak-skill drill: we pick the topic
    count = max(2, min(int(count or 5), 10))
    if config.demo_mode():
        data = demo.sample_content(language, mode, topic)
    else:
        data = chat_json(SYSTEM, build_prompt(language, level, mode, topic, count, focus), temperature=0.8)
    content = normalize(mode, data)
    content.update({"language": language, "level": level, "topic": topic})
    if focus:
        content["focus"] = {"key": focus, "name": FOCUS[focus][0]}
    return content
