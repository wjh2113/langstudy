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

MODES = {
    "article": "短文",
    "dialogue": "情景对话",
    "questions": "话题问答",
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
        }
        for code, meta in LANGUAGES.items()
    ]
