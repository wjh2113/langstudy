"""Import practice topics written by another model.

A topic is one Markdown block. A .md file may hold several, split by a line
that starts with "# ". A .zip holds those Markdown files. The prompt below is
what an administrator pastes to the other model so the file comes back in this shape.
"""
import io
import re
import zipfile
from pathlib import Path

from . import notes
from .generate import normalize
from .languages import get_language
from .llm import LLMError

MAX_BYTES = 8 * 1024 * 1024

PROMPT = """你是 LangStudy 的出题编辑。请为中文母语的学习者写成可以导入的练习文件。只输出 Markdown文件，不要解释，不要用代码块把全文包起来。

用户每次会给其中一种材料。

有课件时，以课件为主。课件可能是 PPT、PDF、Word，或粘贴出来的讲义文字。
- 话题、场景、单词、语法、句型、例句、对话和短文，都从这份课件来。
- 课件里已经有的词、句型、语法点优先原样保留。课件写了读音、释义就用课件的；没写读音再补。
- 可以把课件里的长句改短，方便开口，但不要换成课件没教的说法，也不要编课件里没有的语法点。
- 课件有多个课次或单元时，每个课次单独写成一块。
- 课件里没有足够内容支撑某种形式时，不要硬编，只写能从课件里做出来的形式。
- 用户如果另外指定了语言、级别或形式，以用户指定为准；没指定就按课件判断。用户没写级别时每个级别都要生成，没写形式时每个形式都要生成。

没有课件时，用户会给出话题，以及目标语言。目标语言可能是英语、日语，或两种都要。
- 按这个话题编写自然、口语化的练习。用户没写级别时每个级别都要生成，没写形式时每个形式都要生成。
- 只要英语就写语言 en，只要日语就写语言 ja。两种都要时，同一话题写成两块：一块 en，一块 ja。场景对应，句子各自用该语言来写，不要把一种语言的句子塞进另一种。
- 单词、语法、句型按下面的数量写满。

语言用 en（英语）或 ja（日语），级别用 beginner（入门）、intermediate（中级）或 advanced（高级），形式用 questions（话题问答）、dialogue（情景对话）、article（短文）、dictation（精听填空）或 chat（自由对话）。

规则：
- 台词、问题、短文、例句用目标语言，要自然、口语化，难度符合级别。
- 场景、提示、讲解、释义、用法用中文。
- 英语读音写美式音标，日语读音写假名。
- 单词、语法、句型的数量大约是：入门 8 个单词、3 个语法、4 个句型；中级 12 / 6 / 8；高级 15 / 8 / 10。不要超过 20 个单词、10 个语法、20 个句型。有课件时按课件里实际出现的来写，更多时只留这一课最需要开口用的，更少时不要为了凑数去编。没有课件时按这个数量写满。
- 话题问答写 5 个问题。短文：入门 6 到 8 句，中级 8 到 10 句，高级 10 到 12 句，并配 3 个听力问题。情景对话两个角色交替，从 A 开始，入门 8 句、中级 10 句、高级 12 句。精听每句挖 1 到 2 个词，挖空的词必须和句子里的写法完全一样。自由对话只写设定和一句开场白，开场白以问题结尾。
- 同一个话题要几种练习时，每种练习单独写一个以「# 」开头的块，单词、语法、句型可以重复。
- 几个话题可以写在同一个文件里，每个话题都从「# 」另起一块。

每个话题按这个结构写。没有的小节不要写。

# 话题名

语言: en
级别: intermediate
形式: questions

## 场景

用一两句中文说明学习者在什么场合开口。

## 标题

目标语言的标题

## 问题

### 目标语言的问题
提示: 中文，可以从哪些角度回答
参考答案: 短文和精听才需要，写目标语言的简短要点

## 短文

一句一行。句与句之间空一行。

精听改成这样，挖空的词用竖线分开：

### 目标语言的一句话
挖空: word | another

## 角色

### A
名字: 目标语言名字
说明: 中文

### B
名字: 目标语言名字
说明: 中文

自由对话把 A 写成 AI，把 B 写成学习者。

## 台词

### A
目标语言的一句台词

### B
目标语言的一句台词

## 目标

自由对话才写。中文：学习者这次要完成什么。

## 开场

自由对话才写。AI 的开场白，一两句，以问题结尾。

## 单词

### 单词或短语
读音: /ˈmenjuː/
词性: 名词
释义: 中文
例句: 目标语言例句 | 中文翻译

## 语法

### 语法点名称
讲解: 两三句中文
易错: 中文，没有就省略这一行
例句: 目标语言例句 | 中文翻译

## 句型

### Could I have + 名词
用法: 中文，什么时候用
例句: 目标语言例句 | 中文翻译

下面是一份话题问答的样子，只说明格式，不要照抄内容。

# 餐厅点餐

语言: en
级别: intermediate
形式: questions

## 场景

你坐在餐厅里看菜单，准备点一份晚餐。

## 标题

Ordering Dinner

## 问题

### What kind of dishes usually catch your eye first, and why?
提示: 可以说口味、食材或者价格。

### Describe one dish you might order tonight.
提示: 说说名字、味道，以及为什么点它。

## 单词

### menu
读音: /ˈmenjuː/
词性: 名词
释义: 菜单
例句: Could I see the menu? | 我能看一下菜单吗？

## 语法

### would like
讲解: 用 would like 礼貌地说想要什么，比 want 更适合点餐。
易错: 后面直接加名词，不说 I would like to the soup。
例句: I would like the soup. | 我想要汤。

## 句型

### Could I have + 名词
用法: 点餐时礼貌地要一样东西。
例句: Could I have a salad? | 我能要一份沙拉吗？
"""

_MODES = {
    "questions": "questions", "话题问答": "questions", "问答": "questions",
    "dialogue": "dialogue", "情景对话": "dialogue", "对话": "dialogue",
    "article": "article", "短文": "article",
    "dictation": "dictation", "精听填空": "dictation", "填空": "dictation",
    "chat": "chat", "自由对话": "chat",
}
_LANGS = {"en": "en", "english": "en", "英语": "en", "ja": "ja", "jp": "ja", "japanese": "ja", "日语": "ja"}
_LEVELS = {
    "beginner": "beginner", "入门": "beginner",
    "intermediate": "intermediate", "中级": "intermediate",
    "advanced": "advanced", "高级": "advanced",
}
_KEYS = {"读音", "词性", "释义", "例句", "翻译", "提示", "参考答案", "挖空", "名字", "说明", "易错", "讲解", "用法",
         "语言", "级别", "形式"}


def read_upload(filename: str, data: bytes) -> list[str]:
    """Markdown text, or every Markdown file inside a zip."""
    if not data:
        raise LLMError("文件是空的")
    if len(data) > MAX_BYTES:
        raise LLMError("文件超过 8MB")
    name = Path(filename or "").name.lower()
    if name.endswith(".zip"):
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as e:
            raise LLMError("这个压缩包打不开") from e
        texts = []
        for info in zf.infolist():
            if info.is_dir() or info.filename.startswith("__MACOSX") or "/." in info.filename:
                continue
            if not info.filename.lower().endswith((".md", ".markdown")):
                continue
            raw = zf.read(info)
            if len(raw) > MAX_BYTES:
                raise LLMError(f"{Path(info.filename).name} 超过 8MB")
            texts.append(raw.decode("utf-8-sig"))
        if not texts:
            raise LLMError("压缩包里没有 Markdown 文件")
        return texts
    if name.endswith((".md", ".markdown", ".txt")) or not name:
        return [data.decode("utf-8-sig")]
    raise LLMError("请上传 .md 或 .zip")


def parse_documents(texts: list[str]) -> tuple[list[dict], list[str]]:
    """Return ready topics and human-readable errors. A bad topic does not drop the others."""
    ready, errors = [], []
    for text in texts:
        blocks = _topics(text)
        if not blocks:
            errors.append("没有找到以 # 开头的话题")
            continue
        for block in blocks:
            title = _topic_name(block)
            try:
                ready.append(_build(block))
            except (LLMError, ValueError) as e:
                errors.append(f"{title}：{e}")
    return ready, errors


def _topics(text: str) -> list[str]:
    chunks, cur = [], []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith("# ") and not line.startswith("## "):
            if cur:
                chunks.append("\n".join(cur))
            cur = [line]
        elif cur:
            cur.append(line)
    if cur:
        chunks.append("\n".join(cur))
    return [c for c in chunks if c.strip()]


def _topic_name(block: str) -> str:
    return block.splitlines()[0][2:].strip() or "未命名"


def _build(block: str) -> dict:
    lines = block.splitlines()
    topic = lines[0][2:].strip()
    if not topic:
        raise LLMError("话题名是空的")
    sections: dict[str, list[str]] = {"_meta": []}
    current = "_meta"
    for line in lines[1:]:
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        else:
            sections.setdefault(current, []).append(line)
    meta, _ = _fields(sections["_meta"])
    language = _LANGS.get(_one(meta, "语言").lower(), "")
    level = _LEVELS.get(_one(meta, "级别").lower(), "")
    mode = _MODES.get(_one(meta, "形式").lower(), "")
    if language not in ("en", "ja"):
        raise LLMError("语言要写 en 或 ja")
    if not level:
        raise LLMError("级别要写 beginner、intermediate 或 advanced")
    if not mode:
        raise LLMError("形式要写 questions、dialogue、article、dictation 或 chat")
    get_language(language)
    title = _plain(sections.get("标题", [])) or topic
    data = {"title": title}
    if mode == "questions":
        data["intro"] = _plain(sections.get("场景", []))
        data["questions"] = _questions(sections.get("问题", []), "tip")
    elif mode == "article":
        data["sentences"] = [{"text": s} for s in _paragraphs(sections.get("短文", []))]
        data["questions"] = _questions(sections.get("问题", []), "answerHint")
    elif mode == "dictation":
        data["sentences"] = _dictation(sections.get("短文", []))
    elif mode == "dialogue":
        data["scene"] = _plain(sections.get("场景", []))
        data["roles"] = _roles(sections.get("角色", []))
        data["lines"] = _lines(sections.get("台词", []))
    elif mode == "chat":
        data["scene"] = _plain(sections.get("场景", []))
        data["goal"] = _plain(sections.get("目标", []))
        roles = _roles(sections.get("角色", []), chat=True)
        data["aiRole"] = roles[0]
        data["userRole"] = roles[1]
        data["opening"] = _plain(sections.get("开场", []))
    content = normalize(mode, data)
    content.update({"language": language, "level": level, "topic": topic, "mode": mode})
    notes_data = _notes(sections)
    packed = None
    if notes_data:
        packed = notes.normalize(notes_data)
    return {"content": content, "notes": packed}


def _questions(lines: list[str], hint_key: str) -> list[dict]:
    out = []
    for heading, body in _items(lines):
        meta, prose = _fields(body)
        text = heading or " ".join(prose)
        if not text:
            continue
        hint = _one(meta, "参考答案") if hint_key == "answerHint" else _one(meta, "提示")
        if hint_key == "answerHint" and not hint:
            hint = _one(meta, "提示")
        out.append({"text": text, hint_key: hint})
    return out


def _dictation(lines: list[str]) -> list[dict]:
    found = _items(lines)
    if len(found) == 1 and found[0][0] is None:
        return [{"text": s, "blanks": []} for s in _paragraphs(lines)]
    out = []
    for heading, body in found:
        meta, prose = _fields(body)
        text = heading or " ".join(prose)
        blanks = []
        for piece in re.split(r"[|｜、,，]", _one(meta, "挖空")):
            piece = piece.strip()
            if piece and piece in text and piece not in blanks:
                blanks.append(piece)
        if text:
            out.append({"text": text, "blanks": blanks[:2]})
    return out


def _roles(lines: list[str], chat: bool = False) -> list[dict]:
    found = []
    for heading, body in _items(lines):
        meta, _ = _fields(body)
        label = (heading or "").strip()
        name = _one(meta, "名字") or label
        desc = _one(meta, "说明")
        if name:
            found.append({"id": label, "name": name, "description": desc})
    if chat:
        ai = next((r for r in found if r["id"].upper() in {"A", "AI"}), None)
        user = next((r for r in found if r["id"] in {"B", "学习者", "你"}), None)
        return [
            {"name": (ai or {}).get("name") or "Partner", "description": (ai or {}).get("description") or ""},
            {"name": (user or {}).get("name") or "You", "description": (user or {}).get("description") or ""},
        ]
    if len(found) < 2:
        found = [{"id": "A", "name": "A", "description": ""}, {"id": "B", "name": "B", "description": ""}]
    return found[:2]


def _lines(lines: list[str]) -> list[dict]:
    out = []
    for heading, body in _items(lines):
        role = (heading or "").strip().upper()
        text = _plain(body)
        if role in {"A", "B"} and text:
            out.append({"role": role, "text": text})
    return out


def _notes(sections: dict) -> dict | None:
    vocab, grammar, patterns = [], [], []
    for heading, body in _items(sections.get("单词", [])):
        meta, _ = _fields(body)
        example, trans = _bar(_one(meta, "例句"))
        if not trans:
            trans = _one(meta, "翻译")
        if heading:
            vocab.append({
                "word": heading, "reading": _one(meta, "读音"), "pos": _one(meta, "词性"),
                "meaning": _one(meta, "释义"), "example": example, "exampleTranslation": trans,
            })
    for heading, body in _items(sections.get("语法", [])):
        meta, prose = _fields(body)
        if heading:
            grammar.append({
                "point": heading,
                "explanation": _one(meta, "讲解") or " ".join(prose),
                "pitfall": _one(meta, "易错"),
                "examples": _examples(meta.get("例句", [])),
            })
    for heading, body in _items(sections.get("句型", [])):
        meta, _ = _fields(body)
        if heading:
            patterns.append({
                "pattern": heading, "usage": _one(meta, "用法"), "examples": _examples(meta.get("例句", [])),
            })
    if not (vocab or grammar or patterns):
        return None
    return {"summary": "", "vocabulary": vocab, "grammar": grammar, "patterns": patterns}


def _examples(values: list[str]) -> list[dict]:
    out = []
    for value in values:
        text, trans = _bar(value)
        if text:
            out.append({"text": text, "translation": trans})
    return out


def _items(lines: list[str]) -> list[tuple]:
    out: list[tuple] = []
    heading, buf = None, []

    def flush():
        nonlocal heading, buf
        if heading is not None or any(line.strip() for line in buf):
            out.append((heading, buf))
        heading, buf = None, []

    started = False
    for line in lines:
        if line.startswith("### "):
            if started:
                flush()
            heading = line[4:].strip()
            buf = []
            started = True
        elif started or line.strip():
            buf.append(line)
            started = True
    if started:
        flush()
    return out


def _fields(lines: list[str]) -> tuple[dict, list[str]]:
    meta: dict[str, list[str]] = {}
    prose = []
    for line in lines:
        stripped = line.strip().lstrip("-").strip()
        if not stripped:
            continue
        matched = re.match(r"^([^:：]{1,12})[:：]\s*(.*)$", stripped)
        if matched and matched.group(1) in _KEYS:
            meta.setdefault(matched.group(1), []).append(matched.group(2).strip())
        else:
            prose.append(stripped)
    return meta, prose


def _one(meta: dict, key: str) -> str:
    values = meta.get(key) or []
    return values[0].strip() if values else ""


def _plain(lines: list[str]) -> str:
    _, prose = _fields(lines)
    return " ".join(prose).strip()


def _paragraphs(lines: list[str]) -> list[str]:
    text = "\n".join(lines).strip()
    if not text:
        return []
    parts = re.split(r"\n\s*\n", text)
    return [" ".join(part.split()) for part in parts if part.strip()]


def _bar(value: str) -> tuple[str, str]:
    for mark in ("|", "｜"):
        if mark in value:
            left, right = value.split(mark, 1)
            return left.strip(), right.strip()
    return value.strip(), ""
