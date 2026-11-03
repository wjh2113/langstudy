#!/usr/bin/env python3
"""给已有练习补上重点单词和重点句型。

写在 sessions.notes 里，不改练习正文。同一份正文只调用一次模型。
已经同时有单词和句型的练习会跳过，可以重复运行。
"""
import argparse
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config  # noqa: E402
from app.notes import generate_notes  # noqa: E402


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load_notes(raw) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _ready(notes: dict | None) -> bool:
    """单词和句型都有，才算已经补过。"""
    if not notes:
        return False
    return bool(notes.get("vocabulary")) and bool(notes.get("patterns"))


def _merge(old: dict | None, new: dict) -> dict:
    """已有的字段留下，只补空的单词、句型、语法和摘要。"""
    if not isinstance(old, dict):
        return new
    return {
        "summary": old.get("summary") or new.get("summary") or "",
        "vocabulary": old.get("vocabulary") or new.get("vocabulary") or [],
        "grammar": old.get("grammar") or new.get("grammar") or [],
        "patterns": old.get("patterns") or new.get("patterns") or [],
    }


def load_groups(db_path: Path) -> tuple[list, int]:
    """相同正文合成一组。已经齐的练习不进组。"""
    groups = {}
    skipped = 0
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id, content, notes FROM sessions").fetchall()
    for row in rows:
        notes = _load_notes(row["notes"])
        if _ready(notes):
            skipped += 1
            continue
        try:
            content = json.loads(row["content"])
        except json.JSONDecodeError:
            content = None
        if not isinstance(content, dict):
            groups.setdefault("__bad__", {"content": None, "items": []})
            groups["__bad__"]["items"].append({"id": row["id"], "notes": notes})
            continue
        bucket = groups.setdefault(row["content"], {"content": content, "items": []})
        bucket["items"].append({"id": row["id"], "notes": notes})
    return list(groups.values()), skipped


def save_one(db_path: Path, sid: str, new_notes: dict) -> bool:
    """写入前再看一眼：别人已经补齐的就跳过，避免盖掉。"""
    blob_new = new_notes
    with sqlite3.connect(db_path, timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT notes FROM sessions WHERE id=?", (sid,)).fetchone()
        if not row:
            return False
        old = _load_notes(row["notes"])
        if _ready(old):
            return False
        merged = _merge(old, blob_new)
        conn.execute(
            "UPDATE sessions SET notes=?, notes_at=? WHERE id=?",
            (json.dumps(merged, ensure_ascii=False), _now(), sid),
        )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 份不同正文，0 表示全部")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    if config.demo_mode():
        print("没有配置大模型，不能补重点单词和句型", flush=True)
        return 1
    db_path = Path(config.DB_PATH)
    jobs, skipped = load_groups(db_path)
    bad = [job for job in jobs if not job["content"]]
    jobs = [job for job in jobs if job["content"]]
    if args.limit:
        jobs = jobs[: args.limit]
    pending = sum(len(job["items"]) for job in jobs)
    print(f"待补 {len(jobs)} 份正文、{pending} 条练习，已跳过 {skipped} 条，数据库 {db_path}", flush=True)
    bad_sessions = sum(len(job["items"]) for job in bad)
    if bad_sessions:
        print(f"正文无法解析，跳过 {bad_sessions} 条", flush=True)
    done_sessions = failed = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(generate_notes, job["content"]): job for job in jobs}
        for fut in as_completed(futures):
            job = futures[fut]
            content = job["content"]
            label = f"{content.get('mode')} {content.get('level')} {content.get('topic')}"
            try:
                notes = fut.result()
            except Exception as exc:  # 单条失败不影响其余
                failed += 1
                print(f"失败 {label}（{len(job['items'])} 条）：{exc}", flush=True)
                continue
            if not (notes.get("vocabulary") or notes.get("patterns")):
                failed += 1
                print(f"失败 {label}：模型没有给出单词或句型", flush=True)
                continue
            wrote = 0
            for item in job["items"]:
                if save_one(db_path, item["id"], notes):
                    wrote += 1
            done_sessions += wrote
            partial = "" if notes.get("vocabulary") and notes.get("patterns") else "（还缺一项，下次会再补）"
            print(
                f"完成 {label}：单词 {len(notes.get('vocabulary') or [])}，句型 {len(notes.get('patterns') or [])}，写入 {wrote} 条{partial}",
                flush=True,
            )
    print(
        f"结束：写入 {done_sessions} 条，失败 {failed} 份正文，开始时已跳过 {skipped} 条，正文损坏 {bad_sessions} 条",
        flush=True,
    )
    return 1 if failed and not done_sessions else 0


if __name__ == "__main__":
    raise SystemExit(main())
