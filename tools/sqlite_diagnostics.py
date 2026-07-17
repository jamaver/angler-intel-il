#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

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


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def json_item_count(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("items", "records", "catches", "favorites", "waters", "waterbodies", "reports", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        return 1 if payload else 0
    return 1 if payload is not None else 0


def collect_diagnostics() -> dict:
    result = {
        "diagnostics_version": "v4.5.1a",
        "checked_at": now_utc(),
        "database": str(DB_PATH.relative_to(APP_ROOT)),
        "database_exists": DB_PATH.exists(),
        "database_size_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
        "errors": [],
        "warnings": [],
        "tables": {},
        "sources": [],
        "json_files": {},
    }

    if not DB_PATH.exists():
        result["errors"].append("SQLite database does not exist. Run python tools/sqlite_init.py")
        result["ok"] = False
        return result

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON;")

    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]

    result["integrity_check"] = integrity
    result["journal_mode"] = journal_mode

    if integrity != "ok":
        result["errors"].append(f"SQLite integrity check failed: {integrity}")

    if str(journal_mode).lower() != "wal":
        result["warnings"].append(f"Journal mode is {journal_mode}; expected wal")

    existing_tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }

    for table in REQUIRED_TABLES:
        if table not in existing_tables:
            result["tables"][table] = None
            result["errors"].append(f"Missing required table: {table}")
        else:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            result["tables"][table] = int(count)

    if "app_meta" in existing_tables:
        meta = {
            row["key"]: row["value"]
            for row in conn.execute("SELECT key, value FROM app_meta")
        }
        result["app_meta"] = meta

        if meta.get("sqlite_foundation_version") != "v4.5":
            result["errors"].append("sqlite_foundation_version is not v4.5")

        if meta.get("json_source_of_truth") != "true":
            result["errors"].append("json_source_of_truth marker is missing or false")

    if "json_sources" in existing_tables:
        result["sources"] = [
            dict(row)
            for row in conn.execute(
                """
                SELECT logical_name, path, row_count, source_of_truth, last_loaded_at
                FROM json_sources
                ORDER BY logical_name
                """
            )
        ]

        for source in result["sources"]:
            if source.get("source_of_truth") != "json":
                result["errors"].append(
                    f"{source.get('logical_name')} is not marked as JSON source of truth"
                )

    for rel in [
        "data/favorites.json",
        "data/catches.json",
        "data/saved_reports.json",
    ]:
        path = APP_ROOT / rel
        info = {"exists": path.exists()}

        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                info["valid_json"] = True
                info["top_level_type"] = type(payload).__name__
                info["item_count_estimate"] = json_item_count(payload)
            except Exception as exc:
                info["valid_json"] = False
                info["error"] = str(exc)
                result["errors"].append(f"{rel} is invalid JSON: {exc}")

        result["json_files"][rel] = info

    json_by_path = result["json_files"]
    for source in result.get("sources", []):
        source_path = source.get("path")
        json_info = json_by_path.get(source_path)
        if not json_info or json_info.get("item_count_estimate") is None:
            continue

        expected_count = int(json_info["item_count_estimate"])
        actual_count = int(source.get("row_count", -1))
        if actual_count != expected_count:
            result["errors"].append(
                f"{source.get('logical_name')} mirror row_count {actual_count} "
                f"does not match JSON count {expected_count}"
            )

    result["foundation_status"] = status()
    result["ok"] = len(result["errors"]) == 0

    return result


def print_report(d: dict) -> None:
    print("=== SQLite Diagnostics v4.5.1a ===")
    print(f"Database: {d['database']}")
    print(f"Exists: {d['database_exists']}")
    print(f"Size: {d['database_size_bytes']} bytes")
    print(f"SQLite role: {d['sqlite_role']}")
    print(f"JSON source of truth: {d['json_source_of_truth']}")
    print(f"Integrity: {d.get('integrity_check')}")
    print(f"Journal mode: {d.get('journal_mode')}")

    print()
    print("Tables:")
    for table, count in d.get("tables", {}).items():
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
    print("JSON files:")
    for rel, info in d.get("json_files", {}).items():
        print(f"  {rel}: {info}")

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


if __name__ == "__main__":
    diagnostics = collect_diagnostics()

    if "--json" in sys.argv:
        print(json.dumps(diagnostics, indent=2, ensure_ascii=False))
    else:
        print_report(diagnostics)

    raise SystemExit(0 if diagnostics.get("ok") else 1)
