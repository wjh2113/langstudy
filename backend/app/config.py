"""Settings loaded from backend/.env (see .env.example)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

try:  # python-dotenv is optional at import time (tests run without it)
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover
    pass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# ---- AIapiMgr 网关（推荐：生成、语音识别、朗读、发音评测都走网关）----
GATEWAY_URL = _env("GATEWAY_URL", "https://aiapimgrapi.aidigitcloud.cn")
GATEWAY_API_KEY = _env("GATEWAY_API_KEY")
GATEWAY_TENANT = _env("GATEWAY_TENANT", "langstudy")
GATEWAY_CAP_CHAT = _env("GATEWAY_CAP_CHAT", "quality-chat")  # 生成材料、评分
GATEWAY_CAP_FAST = _env("GATEWAY_CAP_FAST", "fast-chat")  # 追问（要快）
GATEWAY_CAP_SPEECH = _env("GATEWAY_CAP_SPEECH", "speech")
GATEWAY_CAP_TTS = _env("GATEWAY_CAP_TTS", "tts")
GATEWAY_CAP_PRONOUNCE = _env("GATEWAY_CAP_PRONOUNCE", "pronunciation")
# 朗读音色（CosyVoice2 预设），对话里 A/B 两个角色依次使用
GATEWAY_TTS_VOICES = [v.strip() for v in _env(
    "GATEWAY_TTS_VOICES", "FunAudioLLM/CosyVoice2-0.5B:anna,FunAudioLLM/CosyVoice2-0.5B:alex"
).split(",") if v.strip()]
# 朗读用哪家：gateway（网关 CosyVoice）或 edge（微软 Edge 免费语音）
TTS_PROVIDER = _env("TTS_PROVIDER", "gateway")

# ---- 大模型（不用网关时的备选：OpenAI 兼容接口：DeepSeek / 通义千问 / Kimi / OpenAI 等）----
LLM_BASE_URL = _env("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_API_KEY = _env("LLM_API_KEY")
LLM_MODEL = _env("LLM_MODEL", "deepseek-chat")
# 部分服务不支持 response_format=json_object，可设为 0 关闭
LLM_JSON_MODE = _env("LLM_JSON_MODE", "1") == "1"

# ---- 服务端语音识别（可选，OpenAI 兼容 /audio/transcriptions）----
STT_BASE_URL = _env("STT_BASE_URL")
STT_API_KEY = _env("STT_API_KEY")
STT_MODEL = _env("STT_MODEL", "whisper-1")

# ---- 语音合成（edge-tts）----
TTS_ENABLED = _env("TTS_ENABLED", "1") == "1"

DB_PATH = DATA_DIR / "langstudy.db"
TTS_CACHE_DIR = DATA_DIR / "tts_cache"
TTS_CACHE_DIR.mkdir(exist_ok=True)


def gateway_enabled() -> bool:
    return bool(GATEWAY_API_KEY)


def demo_mode() -> bool:
    """既没配网关也没配大模型 Key 时使用内置示例内容，方便先体验界面。"""
    return not (GATEWAY_API_KEY or LLM_API_KEY)


def stt_server_enabled() -> bool:
    return gateway_enabled() or bool(STT_BASE_URL and STT_API_KEY)


def tts_uses_gateway() -> bool:
    return gateway_enabled() and TTS_PROVIDER == "gateway"


def model_label() -> str:
    if gateway_enabled():
        return f"网关 · {GATEWAY_CAP_CHAT}"
    return LLM_MODEL
