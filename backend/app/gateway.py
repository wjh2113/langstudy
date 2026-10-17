"""Client for the AIapiMgr LLM gateway (chat, speech-to-text, TTS, pronunciation scoring).

All calls authenticate with the tenant API key; models are chosen by capability
name, never by upstream model id. See 第三方应用接入指南.md.
"""
import time
import uuid

import httpx

from . import config


class GatewayError(RuntimeError):
    pass


# Messages for the gateway's documented error codes
_ERRORS = {
    401: "网关 API Key 无效或租户已停用，请检查 backend/.env 里的 GATEWAY_API_KEY",
    402: "网关积分不足，请在管理台给租户 langstudy 充值",
    403: "网关拒绝了请求（数据级别超限，或本机 IP 不在租户白名单里）",
    404: "网关不认识这个能力名（capability），请核对 .env 中的能力配置",
    503: "网关当前没有可用的上游通道，请联系管理员检查路由",
}


def _headers(json_body: bool = True) -> dict:
    h = {"Authorization": f"Bearer {config.GATEWAY_API_KEY}"}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


# Transient failures worth retrying. The retry reuses the same idempotency key, so a
# request the gateway already completed (and charged) is not charged a second time.
_RETRY_STATUS = {502, 503, 504}
RETRIES = 2


def _url(path: str) -> str:
    return config.GATEWAY_URL.rstrip("/") + path


def _raise_for(resp: httpx.Response, what: str):
    if resp.status_code < 400:
        return
    detail = ""
    try:
        body = resp.json()
        detail = body.get("detail") or body.get("message") or ""
        if not isinstance(detail, str):
            detail = str(detail)
    except ValueError:
        detail = resp.text[:200]
    hint = _ERRORS.get(resp.status_code, "")
    raise GatewayError(f"{what}失败（{resp.status_code}）：{hint or detail}" + (f"（{detail}）" if hint and detail else ""))


def _post(path: str, what: str, timeout: float, headers: dict, **kwargs) -> httpx.Response:
    headers = {**headers, config.GATEWAY_IDEMPOTENCY_HEADER: uuid.uuid4().hex}
    for attempt in range(RETRIES + 1):
        last = attempt == RETRIES
        try:
            resp = httpx.post(_url(path), timeout=timeout, headers=headers, **kwargs)
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            if last:
                raise GatewayError(f"{what}失败：连不上网关 {config.GATEWAY_URL}（{e}）") from e
        except httpx.HTTPError as e:
            raise GatewayError(f"{what}失败：连不上网关 {config.GATEWAY_URL}（{e}）") from e
        else:
            if resp.status_code not in _RETRY_STATUS or last:
                _raise_for(resp, what)
                return resp
        time.sleep(0.8 * (attempt + 1))
    raise GatewayError(f"{what}失败")  # pragma: no cover


def usage_of(resp: httpx.Response, data=None) -> dict:
    """Tokens and credits charged, from the response body (`usage`) or billing headers, when present."""
    out = {}
    u = data.get("usage") if isinstance(data, dict) and isinstance(data.get("usage"), dict) else {}
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if isinstance(u.get(k), (int, float)):
            out[k] = int(u[k])
    for k in ("credits", "cost", "points"):
        v = u.get(k, data.get(k) if isinstance(data, dict) else None)
        if isinstance(v, (int, float)):
            out["credits"] = float(v)
            break
    headers = getattr(resp, "headers", {}) or {}
    for h in ("x-credits-charged", "x-credits-used", "x-points-charged", "x-billing-credits"):
        try:
            if h in headers:
                out["credits"] = float(headers[h])
                break
        except (TypeError, ValueError):
            pass
    return out


def chat_full(messages: list, capability: str, temperature: float | None = None,
              timeout: float | None = None) -> tuple:
    """(reply text, usage) for a chat completion."""
    body = {
        "tenantId": config.GATEWAY_TENANT,
        "capability": capability,
        "messages": messages,
        "dataClass": "internal",
        "fallback": True,
        "stream": False,
    }
    if temperature is not None:
        body["temperature"] = temperature
    resp = _post("/api/ai/chat", "调用大模型", timeout or config.AI_TIMEOUT_SEC, headers=_headers(), json=body)
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"] or "", usage_of(resp, data)
    except (KeyError, IndexError, TypeError) as e:
        raise GatewayError("网关返回的对话结果格式不对") from e


def chat(messages: list, capability: str, temperature: float | None = None) -> str:
    return chat_full(messages, capability, temperature)[0]


def transcribe(audio: bytes, filename: str, mime: str, language: str) -> str:
    data = _post(
        "/api/ai/transcribe", "语音识别", 90,
        headers=_headers(json_body=False),
        files={"file": (filename, audio, mime or "application/octet-stream")},
        data={"capability": config.GATEWAY_CAP_SPEECH, "language": language, "dataClass": "internal",
              "fallback": "true", "tenantId": config.GATEWAY_TENANT},
    ).json()
    return (data.get("text") or "").strip()


def tts(text: str, voice: str | None, speed: float) -> bytes:
    body = {
        "tenantId": config.GATEWAY_TENANT,
        "capability": config.GATEWAY_CAP_TTS,
        "input": text,
        "response_format": "mp3",
        "speed": speed,
        "dataClass": "internal",
        "fallback": True,
    }
    if voice:
        body["voice"] = voice
    resp = _post("/api/ai/tts", "语音合成", 90, headers=_headers(), json=body)
    if "json" in resp.headers.get("content-type", ""):
        raise GatewayError("语音合成返回了 JSON 而不是音频")
    if not resp.content:
        raise GatewayError("语音合成没有返回音频")
    return resp.content


def pronounce(audio: bytes, filename: str, mime: str, text: str, language: str) -> dict:
    """Score pronunciation of a recording against the script it was reading."""
    data = _post(
        "/api/ai/pronounce", "发音评测", 90,
        headers=_headers(json_body=False),
        files={"file": (filename, audio, mime or "application/octet-stream")},
        data={"capability": config.GATEWAY_CAP_PRONOUNCE, "text": text, "language": language,
              "dataClass": "internal", "fallback": "true", "tenantId": config.GATEWAY_TENANT},
    ).json()
    score = data.get("score")
    return {
        "score": float(score) if isinstance(score, (int, float)) else None,
        "transcript": data.get("transcript") or "",
        "issues": [i for i in data.get("issues") or [] if isinstance(i, dict)][:10],
        "note": data.get("note") or "",
    }
