#!/usr/bin/env python3
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import json
import sqlite3
from pathlib import Path
from intelligence.sqlite_foundation import DB_PATH, APP_ROOT

out_dir = APP_ROOT / "data" / "exports"
out_dir.mkdir(parents=True, exist_ok=True)

if not DB_PATH.exists():
    raise SystemExit("SQLite database does not exist yet. Run: python tools/sqlite_init.py")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

snapshot = {}
for table in [
    "app_meta",
    "json_sources",
    "json_documents",
    "favorites_mirror",
    "catches_mirror",
    "reports_mirror",
]:
    try:
        snapshot[table] = [dict(row) for row in conn.execute(f"SELECT * FROM {table}")]
    except sqlite3.Error as exc:
        snapshot[table] = {"error": str(exc)}

out = out_dir / "sqlite_foundation_snapshot.json"
out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {out.relative_to(APP_ROOT)}")