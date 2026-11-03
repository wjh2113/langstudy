"""Free conversation: the AI stays in role and replies to whatever the learner says."""
from . import config
from .demo import DEMO_REPLIES
from .languages import get_language
from .ai import chat_json
from .llm import LLMError
from .translate import translate_many

from .generate import length_span, passage_length

# 大约进行这么多轮学习者发言，允许上下差 3 轮；到上限才强制收尾。
def _turn_cap(level: str) -> tuple[int, int]:
    low, high = length_span(level or "intermediate")
    return low, high


RECENT_ROUNDS = 6  # only the latest rounds go to the model verbatim; older ones as a one-line summary
RECENT_MESSAGES = RECENT_ROUNDS * 2

SYSTEM = (
    "你在和一名中文母语的外语学习者进行自由口语对话练习，必须始终保持角色、只用目标语言说话。"
    "每次回复 1-3 句，自然、口语化，难度符合学习者级别；通常以一个问题结尾，让对方继续说。"
    "不要纠错、不要用中文讲解、不要跳出角色。只输出一个 JSON 对象。"
)


def build_prompt(content: dict, history: list, summary: str = "") -> str:
    lang = get_language(content.get("language", "en"))
    user_turns = sum(1 for h in history if h.get("role") == "user")
    lines = [
        f"目标语言：{lang['english_name']}，学习者级别：{lang['levels'].get(content.get('level'), content.get('level', ''))}",
        f"场景：{content.get('scene', '')}",
        f"你的角色：{content['aiRole']['name']}（{content['aiRole'].get('description', '')}）",
        f"学习者的角色：{content['userRole']['name']}（{content['userRole'].get('description', '')}）",
        f"学习者的目标：{content.get('goal', '')}",
    ]
    older = history[:-RECENT_MESSAGES]
    if older:
        lines.append(f"更早的对话摘要：{summary or '（略）'}")
    lines.append("\n最近的对话：" if older else "\n对话记录：")
    for h in history[-RECENT_MESSAGES:]:
        who = "你" if h.get("role") == "ai" else "学习者"
        lines.append(f"{who}：{h.get('text', '')}")
    low, high = _turn_cap(content.get("level") or "intermediate")
    about = passage_length(content.get("level") or "intermediate")
    wrap = user_turns >= high
    # once the next turn will push messages out of the window, ask for a refreshed summary
    need_summary = len(history) + 1 > RECENT_MESSAGES
    lines.append(
        "\n请给出你的下一句回复。"
        + (f"这场对话希望大约进行 {about} 轮。学习者已经说了 {user_turns} 轮。"
           + ("已经到上限了，请自然地收尾告别，end 设为 true。" if wrap else
              f"场景里还有没谈到的具体内容（原因、例子、下一步）就继续问，不要刚开场就结束。"
              f"如果目标已经谈完，可以在 {low} 轮前后自然收尾；不到 {low} 轮时，只有学习者明确要结束才把 end 设为 true，否则为 false。"))
        + ('\n输出 JSON：{"text": "回复（目标语言）", "translation": "这句回复的简体中文", "end": false, "summary": "用一句中文概括到目前为止整段对话的要点"}'
           if need_summary else '\n输出 JSON：{"text": "回复（目标语言）", "translation": "这句回复的简体中文", "end": false}')
    )
    return "\n".join(lines)


def reply(content: dict, history: list, summary: str = "") -> dict:
    if content.get("mode") != "chat":
        raise ValueError("这个练习不是自由对话")
    history = [h for h in history if isinstance(h, dict) and str(h.get("text") or "").strip()]
    if not history or history[-1].get("role") != "user":
        raise ValueError("先说点什么，AI 才能接话")
    language = content.get("language", "en")
    if config.demo_mode():
        replies = DEMO_REPLIES.get(language, DEMO_REPLIES["en"])
        n = sum(1 for h in history if h.get("role") == "user")
        text, translation = replies[min(n - 1, len(replies) - 1)]
        return {"text": text, "translation": translation, "end": n >= len(replies), "summary": ""}
    data = chat_json(SYSTEM, build_prompt(content, history, (summary or "")[:500]), temperature=0.8, fast=True, task="chat")
    text = str(data.get("text") or "").strip()
    if not text:
        raise LLMError("AI 没有回复，请重试")
    translation = str(data.get("translation") or "").strip()
    if not translation:
        try:
            translation = translate_many([text], language)[0]
        except LLMError:
            translation = ""
    return {"text": text, "translation": translation, "end": bool(data.get("end")),
            "summary": str(data.get("summary") or summary or "").strip()[:500]}
