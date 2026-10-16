"""AI follow-up questions for the Q&A mode: ask one more question based on the learner's answer."""
from . import config
from .languages import get_language
from .llm import chat_json, LLMError

SYSTEM = (
    "你在和一名中文母语的外语学习者进行口语练习，扮演真实场景中的提问者（例如面试官）。"
    "根据学习者刚才的回答，用目标语言提出一个自然的追问。只输出一个 JSON 对象。"
)

DEMO_FOLLOWUPS = {
    "en": ("Interesting. Could you give me a specific example of that?", "有意思。能举一个具体的例子吗？"),
    "ja": ("なるほど。具体的な例を教えていただけますか。", "原来如此。能具体举个例子吗？"),
}


def build_prompt(content: dict, question: str, answer: str, history: list) -> str:
    lang = get_language(content.get("language", "en"))
    level = lang["levels"].get(content.get("level"), content.get("level", ""))
    lines = [
        f"目标语言：{lang['english_name']}，学习者级别：{level}",
        f"话题：{content.get('topic', '')}",
    ]
    if content.get("intro"):
        lines.append(f"场景：{content['intro']}")
    if history:
        lines.append("之前的问答：")
        for h in history[-6:]:
            lines.append(f"- 问：{h.get('q', '')}\n  答：{h.get('a', '')}")
    lines.append(f"\n当前问题：{question}\n学习者的回答：{answer}")
    lines.append(
        """
追问要求：
1. 紧扣学习者回答中的具体内容（提到的经历、观点、细节），像真人那样追问，让对方多说几句；
2. 如果回答太短、跑题或听不懂，就礼貌地请对方展开或澄清；
3. 只问一个问题，一两句话，难度符合学习者级别，不要重复之前问过的问题，不要评价或纠错。

输出 JSON：{"text": "追问（目标语言）", "translation": "中文翻译"}"""
    )
    return "\n".join(lines)


def follow_up(content: dict, question: str, answer: str, history: list | None = None) -> dict:
    question, answer = (question or "").strip(), (answer or "").strip()
    if not question or not answer:
        raise ValueError("需要先回答问题，才能追问")
    language = content.get("language", "en")
    get_language(language)
    if config.demo_mode():
        text, translation = DEMO_FOLLOWUPS[language]
        return {"text": text, "translation": translation}
    data = chat_json(SYSTEM, build_prompt(content, question, answer[:2000], history or []), temperature=0.7, fast=True)
    text = str(data.get("text") or "").strip()
    if not text:
        raise LLMError("没有生成追问，请重试")
    return {"text": text, "translation": str(data.get("translation") or "").strip()}
