#!/usr/bin/env python3
"""Operator-only management for the external V7 authority manifest."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.authority import V7_DOMAINS
from persistence.authority_manifest import manifest_path, read_manifest, write_manifest
from persistence.authority_resolution import resolve_authority
from persistence.connection import connect


def database_authorities(db: Path) -> dict[str, str]:
    with connect(db, read_only=True) as conn:
        rows = {str(row["domain"]): str(row["authority"]) for row in conn.execute("SELECT domain, authority FROM data_authority")}
    return {domain: rows.get(domain, "json") for domain in V7_DOMAINS}


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair or inspect V7 authority manifest")
    parser.add_argument("action", choices=("show", "initialize", "repair"))
    parser.add_argument("--db", default=str(ROOT / "data" / "angler_intel.sqlite3"))
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--confirm", help="Must be exactly 'authority-manifest'")
    args = parser.parse_args()
    db = Path(args.db)
    path = manifest_path(args.manifest)
    if args.action == "show":
        manifest, error = read_manifest(path)
        result = {"path": str(path), "manifest": manifest, "error": error,
                  "resolutions": [asdict(resolve_authority(domain, db, manifest_path=path)) for domain in V7_DOMAINS]}
        print(json.dumps(result, indent=2, default=str)); return 0
    if args.confirm != "authority-manifest":
        parser.error("--confirm authority-manifest is required for manifest changes")
    values = database_authorities(db)
    if args.action == "initialize" and path.exists():
        parser.error("Manifest already exists; use repair after operator review")
    written = write_manifest(values, path)
    print(json.dumps({"ok": True, "action": args.action, "path": str(written), "domains": values}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
