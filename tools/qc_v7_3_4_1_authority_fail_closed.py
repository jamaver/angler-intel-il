#!/usr/bin/env python3
"""Focused failure-mode QC for V7.3.4.1 authority hardening."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.authority_manifest import write_manifest
from persistence.authority_resolution import AuthorityWriteError, require_write_authority, resolve_authority
from persistence.connection import connect
from persistence.migrations import migrate

DOMAINS = ("target_profile", "gear_inventory", "manual_waters", "catches")


def set_db_authority(db: Path, domain: str, authority: str) -> None:
    with connect(db) as conn:
        with conn:
            conn.execute(
                """INSERT INTO data_authority(domain, authority, source_path, source_hash, note, updated_at)
                   VALUES(?, ?, '', '', 'QC', '2026-07-28T00:00:00+00:00')
                   ON CONFLICT(domain) DO UPDATE SET authority=excluded.authority""",
                (domain, authority),
            )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-3-4-1-qc-") as temp_dir:
        root = Path(temp_dir); db = root / "a.sqlite3"; manifest = root / "authority.json"; compatibility = root / "compat.json"
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
        json_map = {domain: "json" for domain in DOMAINS}
        write_manifest(json_map, manifest)
        for domain in DOMAINS:
            set_db_authority(db, domain, "json")
            resolved = resolve_authority(domain, db, manifest_path=manifest)
            assert resolved.effective_authority == "json" and resolved.writable

        sqlite_map = {domain: "sqlite" for domain in DOMAINS}
        write_manifest(sqlite_map, manifest)
        for domain in DOMAINS:
            set_db_authority(db, domain, "sqlite")
            resolved = resolve_authority(domain, db, manifest_path=manifest)
            assert resolved.effective_authority == "sqlite" and resolved.writable

        missing = root / "missing.sqlite3"
        for domain in DOMAINS:
            resolved = resolve_authority(domain, missing, manifest_path=manifest)
            assert resolved.effective_authority == "sqlite_unavailable" and not resolved.writable
            before = compatibility.read_bytes() if compatibility.exists() else b""
            try:
                require_write_authority(domain, missing, manifest_path=manifest)
                raise AssertionError("missing SQLite must refuse writes")
            except AuthorityWriteError as exc:
                assert exc.http_status == 503
            assert (compatibility.read_bytes() if compatibility.exists() else b"") == before

        write_manifest({domain: "json" for domain in DOMAINS}, manifest)
        set_db_authority(db, "catches", "sqlite")
        conflict = resolve_authority("catches", db, manifest_path=manifest)
        assert conflict.effective_authority == "conflict" and not conflict.writable
        try:
            require_write_authority("catches", db, manifest_path=manifest)
            raise AssertionError("conflict must refuse writes")
        except AuthorityWriteError as exc:
            assert exc.http_status == 409

        manifest.unlink()
        missing_manifest = resolve_authority("catches", db, manifest_path=manifest)
        assert missing_manifest.effective_authority == "conflict"
        manifest.write_text("{bad", encoding="utf-8")
        malformed = resolve_authority("catches", db, manifest_path=manifest)
        assert malformed.effective_authority == "conflict"

        write_manifest(sqlite_map, manifest)
        for domain in DOMAINS:
            set_db_authority(db, domain, "sqlite")
        assert json.loads(manifest.read_text(encoding="utf-8"))["domains"]["catches"] == "sqlite"
    print("PASS: V7.3.4.1 authority fail-closed QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
