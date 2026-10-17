"""Score a finished practice session across listening & speaking dimensions.

Objective signals measured from the learner's speech (speech rate, filler words,
match against the reference text when shadowing, recogniser confidence) are
blended with a language model's judgement of comprehension, grammar,
vocabulary and content. The overall score is computed here, not by the model.
"""
import re
import unicodedata
from difflib import SequenceMatcher

from . import config
from .languages import get_language, MODES
from .ai import chat_json

DIMENSIONS = [
    # key, 中文名, 权重, 说明
    ("listening", "听力理解", 0.20, "是否听懂了材料和问题，回答是否切题"),
    ("pronunciation", "发音清晰度", 0.15, "语音能否被准确识别、与原文的吻合程度"),
    ("fluency", "口语流利度", 0.15, "语速、停顿和口头禅"),
    ("grammar", "语法准确性", 0.15, "句子结构、时态、助词等是否正确"),
    ("vocabulary", "词汇运用", 0.15, "用词是否准确、丰富、地道"),
    ("content", "内容与表达", 0.20, "内容是否充实、有逻辑、完成了任务"),
]
SPEECH_DIMS = {"pronunciation", "fluency"}

_JA_PUNCT = set("、。！？「」『』（）・…，．：；!?,.()\"' 　")


# ---------------------------------------------------------------- text utils
def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def _kata_to_hira(text: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def tokens(text: str, language: str) -> list:
    """Normalised tokens used for matching and counting."""
    text = _nfkc(text).lower()
    if language == "ja":
        return [c for c in _kata_to_hira(text) if not c.isspace() and c not in _JA_PUNCT and unicodedata.category(c)[0] != "P"]
    return re.findall(r"[a-z0-9']+", text)


def count_units(text: str, language: str) -> int:
    return len(tokens(text, language))


def count_fillers(text: str, language: str) -> int:
    fillers = get_language(language)["fillers"]
    t = _nfkc(text).lower()
    if language == "ja":
        return _count_ja_fillers(t, fillers)
    return sum(len(re.findall(r"\b" + re.escape(f) + r"\b", t)) for f in fillers)


def _count_ja_fillers(t: str, fillers: list) -> int:
    # longest-first, remove matches so "あのー" isn't also counted as "あの"
    n = 0
    for f in sorted(fillers, key=len, reverse=True):
        n += t.count(f)
        t = t.replace(f, " ")
    return n


def dictation_correct(answer: str, reference: str, language: str) -> bool:
    """A filled blank counts as right if it matches ignoring case, width, punctuation and kana type."""
    a, r = tokens(answer, language), tokens(reference, language)
    return bool(r) and a == r


def reference_diff(reference: str, spoken: str, language: str) -> dict:
    """Which parts of the reference were (not) heard in the learner's speech."""
    if language == "ja":
        display = list(_nfkc(reference))
        keys = [tokens(c, "ja")[0] if tokens(c, "ja") else None for c in display]
    else:
        display = reference.split()
        keys = [(tokens(w, "en") or [None])[0] for w in display]
    ref_keys = [k for k in keys if k]
    spoken_keys = tokens(spoken, language)
    matcher = SequenceMatcher(a=ref_keys, b=spoken_keys, autojunk=False)
    matched = set()
    for block in matcher.get_matching_blocks():
        matched.update(range(block.a, block.a + block.size))
    out, ki = [], 0
    for d, k in zip(display, keys):
        if k is None:
            out.append({"t": d, "ok": True})
        else:
            out.append({"t": d, "ok": ki in matched})
            ki += 1
    similarity = len(matched) / len(ref_keys) if ref_keys else 0.0
    # penalise lots of extra words as well (ratio uses both sides)
    return {"tokens": out, "similarity": round(min(similarity, matcher.ratio() * 1.15), 3) if ref_keys else 0.0}


# ---------------------------------------------------------- objective scores
def rate_score(rate: float, low: float, high: float) -> float:
    if low <= rate <= high:
        return 100.0
    if rate < low:
        return max(30.0, 100 - (low - rate) / low * 140)
    return max(50.0, 100 - (rate - high) / high * 100)


def turn_metrics(turn: dict, language: str) -> dict:
    m = {"voice": turn.get("input") == "voice"}
    answer = turn.get("answer") or ""
    m["units"] = count_units(answer, language)
    if m["voice"]:
        dur = float(turn.get("durationSec") or 0)
        if dur >= 1.5 and m["units"]:
            m["rate"] = round(m["units"] / (dur / 60), 1)
        m["fillers"] = count_fillers(answer, language)
        conf = turn.get("confidence")
        if isinstance(conf, (int, float)) and 0 < conf <= 1:
            m["confidence"] = float(conf)
        if turn.get("reference") and not turn.get("freeResponse"):
            d = reference_diff(turn["reference"], answer, language)
            m["similarity"] = d["similarity"]
            m["diff"] = d["tokens"]
        pron = turn.get("pronScore")
        if isinstance(pron, (int, float)) and 0 <= pron <= 100:
            m["pron"] = float(pron)  # gateway pronunciation score against the script
    return m


def _avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def objective_scores(turns: list, metrics: list, language: str) -> dict:
    lang = get_language(language)
    low, high = lang["rate_range"]
    voice = [m for m in metrics if m["voice"] and m["units"]]
    res = {"pronunciation": None, "fluency": None, "listening": None, "pronSource": None}
    if voice:
        pron = _avg([m.get("pron") for m in voice])
        sim = _avg([m.get("similarity") for m in voice])
        conf = _avg([m.get("confidence") for m in voice])
        parts = [(sim, 0.75), (conf, 0.25)] if sim is not None else [(conf, 1.0)]
        parts = [(v, w) for v, w in parts if v is not None]
        if pron is not None:
            # real pronunciation assessment beats our recognition-based estimate
            res["pronunciation"], res["pronSource"] = pron, "assessment"
        elif parts:
            res["pronunciation"], res["pronSource"] = sum(v * 100 * w for v, w in parts) / sum(w for _, w in parts), "estimate"
        rates = [m["rate"] for m in voice if "rate" in m]
        total_units = sum(m["units"] for m in voice)
        filler_ratio = sum(m.get("fillers", 0) for m in voice) / max(total_units, 1)
        rs = _avg([rate_score(r, low, high) for r in rates])
        if rs is not None:
            res["fluency"] = max(0.0, rs - min(30.0, filler_ratio * 300))
    plays = [int(t.get("plays") or 0) for t in turns if t.get("kind") != "shadow"]
    hidden = [bool(t.get("textHidden")) for t in turns if t.get("kind") != "shadow"]
    if plays:
        extra = _avg([max(0, p - 1) for p in plays]) or 0
        hidden_share = sum(hidden) / len(hidden)
        res["listening"] = max(40.0, min(100.0, 85 - extra * 8 + hidden_share * 15))
    return res


# ------------------------------------------------------------- LLM judgement
SYSTEM = (
    "你是一名严格但友善的外语口语考官，评价中文母语学习者的听说练习。"
    "学习者的语音回答已由语音识别转成文字，识别错误可能反映发音问题。"
    "评分要客观，分数 0-100（60 及格，80 良好，90 以上接近母语者）。"
    "所有点评、说明用中文；修改后的句子用目标语言。只输出一个 JSON 对象。"
)


def build_eval_prompt(content: dict, turns: list, metrics: list, language: str, level: str) -> str:
    lang = get_language(language)
    lines = [
        f"目标语言：{lang['english_name']}，学习者级别：{lang['levels'].get(level, level)}",
        f"练习形式：{MODES.get(content.get('mode'), '')}，话题：{content.get('topic', '')}，标题：{content.get('title', '')}",
    ]
    lines.append("\n学习者作答记录（index 从 0 开始）：")
    for i, (t, m) in enumerate(zip(turns, metrics)):
        kind = "回答追问" if t.get("followUp") else {"shadow": "跟读", "answer": "回答问题", "line": "角色台词"}.get(t.get("kind"), "作答")
        info = [f"[{i}] 类型：{kind}", f"输入方式：{'语音' if m['voice'] else '文字'}"]
        if t.get("prompt"):
            info.append(f"题目/对方说：{t['prompt']}")
        if t.get("reference"):
            info.append(("参考答案（学习者可自由发挥，不必一致）：" if t.get("freeResponse") else "参考原文：") + t["reference"])
        info.append(f"学习者：{t.get('answer') or '（未作答）'}")
        if "pron" in m:
            info.append(f"发音评测得分：{round(m['pron'])}" + (f"（{t['pronNote']}）" if t.get("pronNote") else ""))
        elif "similarity" in m:
            info.append(f"与原文吻合度：{round(m['similarity'] * 100)}%")
        if "rate" in m:
            info.append(f"语速：{m['rate']} {'词' if lang['unit'] == 'word' else '字'}/分钟")
        if t.get("shadowSync") and t.get("lagSec") is not None:
            info.append(f"影子跟读：比原音晚 {t['lagSec']} 秒开口，用时为原音的 {t.get('durationRatio', '?')} 倍")
        if m.get("fillers"):
            info.append(f"口头禅：{m['fillers']} 次")
        if t.get("kind") != "shadow":
            info.append(f"听了 {t.get('plays', 0)} 遍，{'隐藏文字盲听' if t.get('textHidden') else '看着文字'}")
        lines.append("；".join(info))
    has_voice = any(m["voice"] for m in metrics)
    lines.append(
        """
请输出 JSON：
{
  "scores": {"listening": 0, "pronunciation": 0, "fluency": 0, "grammar": 0, "vocabulary": 0, "content": 0},
  "comments": {"listening": "一句中文点评", "pronunciation": "", "fluency": "", "grammar": "", "vocabulary": "", "content": ""},
  "summary": "2-3 句中文总评",
  "strengths": ["做得好的地方，2-3 条"],
  "improvements": ["最该改进的地方，2-3 条，具体可操作"],
  "items": [{"index": 0, "corrected": "修正错误后的句子", "better": "更自然地道的说法", "notes": "一句中文说明主要问题"}],
  "vocabulary": [{"word": "值得学习的词或短语", "reading": "日语写假名读音，英语留空", "meaning": "中文释义", "example": "例句"}]
}
items 只列出有语法、用词或表达问题的作答（跟读不用列），没问题的不要列；vocabulary 只给 3 个；点评都尽量简短。"""
        + ("" if has_voice else "\n注意：本次全部是文字输入，pronunciation 和 fluency 填 null。")
    )
    return "\n".join(lines)


def _clamp(v):
    try:
        return max(0.0, min(100.0, float(v)))
    except (TypeError, ValueError):
        return None


def combine(llm_scores: dict, obj: dict, has_voice: bool) -> dict:
    # weight of the measured part; a real pronunciation assessment counts for more
    blend = {"pronunciation": 0.85 if obj.get("pronSource") == "assessment" else 0.6, "fluency": 0.5, "listening": 0.3}
    final = {}
    for key, *_ in DIMENSIONS:
        llm_v = _clamp(llm_scores.get(key))
        obj_v = obj.get(key)
        if key in SPEECH_DIMS and not has_voice:
            final[key] = None
        elif obj_v is not None and llm_v is not None:
            w = blend[key]
            final[key] = obj_v * w + llm_v * (1 - w)
        else:
            final[key] = llm_v if llm_v is not None else obj_v
        if final[key] is not None:
            final[key] = round(final[key])
    return final


def overall(final: dict):
    pairs = [(final[k], w) for k, _, w, _ in DIMENSIONS if final.get(k) is not None]
    if not pairs:
        return None
    return round(sum(v * w for v, w in pairs) / sum(w for _, w in pairs))


def _dictation_items(turns: list, language: str):
    items = []
    for t in turns:
        ok = dictation_correct(t.get("answer") or "", t.get("reference") or "", language)
        items.append({
            "key": str(t.get("id") or ""),
            "kind": "dictation", "prompt": t.get("prompt") or "", "reference": t.get("reference") or "",
            "answer": t.get("answer") or "", "input": "text", "correct": ok,
            "corrected": "", "better": "", "notes": "", "metrics": {},
        })
    acc = sum(i["correct"] for i in items) / len(items) if items else None
    return items, acc


def _dictation_only_report(items: list, acc: float, language: str) -> dict:
    score = round(acc * 100)
    dims = []
    for key, name, _, desc in DIMENSIONS:
        if key == "listening":
            dims.append({"key": key, "name": name, "desc": desc, "score": score,
                         "comment": f"填对 {sum(i['correct'] for i in items)} / {len(items)} 个空"})
        else:
            dims.append({"key": key, "name": name, "desc": desc, "score": None, "comment": "本次为精听填空，未评估"})
    wrong = [i for i in items if not i["correct"]]
    lang = get_language(language)
    return {
        "overall": score,
        "dimensions": dims,
        "summary": "全部填对了，听力细节抓得很准！" if not wrong else
                   f"填错了 {len(wrong)} 处。把错的句子多听几遍，注意连读和弱读的地方。",
        "strengths": [], "improvements": [], "items": items, "vocabulary": [],
        "stats": {"turns": len(items), "voiceTurns": 0, "avgRate": None,
                  "rateUnit": "词/分钟" if lang["unit"] == "word" else "字/分钟",
                  "rateRange": list(lang["rate_range"]), "fillers": 0, "pronSource": None,
                  "dictationAccuracy": score},
        "demo": config.demo_mode(),
    }


SHORT_TURNS, SHORT_UNITS = 3, {"en": 120, "ja": 240}


def is_short(turns: list, language: str) -> bool:
    """A small practice (few, short answers) is graded by the fast model."""
    units = sum(count_units(t.get("answer") or "", language) for t in turns)
    return len(turns) <= SHORT_TURNS or units <= SHORT_UNITS.get(language, 120)


def evaluate(content: dict, turns: list) -> dict:
    language = content.get("language", "en")
    level = content.get("level", "intermediate")
    dictation = [t for t in turns if t.get("kind") == "dictation"]  # empty blanks count as wrong
    turns = [t for t in turns if t.get("kind") != "dictation" and (t.get("answer") or "").strip()]
    dict_items, dict_acc = _dictation_items(dictation, language)
    if not turns and dict_items:
        return _dictation_only_report(dict_items, dict_acc, language)
    if not turns:
        raise ValueError("还没有任何作答，先说几句再结束吧")
    metrics = [turn_metrics(t, language) for t in turns]
    has_voice = any(m["voice"] for m in metrics)
    obj = objective_scores(turns, metrics, language)

    if config.demo_mode():
        from .demo import sample_judgement

        judged = sample_judgement(turns, metrics, obj, has_voice)
    else:
        prompt = build_eval_prompt(content, turns, metrics, language, level)
        if dict_acc is not None:
            prompt += f"\n另外，学习者做了精听填空，正确率 {round(dict_acc * 100)}%。"
        judged = chat_json(SYSTEM, prompt, temperature=0.3, fast=is_short(turns, language), task="evaluate")

    final = combine(judged.get("scores") or {}, obj, has_voice)
    if dict_acc is not None:  # blend the dictation result into listening
        base = final.get("listening")
        final["listening"] = round(dict_acc * 100 if base is None else (base + dict_acc * 100) / 2)
    comments = judged.get("comments") or {}
    dims = [
        {
            "key": key,
            "name": name,
            "desc": desc,
            "score": final[key],
            "comment": str(comments.get(key) or "") if final[key] is not None
            else ("录音太短，无法测算" if has_voice else "本次全部为文字输入，未评估"),
        }
        for key, name, _, desc in DIMENSIONS
    ]

    by_index = {}
    for it in judged.get("items") or []:
        if isinstance(it, dict) and isinstance(it.get("index"), int):
            by_index[it["index"]] = it
    items = []
    for i, (t, m) in enumerate(zip(turns, metrics)):
        j = by_index.get(i, {})
        item = {
            "key": str(t.get("id") or ""),
            "kind": t.get("kind"),
            "followUp": bool(t.get("followUp")),
            "prompt": t.get("prompt") or "",
            "reference": t.get("reference") or "",
            "answer": t.get("answer"),
            "input": t.get("input"),
            "corrected": str(j.get("corrected") or ""),
            "better": str(j.get("better") or ""),
            "notes": str(j.get("notes") or ""),
            # graders only list answers with problems; the rest are fine as they are
            "ok": t.get("kind") != "shadow" and i not in by_index,
            "metrics": {k: m[k] for k in ("rate", "fillers", "similarity", "pron") if k in m},
            "audioUrl": str(t.get("audioUrl") or ""),
        }
        if t.get("shadowSync"):
            item["metrics"].update({k: t.get(k) for k in ("lagSec", "durationRatio") if t.get(k) is not None})
        if t.get("pronNote") or t.get("pronIssues"):
            item["pronNote"] = str(t.get("pronNote") or "")
            item["pronIssues"] = [i for i in t.get("pronIssues") or [] if isinstance(i, dict)][:6]
        if "diff" in m:
            item["diff"] = m["diff"]
        items.append(item)
    items.extend(dict_items)

    rates = [m["rate"] for m in metrics if "rate" in m]
    stats = {
        "turns": len(turns),
        "voiceTurns": sum(1 for m in metrics if m["voice"]),
        "avgRate": round(sum(rates) / len(rates)) if rates else None,
        "rateUnit": "词/分钟" if get_language(language)["unit"] == "word" else "字/分钟",
        "rateRange": list(get_language(language)["rate_range"]),
        "fillers": sum(m.get("fillers", 0) for m in metrics),
        "pronSource": obj.get("pronSource"),
        "dictationAccuracy": round(dict_acc * 100) if dict_acc is not None else None,
    }
    return {
        "overall": overall(final),
        "dimensions": dims,
        "summary": str(judged.get("summary") or ""),
        "strengths": [str(s) for s in judged.get("strengths") or []][:5],
        "improvements": [str(s) for s in judged.get("improvements") or []][:5],
        "items": items,
        "vocabulary": [v for v in judged.get("vocabulary") or [] if isinstance(v, dict) and v.get("word")][:8],
        "stats": stats,
        "demo": config.demo_mode(),
    }
