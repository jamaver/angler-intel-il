#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from intelligence.sqlite_foundation import initialize_and_mirror, status
from intelligence.water_registry import load_water_catalog


def _gate(name: str, ok: bool, summary: str, details: dict | None = None) -> dict:
    return {
        "name": name,
        "ok": bool(ok),
        "summary": summary,
        "details": details or {},
    }


def collect_preflight() -> dict:
    catalog = load_water_catalog()
    expected_count = int(catalog.get("total_count", 0))
    init_result = initialize_and_mirror()
    db_status = status()
    export_tool = APP_ROOT / "tools" / "sqlite_export_snapshot.py"
    export_ok = False
    export_table_ok = False
    export_path = APP_ROOT / "data" / "exports" / "sqlite_foundation_snapshot.json"

    if export_tool.exists():
        try:
            subprocess.run([sys.executable, str(export_tool)], cwd=APP_ROOT, check=True, capture_output=True, text=True)
            export_ok = export_path.exists()
            if export_ok:
                snapshot = json.loads(export_path.read_text(encoding="utf-8"))
                export_table_ok = "waterbodies_mirror" in snapshot
        except Exception:
            export_ok = False
            export_table_ok = False

    details = {
        "database": db_status.get("database"),
        "exists": db_status.get("exists"),
        "expected_count": expected_count,
        "catalog_base_count": catalog.get("base_count", 0),
        "catalog_custom_count": catalog.get("custom_count", 0),
        "catalog_total_count": expected_count,
        "table_counts": db_status.get("table_counts", {}),
        "source_path": catalog.get("source_path"),
        "custom_source_path": catalog.get("custom_source_path"),
        "waterbody_mirror_count": db_status.get("table_counts", {}).get("waterbodies_mirror"),
        "export_path": str(export_path.relative_to(APP_ROOT)),
        "mirror_result": init_result.get("waterbodies", {}),
    }

    waterbody_count = db_status.get("table_counts", {}).get("waterbodies_mirror")
    init_waterbody_count = int(init_result.get("waterbodies", {}).get("waterbody_count", 0) or 0)
    waterbody_ok = (
        waterbody_count == expected_count
        and init_waterbody_count == expected_count
        and expected_count > 0
    )

    gates = [
        _gate("waterbody_catalog", expected_count > 0, "Waterbody catalog is available.", details),
        _gate("waterbody_mirror", waterbody_ok, "Waterbodies mirror table matches the catalog count.", details),
        _gate("export_snapshot", export_ok and export_table_ok, "SQLite export snapshot includes waterbodies.", details),
        _gate("sqlite_status", bool(db_status.get("exists")), "SQLite database exists.", details),
    ]

    ok = all(gate["ok"] for gate in gates)
    return {
        "version": "v5.1-sqlite-waterbody-migration-prep",
        "ok": ok,
        "json_source_of_truth": True,
        "authority_flipped": False,
        "current_authority": "json",
        "sqlite_role": "mirror/read-only foundation until explicit migration",
        "migration_target": "waterbodies-first",
        "catalog": {
            "base_count": catalog.get("base_count", 0),
            "custom_count": catalog.get("custom_count", 0),
            "total_count": expected_count,
        },
        "init_result": init_result,
        "gates": gates,
        "warnings": [] if ok else ["Waterbody migration prep still needs attention."],
        "errors": [gate["summary"] for gate in gates if not gate["ok"]],
    }


if __name__ == "__main__":
    print(json.dumps(collect_preflight(), indent=2, ensure_ascii=False))
