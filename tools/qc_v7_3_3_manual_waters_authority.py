#!/usr/bin/env python3
"""QC for V7.3.3 SQLite-authoritative custom waters."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.manual_waters_authority import activate_manual_waters_authority, is_manual_waters_sqlite_authoritative, save_manual_waters_sqlite_authoritative
from persistence.manual_waters_mirror import mirror_manual_waters
from persistence.migrations import migrate


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-3-3-qc-") as temp_dir:
        root = Path(temp_dir)
        db = root / "waters.sqlite3"
        source = root / "manual_waters.json"
        waters = [{"id": "manual-pond", "name": "Fixture Pond", "type": "pond", "lat": 41.0, "lon": -88.0, "manual": True, "source": "manual"}]
        source.write_text(json.dumps(waters), encoding="utf-8")
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
        assert mirror_manual_waters(source, db_path=db).mirror_write_succeeded
        assert activate_manual_waters_authority(db, source) == waters
        assert is_manual_waters_sqlite_authoritative(db)
        changed = [dict(waters[0], favorite=True)]
        assert save_manual_waters_sqlite_authoritative(changed, db, source) == changed
        assert json.loads(source.read_text(encoding="utf-8")) == changed
        blocked = mirror_manual_waters(source, db_path=db)
        assert not blocked.mirror_write_succeeded and "SQLite-authoritative" in (blocked.error or "")
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT authority FROM data_authority WHERE domain='manual_waters'").fetchone()[0] == "sqlite"
            assert conn.execute("SELECT favorite FROM waterbodies WHERE id='manual-pond'").fetchone()[0] == 1
    print("PASS: V7.3.3 manual waters authority QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
