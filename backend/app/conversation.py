"""Free conversation: the AI stays in role and replies to whatever the learner says."""
from . import config
from .demo import DEMO_REPLIES
from .languages import get_language
from .llm import LLMError, chat_json

MAX_USER_TURNS = 12  # wrap the conversation up after this many learner turns

SYSTEM = (
    "你在和一名中文母语的外语学习者进行自由口语对话练习，必须始终保持角色、只用目标语言说话。"
    "每次回复 1-3 句，自然、口语化，难度符合学习者级别；通常以一个问题结尾，让对方继续说。"
    "不要纠错、不要用中文讲解、不要跳出角色。只输出一个 JSON 对象。"
)


def build_prompt(content: dict, history: list) -> str:
    lang = get_language(content.get("language", "en"))
    user_turns = sum(1 for h in history if h.get("role") == "user")
    lines = [
        f"目标语言：{lang['english_name']}，学习者级别：{lang['levels'].get(content.get('level'), content.get('level', ''))}",
        f"场景：{content.get('scene', '')}",
        f"你的角色：{content['aiRole']['name']}（{content['aiRole'].get('description', '')}）",
        f"学习者的角色：{content['userRole']['name']}（{content['userRole'].get('description', '')}）",
        f"学习者的目标：{content.get('goal', '')}",
        "\n对话记录：",
    ]
    for h in history[-20:]:
        who = "你" if h.get("role") == "ai" else "学习者"
        lines.append(f"{who}：{h.get('text', '')}")
    wrap = user_turns >= MAX_USER_TURNS
    lines.append(
        "\n请给出你的下一句回复。"
        + ("对话已经很长了，请自然地收尾告别，end 设为 true。" if wrap else
           "如果对话已经自然结束（比如双方已告别、目标已完成），就简短收尾并把 end 设为 true，否则为 false。")
        + '\n输出 JSON：{"text": "回复（目标语言）", "translation": "中文翻译", "end": false}'
    )
    return "\n".join(lines)


def reply(content: dict, history: list) -> dict:
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
        return {"text": text, "translation": translation, "end": n >= len(replies)}
    data = chat_json(SYSTEM, build_prompt(content, history), temperature=0.8, fast=True)
    text = str(data.get("text") or "").strip()
    if not text:
        raise LLMError("AI 没有回复，请重试")
    return {"text": text, "translation": str(data.get("translation") or "").strip(), "end": bool(data.get("end"))}
