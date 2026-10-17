"""Turn extracted course text into a pack of practices.

One quality-chat call classifies the text. Target-language lines that are not
in the source are dropped, so the model cannot rewrite the worksheet.
"""
import re

from . import config, db
from .ai import chat_json
from .generate import normalize as normalize_mode
from .llm import LLMError
from .notes import normalize as normalize_notes

SYSTEM = (
    "你是课件整理员。把学员上传的课件文字归类，方便做成口语练习。"
    "目标语言的问题、单词、例句、句型、台词必须从原文逐字复制，不得改写、不得翻译、不得补写原文没有的句子。"
    "中文只用于场景说明、词性和释义；释义只有原文里已经写了才填，没有就留空。"
    "只输出一个 JSON 对象。"
)

_SCHEMA = """{
  "title": "原文里的课件标题",
  "topic": "中文话题，8 个字以内",
  "summary": "一句话中文，说明这份课件在练什么",
  "questions": [{"text": "原文中的提问", "tip": "中文答题角度，可空"}],
  "vocabulary": [{"word": "原文单词或短语", "pos": "原文词性标记，可空", "meaning": "原文中的英文或中文释义，没有就空", "example": "原文例句"}],
  "patterns": [{"pattern": "原文中的实用表达或句型", "usage": "中文：什么时候用，可空", "examples": [{"text": "原文例句", "translation": ""}]}],
  "introduce": {"template": "原文中的自我介绍填空模板，多行用换行连在一起"},
  "chat": {"scene": "中文：角色扮演场景，只转述原文", "goal": "中文：对话里要聊到什么", "aiRole": "AI 扮演谁（中文）", "opening": "原文里可以当作开场的一句，没有就空字符串"},
  "dialogue": {"scene": "中文场景", "roles": ["角色名1", "角色名2"], "lines": [{"role": "角色名", "text": "该角色的一句台词，不要带角色名前缀"}]},
  "listening": {"lines": [{"role": "角色名", "text": "被听的那篇对话里的一句台词"}], "questions": [{"text": "理解题原文", "answerHint": "原文里能对上的答案要点，没有就空"}]}
}"""


def build_prompt(text: str) -> str:
    return f"""按下面的方式归类，同一句不要重复放进多个列表，除非原文里它本来就出现了两次。

- 热身提问、每个单词下面的提问、Discussion 讨论题 → questions
- 词汇表里的单词、短语、释义、例句 → vocabulary
- Useful expressions 之类的实用表达 → patterns
- Introduce yourself 这类填空模板 → introduce.template（不要改空格）
- Role play 的场景说明 → chat（opening 只能抄原文里已有的一句，没有就留空）
- 两人对话剧本 → dialogue
- Check your understanding 这类听完对话再回答的题 → listening（lines 用被听的那段对话原文，questions 用理解题原文）

{_SCHEMA}

课件原文：
{text}
"""


def _flat(text: str) -> str:
    return " ".join(str(text or "").split())


def _s(v) -> str:
    return str(v or "").strip()


def _copy(fragment: str, source: str) -> str:
    """Return the fragment only when it already appears in the source."""
    frag = _flat(fragment)
    if len(frag) < 2 or frag.casefold() not in source.casefold():
        return ""
    return frag


def _list(value) -> list:
    return value if isinstance(value, list) else []


def normalize(data: dict, source_text: str) -> dict:
    source = _flat(source_text)
    if not isinstance(data, dict):
        raise LLMError("整理结果不是一份课程")
    questions = []
    for q in _list(data.get("questions"))[:24]:
        if not isinstance(q, dict):
            continue
        text = _copy(q.get("text"), source)
        if text:
            questions.append({"text": text, "tip": _s(q.get("tip"))[:200]})
    vocab = []
    for v in _list(data.get("vocabulary"))[:30]:
        if not isinstance(v, dict):
            continue
        word = _copy(v.get("word"), source)
        if not word:
            continue
        vocab.append({
            "word": word, "reading": "", "pos": _s(v.get("pos"))[:40],
            "meaning": _copy(v.get("meaning"), source), "example": _copy(v.get("example"), source),
            "exampleTranslation": "",
        })
    patterns = []
    for p in _list(data.get("patterns"))[:20]:
        if not isinstance(p, dict):
            continue
        pattern = _copy(p.get("pattern"), source)
        if not pattern:
            continue
        examples = []
        for e in _list(p.get("examples"))[:3]:
            text = _copy(e.get("text") if isinstance(e, dict) else e, source)
            if text:
                examples.append({"text": text, "translation": ""})
        patterns.append({"pattern": pattern, "usage": _s(p.get("usage"))[:200], "examples": examples})
    intro = data.get("introduce") if isinstance(data.get("introduce"), dict) else {}
    template = _copy(intro.get("template"), source)
    chat = data.get("chat") if isinstance(data.get("chat"), dict) else {}
    dialogue = _dialogue(data.get("dialogue"), source)
    listening_src = data.get("listening") if isinstance(data.get("listening"), dict) else {}
    listening_lines = _lines(listening_src.get("lines"), source) or dialogue["lines"]
    listening_qs = []
    for q in _list(listening_src.get("questions"))[:8]:
        if not isinstance(q, dict):
            continue
        text = _copy(q.get("text"), source)
        if text:
            listening_qs.append({"text": text, "answerHint": _copy(q.get("answerHint"), source)})
    title = _copy(data.get("title"), source) or "课程包"
    if not any((questions, vocab, patterns, template, dialogue["lines"], listening_qs)):
        raise LLMError("课件里没有整理出可以练习的原文，请换一份或直接粘贴文字")
    return {
        "title": title[:120],
        "topic": (_s(data.get("topic")) or title)[:80],
        "summary": _s(data.get("summary"))[:200],
        "questions": questions,
        "vocabulary": vocab,
        "patterns": patterns,
        "template": template,
        "chat": {
            "scene": _s(chat.get("scene"))[:300],
            "goal": _s(chat.get("goal"))[:200],
            "aiRole": _s(chat.get("aiRole"))[:40] or "对话伙伴",
            "opening": _copy(chat.get("opening"), source),
        },
        "dialogue": dialogue,
        "listeningLines": listening_lines,
        "listeningQuestions": listening_qs,
    }


def _lines(raw, source: str) -> list:
    out = []
    for line in _list(raw)[:40]:
        if not isinstance(line, dict):
            continue
        text = _copy(line.get("text"), source)
        role = _s(line.get("role")) or "A"
        if text:
            out.append({"role": role[:40], "text": text})
    return out


def _dialogue(raw, source: str) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    roles = [_s(r) for r in _list(raw.get("roles")) if _s(r)][:2]
    lines = _lines(raw.get("lines"), source)
    # "Matt: Hi there" sometimes comes back as one string. Split a leading name once.
    cleaned = []
    for line in lines:
        m = re.match(r"^([A-Za-z][A-Za-z .'-]{0,30}):\s+(.+)$", line["text"])
        if m and _copy(m.group(2), source):
            cleaned.append({"role": m.group(1).strip(), "text": _copy(m.group(2), source)})
        else:
            cleaned.append(line)
    names = []
    for line in cleaned:
        if line["role"] not in names:
            names.append(line["role"])
    if len(roles) < 2:
        roles = names[:2]
    return {"scene": _s(raw.get("scene"))[:300], "roles": roles[:2], "lines": cleaned}


def _blank_for(example: str, word: str) -> str:
    match = re.search(re.escape(word), example, re.IGNORECASE)
    return match.group(0) if match else ""


def _base(pack: dict, language: str, level: str) -> dict:
    return {"language": language, "level": level, "topic": pack["topic"]}


def activities(pack: dict, language: str, level: str) -> list:
    """Practice sessions to create, in the order a learner would meet them in class."""
    base = _base(pack, language, level)
    out = []
    if pack["questions"]:
        content = normalize_mode("questions", {
            "title": "话题问答",
            "intro": "下面的问题来自课件原文。答完后可以让 AI 再追问一句。",
            "questions": pack["questions"],
        })
        content.update(base)
        out.append(("questions", "话题问答", "热身、单词下面的提问和讨论题都用原文，答完可以让 AI 追问。", content))
    examples = []
    for v in pack["vocabulary"]:
        blank = _blank_for(v["example"], v["word"]) if v["example"] else ""
        if blank:
            examples.append({"text": v["example"], "blanks": [blank]})
    if examples:
        content = normalize_mode("dictation", {"title": "精听填空", "sentences": examples})
        content.update(base)
        out.append(("dictation", "精听填空", "用词汇表里的例句挖空关键词，先听再填。", content))
    opening = pack["chat"]["opening"]
    if not opening and pack["dialogue"]["lines"]:
        opening = pack["dialogue"]["lines"][0]["text"]
    if pack["chat"]["scene"] and opening:
        content = normalize_mode("chat", {
            "title": "自由对话",
            "scene": pack["chat"]["scene"],
            "goal": pack["chat"]["goal"] or "按课件里的场景聊下去",
            "aiRole": {"name": pack["chat"]["aiRole"], "description": pack["chat"]["scene"]},
            "userRole": {"name": "You", "description": "你自己"},
            "opening": opening,
        })
        content.update(base)
        out.append(("chat", "自由对话", "AI 按课件里的角色扮演场景和你聊，开场用的是原文里的一句。", content))
    if len(pack["dialogue"]["lines"]) >= 2 and len(pack["dialogue"]["roles"]) >= 2:
        a, b = pack["dialogue"]["roles"][:2]
        content = normalize_mode("dialogue", {
            "title": "情景对话",
            "scene": pack["dialogue"]["scene"] or "用课件原文台词分角色练习。",
            "roles": [{"id": a, "name": a, "description": ""}, {"id": b, "name": b, "description": ""}],
            "lines": pack["dialogue"]["lines"],
        })
        content.update(base)
        names = " 或 ".join(r["name"] for r in content["roles"])
        out.append(("dialogue", "情景对话", f"台词是原文。选 {names} 来演。", content))
    if pack["listeningLines"] and pack["listeningQuestions"]:
        spoken = [f"{ln['role']}: {ln['text']}" if ln["role"] else ln["text"] for ln in pack["listeningLines"]]
        content = normalize_mode("article", {
            "title": "听后回答",
            "sentences": [{"text": s} for s in spoken],
            "questions": pack["listeningQuestions"],
        })
        content.update(base)
        out.append(("listening", "听后回答", "先点「播放全文」把对话听完，再口头回答这几道理解题。", content))
    if pack["template"]:
        content = normalize_mode("questions", {
            "title": "用这个句型介绍你自己",
            "intro": "用课件里的填空句型介绍你自己，把空格换成你的情况，并展开说一两句。",
            "questions": [{"text": pack["template"], "tip": "用这个句型介绍你自己"}],
        })
        content.update(base)
        out.append(("introduce", "口语题", "用课件里的填空模板介绍你自己。", content))
    notes = None
    if pack["vocabulary"] or pack["patterns"]:
        notes = normalize_notes({
            "summary": pack["summary"],
            "vocabulary": pack["vocabulary"],
            "grammar": [],
            "patterns": pack["patterns"],
        })
    return _with_notes(out, notes)


def _with_notes(items: list, notes: dict | None) -> list:
    """Notes ride on the topic Q&A session when there is one, and show as their own step."""
    if not notes or not items:
        return [(k, t, b, c, None) for k, t, b, c in items]
    host = 0
    for i, (kind, *_) in enumerate(items):
        if kind == "questions":
            host = i
            break
    out = []
    for i, (kind, title, blurb, content) in enumerate(items):
        out.append((kind, title, blurb, content, notes if i == host else None))
        if i == host:
            out.append(("notes", "学习笔记", "词汇和实用表达已按原文整理好，不用再生成。单词可以一键加入生词本。", None, None))
    return out


def classify(text: str) -> dict:
    if config.demo_mode():
        questions = [{"text": _flat(ln), "tip": ""} for ln in text.splitlines() if ln.strip().endswith("?")]
        return {"title": "上传的资料", "topic": "上传的资料", "questions": questions[:12]}
    return chat_json(SYSTEM, build_prompt(text[:24000]), temperature=0.2, fast=False, task="course")


def save_course(user_id: int, language: str, level: str, source_name: str, source_text: str, data: dict) -> dict:
    pack = normalize(data, source_text)
    steps = activities(pack, language, level)
    if not any(content for *_, content, _notes in steps):
        raise LLMError("课件里没有整理出可以练习的原文，请换一份或直接粘贴文字")
    items = []
    notes_sid = None
    for kind, title, blurb, content, notes in steps:
        if content is None:
            items.append({"key": kind, "kind": kind, "title": title, "blurb": blurb, "sessionId": ""})
            continue
        if notes:
            content["notesLocked"] = True
        sid = db.create_session(content, user_id)
        if notes:
            db.save_notes(sid, notes)
            notes_sid = sid
        items.append({"key": kind, "kind": kind, "title": title, "blurb": blurb, "sessionId": sid})
    for item in items:
        if item["kind"] == "notes":
            item["sessionId"] = notes_sid or ""
    course_id = db.create_course(user_id, pack["title"], pack["topic"], language, source_name, items)
    return {"id": course_id, "title": pack["title"], "topic": pack["topic"]}
