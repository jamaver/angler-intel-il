#!/usr/bin/env python3
"""Record a verified active SQLite recovery baseline without changing authority."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.safe_zip import safe_extract
from persistence.sqlite_digest import logical_database_digest

INSTANCE = ROOT / "instance"
STATE_PATH = INSTANCE / "runtime_transition_v7_6.json"
BASELINE_PATH = INSTANCE / "runtime_recovery_baseline_v7_6_1.json"
ACTIVE_DB = INSTANCE / "angler_intel.sqlite3"
PARKED_DB = INSTANCE / "legacy_pre_v7_6" / "data" / "angler_intel.sqlite3"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def inspect() -> dict:
    active = logical_database_digest(ACTIVE_DB)
    parked = logical_database_digest(PARKED_DB) if PARKED_DB.exists() else None
    differences = {}
    if parked:
        for table in sorted(set(active["tables"]) | set(parked["tables"])):
            if active["tables"].get(table) != parked["tables"].get(table):
                differences[table] = {"parked": parked["tables"].get(table), "active": active["tables"].get(table)}
    return {"active": active, "parked": parked, "match": not differences if parked else None, "differences": differences}


def record(archive: Path, manifest_path: Path) -> dict:
    archive = archive.resolve()
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("verified"):
        raise RuntimeError("Recovery baseline requires a verified V7 backup manifest")
    if not archive.exists():
        raise RuntimeError("Recovery archive does not exist")
    with tempfile.TemporaryDirectory(prefix="angler-v7-6-1-baseline-") as temp_dir:
        root = Path(temp_dir)
        safe_extract(archive, root)
        archived_db = root / "data" / "angler_intel.sqlite3"
        archived = logical_database_digest(archived_db)
    active = logical_database_digest(ACTIVE_DB)
    if archived["combined_sha256"] != active["combined_sha256"] or archived["tables"] != active["tables"]:
        raise RuntimeError("Verified backup database does not match the active authoritative database")
    payload = {
        "schema": 1,
        "recorded_at": _now(),
        "authority_changed": False,
        "active_database": str(ACTIVE_DB.relative_to(ROOT)),
        "backup_archive": str(archive.relative_to(ROOT)),
        "backup_manifest": str(manifest_path.relative_to(ROOT)),
        "logical_digest": active,
        "parked_baseline": {
            "path": str(PARKED_DB.relative_to(ROOT)),
            "status": "historical_diverged" if PARKED_DB.exists() else "missing",
            "rollback_eligible": False,
            "reason": "Active SQLite authority history differs from the pre-V7.6 parked snapshot; preserve it as history, not a rollback source.",
        },
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        item = (state.get("items") or {}).get("data/angler_intel.sqlite3")
        if isinstance(item, dict):
            item["rollback_eligible"] = False
            item["rollback_reason"] = payload["parked_baseline"]["reason"]
            item["active_recovery_baseline"] = str(BASELINE_PATH.relative_to(ROOT))
            STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--record", action="store_true")
    parser.add_argument("--archive")
    parser.add_argument("--manifest")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.record:
        if args.confirm != "REBASELINE_ACTIVE_RUNTIME":
            parser.error("--record requires --confirm REBASELINE_ACTIVE_RUNTIME")
        if not args.archive or not args.manifest:
            parser.error("--record requires --archive and --manifest")
        result = record(Path(args.archive), Path(args.manifest))
    else:
        result = inspect()
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
