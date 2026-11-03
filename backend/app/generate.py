"""Generate practice material for a topic: article / dialogue / questions /
free chat setup / dictation (cloze). Optionally focused on a weak skill."""
import random
import re

from . import config, demo, notes
from .languages import get_language, MODES
from .ai import chat_json
from .llm import LLMError
from .translate import translate_many

# Model output sometimes splits "Mr. Stein" into two sentences at the title dot.
_TITLE_END = re.compile(r"(?:Mr|Mrs|Ms|Dr|Prof|St|Sr|Jr)\.\s*$", re.I)

from .note_quality import PATTERN_RULE

SYSTEM = (
    PATTERN_RULE +
    "你是一名经验丰富的外语口语与听力教练，为中文母语的学习者编写练习材料。"
    "材料必须自然、地道、贴合真实场景，难度严格符合指定级别。"
    "只输出一个 JSON 对象，不要输出任何其他文字。"
)

SCHEMAS = {
    "article": """{
  "title": "目标语言标题",
  "sentences": [{"text": "目标语言的一句话", "translation": "这句的简体中文"}],
  "questions": [{"text": "关于这篇短文的听力理解问题（目标语言）", "translation": "这个问题的简体中文", "answerHint": "参考答案要点（目标语言，简短）", "modelAnswer": "一句完整的目标语示范回答", "modelAnswerTranslation": "示范回答的简体中文"}]
}
要求：短文正好 %(sentences)s 句，不能少也不能把一句拆成两句凑数，连贯成文，逐句拆分到 sentences（Mr./Mrs./Dr. 等称谓后的点不要当成句号拆开）；questions 共 %(count)s 个，需要听懂短文才能回答，鼓励用完整句子口头作答。""",
    "dialogue": """{
  "title": "目标语言标题",
  "scene": "用中文描述场景（1-2 句）",
  "roles": [{"id": "A", "name": "角色名（目标语言）", "description": "中文说明"}, {"id": "B", "name": "...", "description": "..."}],
  "lines": [{"role": "A", "text": "台词（目标语言）", "translation": "这句台词的简体中文"}]
}
要求：两个角色交替发言，大约 %(lines)s 句台词，可以少 2 到 3 句或多 2 到 3 句，按场景自然收住，不要为了凑数把一句拆成两句。从 A 开始；每句台词口语化、长度适中，适合学习者跟读和角色扮演。""",
    "questions": """{
  "title": "目标语言标题",
  "intro": "用中文简要说明这组问题的场景，例如“你正在参加一场软件工程师面试”",
  "questions": [{"text": "问题（目标语言）", "translation": "这个问题的简体中文", "tip": "中文答题提示：可以从哪些角度回答", "modelAnswer": "一句完整的目标语示范回答", "modelAnswerTranslation": "示范回答的简体中文"}]
}
要求：大约 %(sentences)s 个问题，可以少 2 到 3 个或多 2 到 3 个。按这个场景能自然问到的程度来定，不要为了凑数重复同一个意思。由浅入深，像真实对话那样衔接，每个问题都需要学习者用多句话口头回答。""",
    "chat": """{
  "title": "目标语言标题",
  "scene": "用中文描述场景（1-2 句）",
  "aiRole": {"name": "AI 扮演的角色（目标语言）", "description": "中文说明"},
  "userRole": {"name": "学习者扮演的角色（目标语言）", "description": "中文说明"},
  "goal": "中文：学习者在这次对话里要完成什么（例如“说服面试官你适合这个岗位”）",
  "opening": "AI 的开场白（目标语言，1-2 句，以一个问题结尾）",
  "openingTranslation": "开场白的简体中文"
}
要求：这是开放式自由对话的设定，之后 AI 会根据学习者的回答继续聊。目标要具体，让对话能自然进行大约 %(sentences)s 轮，可以少 2 到 3 轮或多 2 到 3 轮，谈完就可以结束。""",
    "dictation": """{
  "title": "目标语言标题",
  "sentences": [{"text": "目标语言的一句话", "translation": "这句的简体中文", "blanks": ["要挖空的词，必须原样出现在 text 里"]}]
}
要求：短文大约 %(sentences)s 句，可以少 2 到 3 句或多 2 到 3 句，连贯成文，按内容自然收住，不要拆句凑数；每句挑 1-2 个关键词挖空（实词、数字、容易听错的词，不挑冠词和标点），blanks 里的词必须与 text 中的写法完全一致。""",
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

# 短文按这个句数写满。情景对话、话题问答、精听和自由对话可以上下差 3。
PASSAGE_LENGTH = {"beginner": 15, "intermediate": 20, "advanced": 30}


def passage_length(level: str) -> int:
    return PASSAGE_LENGTH.get(level, PASSAGE_LENGTH["intermediate"])


def length_span(level: str) -> tuple[int, int]:
    """目标句数上下可浮动 3。"""
    n = passage_length(level)
    return n - 3, n + 3


def passage_count(mode: str, content: dict) -> int | None:
    if mode in ("article", "dictation"):
        return len(content.get("sentences") or [])
    if mode == "dialogue":
        return len(content.get("lines") or [])
    if mode == "questions":
        return len(content.get("questions") or [])
    return None

AUTO_TOPICS = {
    "en": ["工作面试", "介绍你的家乡", "周末计划", "在餐厅点餐", "旅行中问路", "介绍你的工作", "最近看的一部电影", "健康的生活习惯", "网购退换货", "和同事讨论项目"],
    "ja": ["自我介绍", "周末做了什么", "在便利店购物", "介绍你的家乡", "日企面试", "预约餐厅", "最喜欢的季节", "坐电车问路", "介绍你的爱好", "和同事吃午饭"],
}


def build_prompt(language: str, level: str, mode: str, topic: str, count: int, focus: str = "") -> str:
    lang = get_language(language)
    level_label = lang["levels"].get(level, lang["levels"]["intermediate"])
    length = str(passage_length(level))
    schema = SCHEMAS[mode] % {"count": count, "sentences": length, "lines": length}
    return (
        f"目标语言：{lang['english_name']}（{lang['name']}）\n"
        f"学习者级别：{level_label}\n"
        f"练习形式：{MODES[mode]}\n"
        f"话题：{topic}\n"
        + (f"专项训练：{FOCUS[focus][0]}。{FOCUS[focus][2]}\n" if focus in FOCUS else "")
        + f"\n{_points_hint(language, level)}\n"
        + f"\n练习正文按以下 JSON 结构输出，与 vocabulary、grammar、patterns 合成一个 JSON 对象。"
        f"句子、台词、问题和开场白都要带简体中文，练习时直接显示，不要留空：\n{schema}"
    )


def _points_hint(language: str, level: str) -> str:
    """重点单词、语法和句型。释义用中文，和正文的逐句译文一起生成。"""
    words, grammar, patterns = notes.COUNTS.get(level, notes.COUNTS["intermediate"])
    reading = "日语在 reading 写假名" if language == "ja" else "英语在 reading 写美式音标，如 /ˈmiːtɪŋ/"
    return (
        "请在同一个 JSON 里附上这个练习的重点单词、语法和重点句型（释义、讲解、用法用中文，单词、句型和例句用目标语言）。"
        "不要把它们写进句子、台词或问题。数量可以略少，不要为了凑数硬编。\n"
        f"- vocabulary：大约 {words} 个，优先用材料里出现的，再补这个话题常用的。{reading}。\n"
        f"- grammar：大约 {grammar} 个语法点，结合材料里的句子讲用法和常见错误。\n"
        f"- patterns：大约 {patterns} 个能直接开口用的句型，带可替换部分。\n"
        '{"vocabulary": [{"word": "", "reading": "", "pos": "词性（中文，如 名词）", "meaning": "中文释义", '
        '"example": "例句", "exampleTranslation": "例句中文"}], '
        '"grammar": [{"point": "语法点名称", "explanation": "中文讲解", "examples": [{"text": "例句", "translation": "中文"}], "pitfall": "中文常见错误，没有可留空"}], '
        '"patterns": [{"pattern": "句型", "usage": "中文：什么时候用", "examples": [{"text": "例句", "translation": "中文"}]}]}'
    )


def _str(v) -> str:
    return str(v or "").strip()


def _merge_title_breaks(sentences: list[dict]) -> list[dict]:
    """Join a fragment that ends with Mr./Dr. back onto the next sentence."""
    out: list[dict] = []
    for s in sentences:
        text = _str(s.get("text"))
        if not text:
            continue
        if out and _TITLE_END.search(out[-1]["text"]):
            prev = out[-1]
            joined = {**prev, "text": f"{prev['text'].rstrip()} {text.lstrip()}".strip()}
            # 称谓被拆开时，两段中文也接回同一句。
            tr = " ".join(x for x in (_str(prev.get("translation")), _str(s.get("translation"))) if x)
            if tr:
                joined["translation"] = tr
            out[-1] = joined
            if "blanks" in prev or "blanks" in s:
                blanks = list(prev.get("blanks") or [])
                for b in s.get("blanks") or []:
                    if b and b not in blanks:
                        blanks.append(b)
                out[-1]["blanks"] = blanks
        else:
            out.append(dict(s, text=text))
    return out


def _spoken(item: dict, **fields) -> dict:
    """保留生成时带上的简体中文，练习页直接显示，不再当场翻译。"""
    tr = _str(item.get("translation"))
    if tr:
        fields["translation"] = tr
    return fields


def _question(item: dict, **fields) -> dict:
    """问题附带示范回答，评分和练习页直接用，不再现编。"""
    out = _spoken(item, **fields)
    answer = _str(item.get("modelAnswer"))
    if answer:
        out["modelAnswer"] = answer
    tr = _str(item.get("modelAnswerTranslation"))
    if tr:
        out["modelAnswerTranslation"] = tr
    return out


def normalize(mode: str, data: dict) -> dict:
    """Validate and clean model output so the frontend can rely on the shape."""
    out = {"mode": mode, "title": _str(data.get("title")) or "Practice"}
    if mode == "article":
        out["sentences"] = _merge_title_breaks([
            _spoken(s, text=_str(s.get("text")))
            for s in data.get("sentences") or []
            if isinstance(s, dict) and _str(s.get("text"))
        ])
        out["questions"] = [
            _question(q, text=_str(q.get("text")), answerHint=_str(q.get("answerHint")))
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
            lines.append(_spoken(line, role=role, text=_str(line.get("text"))))
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
        opening_tr = _str(data.get("openingTranslation") or data.get("translation"))
        if opening_tr:
            out["openingTranslation"] = opening_tr
        if not out["opening"]:
            raise LLMError("没有生成开场白，请重试")
    elif mode == "dictation":
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
            sentences.append(_spoken(s, text=text, blanks=blanks[:2]))
        if not any(s["blanks"] for s in sentences):
            raise LLMError("生成的填空内容不完整，请重试")
        out["sentences"] = _merge_title_breaks(sentences)
    elif mode == "questions":
        out["intro"] = _str(data.get("intro"))
        out["questions"] = [
            _question(q, text=_str(q.get("text")), tip=_str(q.get("tip")))
            for q in data.get("questions") or []
            if isinstance(q, dict) and _str(q.get("text"))
        ]
        if not out["questions"]:
            raise LLMError("生成的问题为空，请重试")
    return out


def _key_points(data: dict) -> dict | None:
    """从生成结果里取出重点单词、语法和句型。缺了不让整份练习失败。"""
    if not isinstance(data, dict):
        return None
    raw = {
        "summary": data.get("summary") or "",
        "vocabulary": data.get("vocabulary") or [],
        "grammar": data.get("grammar") or [],
        "patterns": data.get("patterns") or [],
    }
    if not (raw["vocabulary"] or raw["grammar"] or raw["patterns"]):
        return None
    try:
        return notes.normalize(raw)
    except LLMError:
        return None


def _points_ready(points: dict | None) -> bool:
    return bool(points and points.get("vocabulary") and points.get("grammar") and points.get("patterns"))


def _merge_points(primary: dict | None, extra: dict | None) -> dict | None:
    """已有的单词、句型、语法留下，只补空的。"""
    if not primary:
        return extra
    if not extra:
        return primary
    return {
        "summary": primary.get("summary") or extra.get("summary") or "",
        "vocabulary": primary.get("vocabulary") or extra.get("vocabulary") or [],
        "grammar": primary.get("grammar") or extra.get("grammar") or [],
        "patterns": primary.get("patterns") or extra.get("patterns") or [],
    }


def _extend_if_short(mode: str, level: str, prompt: str, content: dict, data: dict) -> tuple[dict, dict]:
    """短文不够目标句数，或其他形式低于下限时，再要一次。更长的那份才留下。"""
    if config.demo_mode():
        return content, data
    got = passage_count(mode, content)
    if mode == "article":
        short = passage_length(level)
        hint = f"上次只有 {got} 句，这次大约 {short} 句。"
        too_short = got is not None and got < short
    elif mode in ("dialogue", "dictation", "questions"):
        low, high = length_span(level)
        unit = "个问题" if mode == "questions" else "句"
        hint = (
            f"上次只有 {got} {unit}，偏少。这次大约 {passage_length(level)}，"
            f"可以在 {low} 到 {high} 之间，按内容自然收住。"
        )
        too_short = got is not None and got < low
    else:
        return content, data
    if not too_short:
        return content, data
    try:
        again_data = chat_json(SYSTEM, prompt + "\n\n" + hint, temperature=0.5, task="generate")
        again = normalize(mode, again_data)
        if (passage_count(mode, again) or 0) > (got or 0):
            return again, again_data
    except LLMError:
        pass
    return content, data


def _attach_translations(content: dict) -> dict:
    """模型漏掉的中文，在保存练习前一次补上，练习过程中不再逐句翻译。"""
    slots = []
    for key in ("sentences", "questions", "lines"):
        for item in content.get(key) or []:
            if isinstance(item, dict) and item.get("text") and not item.get("translation"):
                slots.append((item, "translation", item["text"]))
            if key == "questions" and not config.demo_mode() and isinstance(item, dict) and item.get("modelAnswer") and not item.get("modelAnswerTranslation"):
                slots.append((item, "modelAnswerTranslation", item["modelAnswer"]))
    if content.get("mode") == "chat" and content.get("opening") and not content.get("openingTranslation"):
        slots.append((content, "openingTranslation", content["opening"]))
    if not slots:
        return content
    language = content.get("language") or "en"
    try:
        for start in range(0, len(slots), 40):
            chunk = slots[start:start + 40]
            got = translate_many([text for _, _, text in chunk], language)
            for (item, field, _), tr in zip(chunk, got):
                if tr:
                    item[field] = tr
    except LLMError:
        pass
    return content


def fill_model_answers(content: dict) -> dict:
    """问题缺示范回答时再问一次。已经写好的留下。演示模式用短文里的要点代替。"""
    missing = [
        q for q in content.get("questions") or []
        if isinstance(q, dict) and _str(q.get("text")) and not _str(q.get("modelAnswer"))
    ]
    if not missing:
        return content
    if config.demo_mode():
        for q in missing:
            hint = _str(q.get("answerHint"))
            if hint:
                q["modelAnswer"] = hint
        return content
    lines = []
    for i, q in enumerate(missing, 1):
        extra = _str(q.get("tip")) or _str(q.get("answerHint"))
        lines.append(f"{i}. {q['text']}" + (f"（已有提示：{extra}）" if extra else ""))
    language = content.get("language") or "en"
    prompt = (
        f"目标语言：{get_language(language)['name']}。\n"
        "下面每一题写一句完整、自然的目标语示范回答，并给出简体中文。"
        "这是给学习者参考的，不是唯一正确答案。\n"
        + "\n".join(lines)
        + '\n\n只输出 JSON：{"answers": [{"modelAnswer": "", "modelAnswerTranslation": ""}]}'
        f"\n顺序与题目一致，共 {len(missing)} 条。"
    )
    try:
        data = chat_json(SYSTEM, prompt, temperature=0.4, task="generate")
    except LLMError:
        return content
    answers = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(answers, list):
        return content
    for q, item in zip(missing, answers):
        if not isinstance(item, dict):
            continue
        answer = _str(item.get("modelAnswer"))
        if answer:
            q["modelAnswer"] = answer
        tr = _str(item.get("modelAnswerTranslation"))
        if tr and not q.get("modelAnswerTranslation"):
            q["modelAnswerTranslation"] = tr
    return content


def complete_imported(content: dict, study_notes: dict | None) -> tuple[dict, dict | None]:
    """导入文件里缺译文、示范回答或重点时再补。解析本身不连模型，已有内容保留。"""
    fill_model_answers(content)
    _attach_translations(content)
    if not config.demo_mode() and not _points_ready(study_notes):
        try:
            study_notes = _merge_points(study_notes, notes.generate_notes(content))
        except LLMError:
            pass
    return content, study_notes


def generate_with_notes(language: str, level: str, mode: str, topic: str, count: int = 5, focus: str = "") -> tuple[dict, dict | None]:
    """生成练习正文，并尽量带上重点单词、语法和句型。笔记不放进正文。"""
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
    prompt = build_prompt(language, level, mode, topic, count, focus)
    if config.demo_mode():
        data = demo.sample_content(language, mode, topic)
    else:
        data = chat_json(SYSTEM, prompt, temperature=0.8, task="generate")
    content = normalize(mode, data)
    content, data = _extend_if_short(mode, level, prompt, content, data)
    content.update({"language": language, "level": level, "topic": topic})
    fill_model_answers(content)
    _attach_translations(content)
    if focus:
        content["focus"] = {"key": focus, "name": FOCUS[focus][0]}
    if config.demo_mode():
        points = demo.sample_notes(language)
    else:
        points = _key_points(data)
        # 模型没把单词、语法或句型写全时，再单独整理一份笔记，不改已经生成的正文
        if not _points_ready(points):
            try:
                points = _merge_points(points, notes.generate_notes(content))
            except LLMError:
                pass
    return content, points


def generate(language: str, level: str, mode: str, topic: str, count: int = 5, focus: str = "") -> dict:
    content, _points = generate_with_notes(language, level, mode, topic, count, focus)
    return content
