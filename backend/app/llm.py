"""Thin wrapper around any OpenAI-compatible chat API that returns JSON."""
import json
import re

from . import config


class LLMError(RuntimeError):
    pass


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY, timeout=120)
    return _client


def parse_json(text: str) -> dict:
    """Parse model output into a dict, tolerating ```json fences or leading prose."""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise LLMError("模型返回的内容不是有效的 JSON，请重试")


def chat_json(system: str, user: str, temperature: float = 0.7, fast: bool = False) -> dict:
    """Ask the model for a JSON object. Goes through the gateway when it is configured."""
    if config.gateway_enabled():
        from .gateway import GatewayError, chat

        capability = config.GATEWAY_CAP_FAST if fast else config.GATEWAY_CAP_CHAT
        messages = [{"role": "system", "content": system + "\n只输出 JSON，不要用 ``` 包裹，不要任何解释。"},
                    {"role": "user", "content": user}]
        try:
            return parse_json(chat(messages, capability, temperature))
        except GatewayError as e:
            raise LLMError(str(e)) from e
    kwargs = dict(
        model=config.LLM_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
    )
    if config.LLM_JSON_MODE:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = _get_client().chat.completions.create(**kwargs)
    except Exception as e:  # network / auth errors from the provider
        raise LLMError(f"调用大模型失败：{e}") from e
    return parse_json(resp.choices[0].message.content)
