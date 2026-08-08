#!/usr/bin/env python3
"""Operator CLI for the non-authoritative Google Drive export queue."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.google_drive import BACKUP_DIR, public_status, queue_report_export, queue_verified_backup, test_connection, upload_pending


def _latest_backup() -> Path:
    manifest = json.loads((BACKUP_DIR / "latest_v7_runtime_backup_manifest.json").read_text(encoding="utf-8"))
    archive = ROOT / str(manifest.get("archive") or "")
    if not archive.exists():
        raise ValueError("Latest verified backup is unavailable")
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload verified Angler Intel artifacts to Google Drive")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true")
    group.add_argument("--test", action="store_true")
    group.add_argument("--latest-backup", action="store_true")
    group.add_argument("--report")
    group.add_argument("--pending", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if args.status:
            result = {"ok": True, "google_drive": public_status()}
        elif args.test:
            result = test_connection()
        elif args.latest_backup:
            archive = _latest_backup(); queue_verified_backup(archive); result = upload_pending(object_id=archive.stem)
        elif args.report:
            queue_report_export(args.report); result = upload_pending(object_id=args.report)
        else:
            result = upload_pending()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) if args.json else result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
