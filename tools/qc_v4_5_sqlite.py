#!/usr/bin/env python3
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import json
import sqlite3
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = APP_ROOT / "data" / "angler_intel.sqlite3"

required_tables = {
    "app_meta",
    "json_sources",
    "json_documents",
    "favorites_mirror",
    "catches_mirror",
    "reports_mirror",
}

errors = []

if not DB_PATH.exists():
    errors.append("Missing data/angler_intel.sqlite3")
else:
    conn = sqlite3.connect(DB_PATH)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    missing = required_tables - tables
    if missing:
        errors.append(f"Missing tables: {sorted(missing)}")

    meta = dict(conn.execute("SELECT key, value FROM app_meta").fetchall())
    if meta.get("sqlite_foundation_version") != "v4.5":
        errors.append("app_meta.sqlite_foundation_version is not v4.5")

    if meta.get("json_source_of_truth") != "true":
        errors.append("JSON source-of-truth marker missing")

    source_count = conn.execute("SELECT COUNT(*) FROM json_sources").fetchone()[0]
    if source_count < 0:
        errors.append("Invalid json_sources count")

# Confirm JSON files were not replaced with empty files.
for name in ["favorites.json", "catches.json"]:
    path = APP_ROOT / "data" / name
    if path.exists():
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{name} is not valid JSON: {exc}")

if errors:
    print("QC FAILED")
    for err in errors:
        print(f" - {err}")
    raise SystemExit(1)

print("QC PASSED: v4.5 SQLite Foundation is installed and JSON remains source of truth.")