"""Low-level model access (gateway or any OpenAI-compatible API) and JSON parsing/repair.
Feature code calls ai.chat_json, which adds accounting, limits and the parse retry."""
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

        # the client retries connection errors / 5xx itself (same request, nothing billed twice on our side)
        _client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY, timeout=config.AI_TIMEOUT_SEC, max_retries=2)
    return _client


def _close_truncated(text: str) -> str:
    """Close strings/brackets left open when the model output was cut off."""
    stack, in_str, esc = [], False, False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    out = text + ('"' if in_str else "")
    out = re.sub(r",\s*$", "", out.rstrip())
    out = re.sub(r':\s*$', ": null", out)
    return out + "".join(reversed(stack))


def repair_json(text: str) -> str:
    """Fix the usual ways models break JSON, without another (billed) model call."""
    t = text.strip().lstrip("\ufeff")
    t = re.sub(r"^\s*json\s*", "", t, flags=re.I)
    start = t.find("{")
    if start > 0:
        t = t[start:]
    t = re.sub(r"//[^\n\"]*$", "", t, flags=re.M)  # line comments outside strings (best effort)
    t = re.sub(r",(\s*[}\]])", r"\1", t)  # trailing commas
    t = re.sub(r"\bNone\b", "null", t)
    t = re.sub(r"\bTrue\b", "true", t)
    t = re.sub(r"\bFalse\b", "false", t)
    t = _close_truncated(t)
    return re.sub(r",(\s*[}\]])", r"\1", t)


def parse_json(text: str) -> dict:
    """Parse model output into a dict, tolerating ```json fences, leading prose and small breakage."""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)(?:```|$)", text, re.S)
    if fence:
        text = fence.group(1).strip()
    candidates = [text]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    candidates.append(repair_json(text))
    for c in candidates:
        try:
            data = json.loads(c, strict=False)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    raise LLMError("模型返回的内容不是有效的 JSON，请重试")


def raw_chat(system: str, user: str, temperature: float, fast: bool) -> tuple:
    """One completion: (text, usage). Use ai.chat_json instead of calling this directly."""
    if config.gateway_enabled():
        from .gateway import GatewayError, chat_full

        capability = config.GATEWAY_CAP_FAST if fast else config.GATEWAY_CAP_CHAT
        messages = [{"role": "system", "content": system + "\n只输出 JSON，不要用 ``` 包裹，不要任何解释。"},
                    {"role": "user", "content": user}]
        try:
            return chat_full(messages, capability, temperature)
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
    u = getattr(resp, "usage", None)
    usage = {k: getattr(u, k) for k in ("prompt_tokens", "completion_tokens", "total_tokens") if u and getattr(u, k, None) is not None}
    return resp.choices[0].message.content or "", usage
