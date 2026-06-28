#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/angler-intel"
cd "$APP_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$APP_DIR/backups/v4_5_1a_sqlite_diagnostics_$STAMP"

echo "=== Angler Intel IL v4.5.1a SQLite Diagnostics ==="
echo "App dir: $APP_DIR"
echo "Backup:  $BACKUP_DIR"

mkdir -p "$BACKUP_DIR"
cp -a intelligence tools data "$BACKUP_DIR/" 2>/dev/null || true

echo
echo "1) Checking current v4.5 foundation..."
python tools/sqlite_init.py
python tools/qc_v4_5_sqlite.py

echo
echo "2) Writing enhanced diagnostics tool..."

cat > tools/sqlite_diagnostics.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from intelligence.sqlite_foundation import DB_PATH, status


REQUIRED_TABLES = [
    "app_meta",
    "json_sources",
    "json_documents",
    "favorites_mirror",
    "catches_mirror",
    "reports_mirror",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db_size() -> int:
    if not DB_PATH.exists():
        return 0
    return DB_PATH.stat().st_size


def get_integrity_check(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute("PRAGMA integrity_check;").fetchone()
        return str(row[0]) if row else "unknown"
    except sqlite3.Error as exc:
        return f"error: {exc}"


def get_journal_mode(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute("PRAGMA journal_mode;").fetchone()
        return str(row[0]) if row else "unknown"
    except sqlite3.Error as exc:
        return f"error: {exc}"


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def table_count(conn: sqlite3.Connection, table: str) -> int | None:
    if not table_exists(conn, table):
        return None
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0])


def collect_diagnostics() -> dict:
    base_status = status()

    diagnostics = {
        "diagnostics_version": "v4.5.1a",
        "checked_at": utc_now(),
        "database": str(DB_PATH.relative_to(APP_ROOT)),
        "database_exists": DB_PATH.exists(),
        "database_size_bytes": get_db_size(),
        "json_source_of_truth": True,
        "foundation_status": base_status,
        "checks": {},
        "warnings": [],
        "errors": [],
    }

    if not DB_PATH.exists():
        diagnostics["errors"].append("SQLite database does not exist.")
        return diagnostics

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    diagnostics["checks"]["integrity_check"] = get_integrity_check(conn)
    diagnostics["checks"]["journal_mode"] = get_journal_mode(conn)

    table_counts = {}
    missing_tables = []

    for table in REQUIRED_TABLES:
        count = table_count(conn, table)
        table_counts[table] = count
        if count is None:
            missing_tables.append(table)

    diagnostics["table_counts"] = table_counts

    if missing_tables:
        diagnostics["errors"].append(f"Missing required tables: {missing_tables}")

    meta = {}
    if table_exists(conn, "app_meta"):
        meta = {
            row["key"]: row["value"]
            for row in conn.execute("SELECT key, value FROM app_meta").fetchall()
        }

    diagnostics["app_meta"] = meta

    if meta.get("sqlite_foundation_version") != "v4.5":
        diagnostics["errors"].append("sqlite_foundation_version is not v4.5.")

    if meta.get("json_source_of_truth") != "true":
        diagnostics["errors"].append("json_source_of_truth marker is missing or false.")

    if diagnostics["checks"]["integrity_check"] != "ok":
        diagnostics["errors"].append(
            f"SQLite integrity check failed: {diagnostics['checks']['integrity_check']}"
        )

    if diagnostics["checks"]["journal_mode"].lower() != "wal":
        diagnostics["warnings"].append(
            f"SQLite journal mode is {diagnostics['checks']['journal_mode']}, expected wal."
        )

    if table_exists(conn, "json_sources"):
        sources = [
            dict(row)
            for row in conn.execute(
                """
                SELECT logical_name, path, row_count, source_of_truth, last_loaded_at
                FROM json_sources
                ORDER BY logical_name
                """
            ).fetchall()
        ]
        diagnostics["sources"] = sources

        for source in sources:
            if source.get("source_of_truth") != "json":
                diagnostics["errors"].append(
                    f"Source {source.get('logical_name')} is not marked as JSON source of truth."
                )
    else:
        diagnostics["sources"] = []

    # JSON file validity checks remain critical because JSON is still authoritative.
    json_health = {}
    for rel in ["data/favorites.json", "data/catches.json", "data/saved_reports.json"]:
        path = APP_ROOT / rel
        if not path.exists():
            json_health[rel] = {
                "exists": False,
                "valid_json": None,
                "note": "optional or not present",
            }
            continue

        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(parsed, list):
                item_count = len(parsed)
            elif isinstance(parsed, dict):
                item_count = len(parsed)
            else:
                item_count = 1

            json_health[rel] = {
                "exists": True,
                "valid_json": True,
                "top_level_type": type(parsed).__name__,
                "item_count_estimate": item_count,
            }
        except Exception as exc:
            json_health[rel] = {
                "exists": True,
                "valid_json": False,
                "error": str(exc),
            }
            diagnostics["errors"].append(f"{rel} is not valid JSON: {exc}")

    diagnostics["json_health"] = json_health

    diagnostics["ok"] = len(diagnostics["errors"]) == 0
    return diagnostics


def print_human_report(d: dict) -> None:
    print("=== SQLite Diagnostics v4.5.1a ===")
    print(f"Database: {d['database']}")
    print(f"Exists:   {d['database_exists']}")
    print(f"Size:     {d['database_size_bytes']} bytes")
    print(f"JSON authoritative: {d['json_source_of_truth']}")

    print()
    print("Checks:")
    for key, value in d.get("checks", {}).items():
        print(f"  {key}: {value}")

    print()
    print("Table counts:")
    for table, count in d.get("table_counts", {}).items():
        print(f"  {table}: {count}")

    print()
    print("Sources:")
    for source in d.get("sources", []):
        print(
            f"  {source.get('logical_name')}: "
            f"{source.get('row_count')} rows, "
            f"{source.get('source_of_truth')} source, "
            f"loaded {source.get('last_loaded_at')}"
        )

    print()
    print("JSON health:")
    for rel, info in d.get("json_health", {}).items():
        if info.get("exists"):
            print(
                f"  {rel}: valid={info.get('valid_json')}, "
                f"type={info.get('top_level_type')}, "
                f"items={info.get('item_count_estimate')}"
            )
        else:
            print(f"  {rel}: not present ({info.get('note')})")

    if d.get("warnings"):
        print()
        print("Warnings:")
        for warning in d["warnings"]:
            print(f"  - {warning}")

    if d.get("errors"):
        print()
        print("Errors:")
        for error in d["errors"]:
            print(f"  - {error}")

    print()
    print("Result:", "PASS" if d.get("ok") else "FAIL")


def main() -> int:
    as_json = "--json" in sys.argv
    diagnostics = collect_diagnostics()

    if as_json:
        print(json.dumps(diagnostics, indent=2, ensure_ascii=False))
    else:
        print_human_report(diagnostics)

    return 0 if diagnostics.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
PY

chmod +x tools/sqlite_diagnostics.py

echo
echo "3) Upgrading v4.5 QC to include diagnostics..."

cat > tools/qc_v4_5_1a_sqlite_diagnostics.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from tools.sqlite_diagnostics import collect_diagnostics


d = collect_diagnostics()

if not d.get("ok"):
    print("QC FAILED: v4.5.1a SQLite diagnostics")
    for err in d.get("errors", []):
        print(f" - {err}")
    raise SystemExit(1)

print("QC PASSED: v4.5.1a SQLite diagnostics")
print(f"Database: {d['database']}")
print(f"Size: {d['database_size_bytes']} bytes")
print("JSON remains source of truth.")
PY

chmod +x tools/qc_v4_5_1a_sqlite_diagnostics.py

echo
echo "4) Writing version marker..."

cat > data/version_v4_5_1a_sqlite_diagnostics.json <<JSON
{
  "version": "v4.5.1a-sqlite-diagnostics",
  "previous": "v4.5-sqlite-foundation",
  "json_source_of_truth": true,
  "sqlite_role": "read-only diagnostics and mirror health only",
  "flask_ui_changed": false,
  "installed_at": "$(date -Iseconds)"
}
JSON

echo
echo "5) Running diagnostics..."
python tools/sqlite_diagnostics.py

echo
echo "6) Running QC..."
python tools/qc_v4_5_sqlite.py
python tools/qc_v4_5_1a_sqlite_diagnostics.py

echo
echo "7) Git status..."
git status --short || true

echo
echo "=== v4.5.1a complete ==="
echo
echo "Recommended commit:"
echo "git add tools/sqlite_diagnostics.py tools/qc_v4_5_1a_sqlite_diagnostics.py data/version_v4_5_1a_sqlite_diagnostics.json upgrade_v4_5_1a_sqlite_diagnostics.sh"
echo "git commit -m 'Add v4.5.1a SQLite diagnostics QC'"
echo "git push"
