"""Coaching from recent results: suggested difficulty and the weakest skill to drill."""
from .evaluate import DIMENSIONS
from .generate import FOCUS

LEVELS = ["beginner", "intermediate", "advanced"]
LEVEL_NAMES = {"beginner": "入门", "intermediate": "中级", "advanced": "高级"}
UP, DOWN = 85, 60  # average overall score thresholds for moving level
WINDOW = 3  # sessions at the current level that the decision looks at


def recommend(recent: list) -> dict:
    """recent: newest-first [{"level", "overall", "dims": {key: score}}] for one language."""
    scored = [r for r in recent if r.get("overall") is not None]
    if not scored:
        return {"level": None, "currentLevel": None, "change": 0,
                "reason": "还没有完成的练习，先按自己的感觉选一个难度。", "weakest": None, "averages": {}}

    current = scored[0].get("level") or "intermediate"
    same = [r["overall"] for r in scored if r.get("level") == current][:WINDOW]
    avg = sum(same) / len(same)
    i = LEVELS.index(current) if current in LEVELS else 1
    change, level = 0, current
    if len(same) >= 2 and avg >= UP and i < len(LEVELS) - 1:
        change, level = 1, LEVELS[i + 1]
        reason = f"最近 {len(same)} 次{LEVEL_NAMES[current]}平均 {round(avg)} 分，可以挑战{LEVEL_NAMES[level]}了。"
    elif len(same) >= 2 and avg < DOWN and i > 0:
        change, level = -1, LEVELS[i - 1]
        reason = f"最近 {len(same)} 次{LEVEL_NAMES[current]}平均 {round(avg)} 分，先回到{LEVEL_NAMES[level]}打好基础。"
    elif len(same) < 2:
        reason = f"再做 {2 - len(same)} 次{LEVEL_NAMES.get(current, current)}练习，就能给出难度建议。"
    else:
        reason = f"最近{LEVEL_NAMES.get(current, current)}平均 {round(avg)} 分，保持这个难度继续练。"

    # weakest skill across the last few finished sessions (any level)
    sums, counts = {}, {}
    for r in scored[:5]:
        for k, v in (r.get("dims") or {}).items():
            if v is not None:
                sums[k] = sums.get(k, 0) + v
                counts[k] = counts.get(k, 0) + 1
    averages = {k: round(sums[k] / counts[k]) for k in sums}
    weakest = None
    candidates = [(averages[k], k) for k, *_ in DIMENSIONS if k in averages and k in FOCUS]
    if candidates:
        score, key = min(candidates)
        if score < 85:
            weakest = {"key": key, "name": FOCUS[key][0], "score": score, "mode": FOCUS[key][1]}
    return {"level": level, "currentLevel": current, "change": change, "reason": reason,
            "weakest": weakest, "averages": averages}
