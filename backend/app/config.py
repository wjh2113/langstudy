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
# 朗读用哪家：edge（微软 Edge 免费语音，默认，不耗积分）或 gateway（网关 CosyVoice，按次计费）
TTS_PROVIDER = _env("TTS_PROVIDER", "edge")
# 幂等键请求头：网络重试时带同一个键，网关不会重复扣积分
GATEWAY_IDEMPOTENCY_HEADER = _env("GATEWAY_IDEMPOTENCY_HEADER", "Idempotency-Key")

# ---- AI 调用：超时、每日上限、后台任务 ----
AI_TIMEOUT_SEC = float(_env("AI_TIMEOUT_SEC", "90"))  # 单次大模型调用超时（秒）
STT_TIMEOUT_SEC = float(_env("STT_TIMEOUT_SEC", "20"))  # 单次语音识别超时（秒），最多再重试 1 次
AI_DAILY_LIMIT = int(_env("AI_DAILY_LIMIT", "0") or 0)  # 每个用户每天最多调用大模型几次，0 = 不限（管理员不受限）
JOB_WORKERS = int(_env("JOB_WORKERS", "4") or 4)  # 同时处理出题/评分/笔记的后台线程数

# ---- 防暴力尝试 ----
TRUST_PROXY = _env("TRUST_PROXY", "0") == "1"  # 部署在 Nginx 等反向代理后面时设为 1，用 X-Forwarded-For 识别 IP

# ---- 磁盘 ----
TTS_CACHE_MAX_MB = int(_env("TTS_CACHE_MAX_MB", "500") or 500)  # 朗读缓存上限，超出后清掉最久没用的
AUDIO_RETENTION_DAYS = int(_env("AUDIO_RETENTION_DAYS", "90") or 0)  # 练习录音保留天数，0 = 永久

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
