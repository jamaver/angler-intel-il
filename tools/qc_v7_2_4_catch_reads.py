#!/usr/bin/env python3
"""Focused QC for V7.2.4 JSON-returning catch comparison reads."""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from persistence.connection import connect
from persistence.catches_mirror import mirror_catches
from persistence.migrations import migrate
from persistence.repositories import JsonCatchesRepository, SQLiteCatchesRepository, read_domain
def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-2-4-qc-") as temp_dir:
        root = Path(temp_dir); source = root / "catches.json"; db = root / "catches.sqlite3"
        catches = [{"id": "catch-1", "species": "Largemouth Bass", "waterbody": "QC Pond", "gear_refs": {"rod": "missing"}}]
        source.write_text(json.dumps(catches), encoding="utf-8")
        with connect(db) as conn: migrate(conn, db_path=str(db))
        assert mirror_catches(source, db_path=db).mirror_write_succeeded
        result = read_domain("catches", json_repository=JsonCatchesRepository(source), sqlite_repository=SQLiteCatchesRepository(db), source="compare_json")
        assert result.effective_source == "json" and result.comparison_status == "exact"
        fallback = read_domain("catches", json_repository=JsonCatchesRepository(source), sqlite_repository=SQLiteCatchesRepository(root / "missing.sqlite3"), source="sqlite_with_json_fallback")
        assert fallback.fallback_used and fallback.value[0]["id"] == "catch-1"
    print("PASS: V7.2.4 catch staged reads QC")
    return 0
if __name__ == "__main__": raise SystemExit(main())
