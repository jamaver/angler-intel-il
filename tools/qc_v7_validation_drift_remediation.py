#!/usr/bin/env python3
"""Focused checks for deterministic V7 reference-data drift remediation."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.canonical_json import canonical_dumps
from persistence.connection import connect
from persistence.migrations import migrate
from persistence.catches_mirror import mirror_catches
from persistence.validation import _compare_records


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    favorite = {"name": "Home", "zip": "60543"}
    diffs, counts = _compare_records(
        "favorites",
        [favorite],
        [{"id": "home", "legacy_payload_json": canonical_dumps(favorite)}],
    )
    check(not diffs and counts["exact"] == 1, "legacy favorite without an explicit ID must validate exactly")
    check(counts["invalid_source"] == 0, "legacy favorite must not be marked invalid")

    tool = ROOT / "tools" / "v7_1_reference_reconcile.py"
    check(tool.exists(), "reference reconciliation tool is missing")
    proc = subprocess.run(
        [sys.executable, str(tool), "--dry-run", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    check(proc.returncode in (0, 1), f"reference dry-run crashed: {proc.stderr}")
    payload = json.loads(proc.stdout)
    check(payload.get("json_authoritative") is True, "reference reconciliation must retain JSON authority")
    check(set(payload.get("imported", {})) == {"species", "waters", "favorites"}, "reference reconciliation domains changed")

    # A complete catch-log reconcile must remove stale fixture rows even when
    # their earlier mirror source path differed from the runtime catch path.
    with tempfile.TemporaryDirectory(prefix="angler-v7-catch-qc-") as tmpdir:
        root = Path(tmpdir)
        db_path = root / "mirror.sqlite3"
        stale_path = root / "stale" / "catches.json"; stale_path.parent.mkdir()
        live_path = root / "live" / "catches.json"; live_path.parent.mkdir()
        stale_path.write_text(json.dumps([{"id": "stale-catch", "species": "Bass"}]), encoding="utf-8")
        live_path.write_text(json.dumps([{"id": "live-catch", "species": "Bass"}]), encoding="utf-8")
        with connect(db_path) as conn:
            migrate(conn, db_path=str(db_path))
        check(mirror_catches(stale_path, db_path=db_path).mirror_write_succeeded, "stale fixture mirror failed")
        check(mirror_catches(live_path, db_path=db_path).mirror_write_succeeded, "live catch mirror failed")
        with connect(db_path, read_only=True) as conn:
            ids = {row[0] for row in conn.execute("SELECT id FROM catches")}
    check(ids == {"live-catch"}, "catch reconciliation retained stale mirror rows")

    authority_tool = ROOT / "tools" / "v7_authority.py"
    check(authority_tool.exists(), "authority preflight tool is missing")

    print("PASS: V7 validation drift remediation QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
