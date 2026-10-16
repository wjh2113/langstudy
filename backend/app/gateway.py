"""Client for the AIapiMgr LLM gateway (chat, speech-to-text, TTS, pronunciation scoring).

All calls authenticate with the tenant API key; models are chosen by capability
name, never by upstream model id. See 第三方应用接入指南.md.
"""
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


def _post(path: str, what: str, timeout: float, **kwargs) -> httpx.Response:
    try:
        resp = httpx.post(_url(path), timeout=timeout, **kwargs)
    except httpx.HTTPError as e:
        raise GatewayError(f"{what}失败：连不上网关 {config.GATEWAY_URL}（{e}）") from e
    _raise_for(resp, what)
    return resp


def chat(messages: list, capability: str, temperature: float | None = None) -> str:
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
    data = _post("/api/ai/chat", "调用大模型", 120, headers=_headers(), json=body).json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        raise GatewayError("网关返回的对话结果格式不对") from e


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
