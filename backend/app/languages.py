"""Per-language metadata. Add a new language by adding an entry here."""

LANGUAGES = {
    "en": {
        "name": "英语",
        "english_name": "English",
        "stt_locale": "en-US",
        "voices": ["en-US-AriaNeural", "en-US-GuyNeural"],
        "levels": {
            "beginner": "入门 (CEFR A2)",
            "intermediate": "中级 (CEFR B1-B2)",
            "advanced": "高级 (CEFR C1)",
        },
        "fillers": ["um", "uh", "er", "erm", "hmm", "you know"],
        "unit": "word",  # speech rate measured in words / minute
        "rate_range": (100, 170),  # comfortable conversational rate for a learner
    },
    "ja": {
        "name": "日语",
        "english_name": "Japanese",
        "stt_locale": "ja-JP",
        "voices": ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"],
        "levels": {
            "beginner": "入门 (JLPT N5-N4)",
            "intermediate": "中级 (JLPT N3)",
            "advanced": "高级 (JLPT N2-N1)",
        },
        "fillers": ["えー", "ええと", "えっと", "あの", "あのー", "うーん", "えーと"],
        "unit": "char",  # characters / minute
        "rate_range": (200, 360),
    },
}

# Listening accents. "default" uses the configured TTS (gateway or edge); the others
# always use Microsoft Edge voices. Accents marked simulated=True are produced by a
# native voice of that country reading the target language (e.g. a Japanese voice
# reading English), which gives a believable foreign accent but is not a real recording.
#   key: (中文名, 地区分组, [女声, 男声], 浏览器兜底 locale, simulated)
ACCENTS = {
    "en": {
        "default": ("默认音色", "", None, "en-US", False),
        "us": ("美国", "美洲", ["en-US-AriaNeural", "en-US-GuyNeural"], "en-US", False),
        "ca": ("加拿大", "美洲", ["en-CA-ClaraNeural", "en-CA-LiamNeural"], "en-CA", False),
        "latam": ("拉美口音", "美洲", ["es-MX-DaliaNeural", "es-MX-JorgeNeural"], "es-MX", True),
        "gb": ("英国", "欧洲", ["en-GB-SoniaNeural", "en-GB-RyanNeural"], "en-GB", False),
        "ie": ("爱尔兰", "欧洲", ["en-IE-EmilyNeural", "en-IE-ConnorNeural"], "en-IE", False),
        "de": ("德国口音", "欧洲", ["de-DE-KatjaNeural", "de-DE-ConradNeural"], "de-DE", True),
        "fr": ("法国口音", "欧洲", ["fr-FR-DeniseNeural", "fr-FR-HenriNeural"], "fr-FR", True),
        "in": ("印度", "亚洲", ["en-IN-NeerjaNeural", "en-IN-PrabhatNeural"], "en-IN", False),
        "sg": ("新加坡", "亚洲", ["en-SG-LunaNeural", "en-SG-WayneNeural"], "en-SG", False),
        "jp": ("日本口音", "亚洲", ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"], "ja-JP", True),
        "au": ("澳大利亚", "大洋洲", ["en-AU-NatashaNeural", "en-AU-WilliamNeural"], "en-AU", False),
    },
    "ja": {
        "default": ("默认音色", "", None, "ja-JP", False),
        "tokyo": ("东京标准音（微软）", "日本", ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"], "ja-JP", False),
    },
}


def get_accent(language: str, key: str):
    """(voices or None, fallback locale) for an accent; unknown keys fall back to default."""
    table = ACCENTS.get(language, {})
    entry = table.get(key or "default") or table.get("default")
    return (entry[2], entry[3]) if entry else (None, LANGUAGES[language]["stt_locale"])


MODES = {
    "article": "短文",
    "dialogue": "情景对话",
    "questions": "话题问答",
    "chat": "自由对话",
    "dictation": "精听填空",
}


def get_language(code: str) -> dict:
    if code not in LANGUAGES:
        raise ValueError(f"暂不支持的语言：{code}")
    return LANGUAGES[code]


def public_languages() -> list:
    return [
        {
            "code": code,
            "name": meta["name"],
            "sttLocale": meta["stt_locale"],
            "voices": meta["voices"],
            "levels": [{"key": k, "label": v} for k, v in meta["levels"].items()],
            "accents": [
                {"key": k, "label": a[0], "group": a[1], "locale": a[3], "simulated": a[4]}
                for k, a in ACCENTS.get(code, {}).items()
            ],
        }
        for code, meta in LANGUAGES.items()
    ]
