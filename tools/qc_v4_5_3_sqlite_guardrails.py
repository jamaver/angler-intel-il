#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
import sqlite3
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

errors: list[str] = []
warnings: list[str] = []

DB_REL = "data/angler_intel.sqlite3"
DB_PATH = APP_ROOT / DB_REL
REQUIRED_TABLES = {
    "app_meta",
    "json_sources",
    "json_documents",
    "favorites_mirror",
    "catches_mirror",
    "reports_mirror",
}
MIRROR_TABLES = {
    "favorites_mirror",
    "catches_mirror",
    "reports_mirror",
}
EXPECTED_JSON = {
    "favorites": "data/favorites.json",
    "catches": "data/catches.json",
    "saved_reports": "data/saved_reports.json",
}


def read(rel: str) -> str:
    return (APP_ROOT / rel).read_text(encoding="utf-8")


def json_item_count(path: Path) -> int | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("items", "records", "catches", "favorites", "waters", "waterbodies", "reports", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        return len(payload)
    return 1


for rel in (
    "app.py",
    "intelligence/sqlite_foundation.py",
    "intelligence/app_health_sqlite.py",
    "tools/sqlite_diagnostics.py",
):
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

gitignore = read(".gitignore") if (APP_ROOT / ".gitignore").exists() else ""
for required in (
    "data/angler_intel.sqlite3",
    "data/angler_intel.sqlite3-*",
    "backups/",
    "__pycache__/",
    "venv/",
):
    if required not in gitignore.splitlines():
        errors.append(f".gitignore missing {required}")

index = read("templates/index.html")
if 'href="/admin"' in index:
    errors.append("Normal navigation should not expose Admin")
if '{% include "_sqlite_health_card.html" %}' in index:
    errors.append("SQLite maintenance card should live in App Health, not the dashboard")
if '{% include "_backup_health_card.html" %}' in index:
    errors.append("Backup maintenance card should live in App Health, not the dashboard")

app_text = read("app.py")
if "get_sqlite_health_for_app" not in app_text:
    errors.append("app.py is missing SQLite App Health helper wiring")

if re.search(r"sqlite3\s*\.\s*connect|from\s+sqlite3\s+import", app_text):
    errors.append("app.py should not connect to SQLite directly")

health_text = read("angler_health_v39.py")
if 'href="/admin"' in health_text:
    errors.append("App Health navigation should not expose Admin")
if "_sqlite_health_card.html" not in health_text:
    errors.append("App Health should render the SQLite maintenance card")
if "_backup_health_card.html" not in health_text:
    errors.append("App Health should render the backup maintenance card")

if DB_REL not in gitignore:
    errors.append("Runtime SQLite database is not ignored")

if not DB_PATH.exists():
    errors.append("SQLite database does not exist. Run python tools/sqlite_init.py")
else:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        errors.append(f"SQLite integrity check failed: {integrity}")

    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    missing = REQUIRED_TABLES - tables
    for table in sorted(missing):
        errors.append(f"Missing required table: {table}")

    if "app_meta" in tables:
        meta = {
            row["key"]: row["value"]
            for row in conn.execute("SELECT key, value FROM app_meta")
        }
        if meta.get("json_source_of_truth") != "true":
            errors.append("SQLite app_meta does not preserve json_source_of_truth=true")
        if meta.get("sqlite_foundation_version") != "v4.5":
            errors.append("SQLite foundation version should remain v4.5")

    if "json_sources" in tables:
        sources = [
            dict(row)
            for row in conn.execute(
                """
                SELECT logical_name, path, row_count, source_of_truth, last_loaded_at
                FROM json_sources
                ORDER BY logical_name
                """
            )
        ]

        for source in sources:
            if source.get("source_of_truth") != "json":
                errors.append(f"{source.get('logical_name')} is not marked as JSON source of truth")
            if not source.get("last_loaded_at"):
                errors.append(f"{source.get('logical_name')} is missing mirror freshness timestamp")

            logical = source.get("logical_name")
            rel = EXPECTED_JSON.get(logical)
            if rel:
                count = json_item_count(APP_ROOT / rel)
                if count is not None and int(source.get("row_count", -1)) != count:
                    errors.append(
                        f"{logical} mirror row_count {source.get('row_count')} does not match JSON count {count}"
                    )

    for table in MIRROR_TABLES & tables:
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})")
        }
        for required_column in ("payload_json", "payload_sha256", "mirrored_at"):
            if required_column not in columns:
                errors.append(f"{table} missing mirror guardrail column {required_column}")

    conn.close()

sqlite_helper = read("intelligence/app_health_sqlite.py")
if "mirror/read-only foundation" not in sqlite_helper:
    errors.append("SQLite App Health helper must state mirror/read-only foundation")
if "Read-only SQLite health summary" not in sqlite_helper:
    errors.append("SQLite App Health helper should remain read-only")
if "initialize_and_mirror" in sqlite_helper:
    errors.append("SQLite App Health helper must not import or call mirror initialization")

foundation = read("intelligence/sqlite_foundation.py")
if "source_of_truth='json'" not in foundation and "source_of_truth TEXT NOT NULL DEFAULT 'json'" not in foundation:
    errors.append("SQLite foundation should keep JSON source-of-truth markers")

if errors:
    print("QC FAILED: v4.5.3 SQLite Mirror Guardrails")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.5.3 SQLite Mirror Guardrails")
print("JSON remains source of truth.")
print("SQLite remains mirror/read-only foundation.")
if warnings:
    print("Warnings:")
    for warning in warnings:
        print(f" - {warning}")
