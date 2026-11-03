#!/usr/bin/env python3
"""Preview cleanup; --apply backs up SQLite before updating historical notes."""
import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.note_quality import clean_notes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('database', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error('database does not exist')
    with sqlite3.connect(args.database) as conn:
        if args.apply:
            backup = str(args.database) + '.notes-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.bak'
            with sqlite3.connect(backup) as target:
                conn.backup(target)
            print('Backup:', backup)
        changed = 0
        for sid, raw in conn.execute('SELECT id, notes FROM sessions WHERE notes IS NOT NULL').fetchall():
            old = json.loads(raw)
            new = clean_notes(old)
            if old != new:
                changed += 1
                if args.apply:
                    conn.execute('UPDATE sessions SET notes=? WHERE id=? AND notes=?',
                                 (json.dumps(new, ensure_ascii=False), sid, raw))
        print(('Updated' if args.apply else 'Would update'), changed, 'sessions')


if __name__ == '__main__':
    main()
