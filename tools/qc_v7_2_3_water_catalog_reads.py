#!/usr/bin/env python3
"""Focused QC for V7.2.3 JSON-returning water-catalog comparison reads."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
from persistence.repositories import JsonWaterCatalogRepository, SQLiteWaterCatalogRepository, read_domain


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-2-3-qc-") as temp_dir:
        db = Path(temp_dir) / "waters.sqlite3"
        catalog = {"records": [{"id": "water-1", "name": "QC Pond", "lat": 41.0, "lon": -88.0}], "base_count": 1, "custom_count": 0, "total_count": 1, "warnings": []}
        with connect(db) as conn, conn:
            migrate(conn, db_path=str(db))
            conn.execute("INSERT INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)", (SQLiteWaterCatalogRepository.SETTING_KEY, json.dumps(catalog), "2026-07-23"))
        json_repo, sqlite_repo = JsonWaterCatalogRepository(lambda: catalog), SQLiteWaterCatalogRepository(db)
        compared = read_domain("waters", json_repository=json_repo, sqlite_repository=sqlite_repo, source="compare_json")
        assert compared.effective_source == "json" and compared.comparison_status == "exact"
        fallback = read_domain("waters", json_repository=json_repo, sqlite_repository=SQLiteWaterCatalogRepository(Path(temp_dir) / "missing.sqlite3"), source="sqlite_with_json_fallback")
        assert fallback.fallback_used and fallback.value["total_count"] == 1
    print("PASS: V7.2.3 water catalog staged reads QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
