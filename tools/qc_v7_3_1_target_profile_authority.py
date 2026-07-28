#!/usr/bin/env python3
"""QC for the target-profile-only V7.3.1 authority contract."""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from persistence.connection import connect
from persistence.migrations import migrate
from persistence.target_profile_mirror import mirror_target_profile
from persistence.target_profile_authority import activate_target_profile_authority, is_target_profile_sqlite_authoritative, save_target_profile_sqlite_authoritative
def main() -> int:
    with tempfile.TemporaryDirectory(prefix='angler-v7-3-1-qc-') as td:
        root=Path(td); db=root/'a.sqlite3'; source=root/'target_profile.json'
        original={'default_target_species':'Largemouth Bass','current_trip_target':'','favorite_species':['Largemouth Bass'],'updated_at':'2026-07-27T00:00:00'}
        source.write_text(json.dumps(original), encoding='utf-8')
        with connect(db) as conn:
            migrate(conn, db_path=str(db)); conn.execute("INSERT INTO species(id,name,legacy_payload_json) VALUES('largemouth-bass','Largemouth Bass','{}')")
        assert mirror_target_profile(original, source, db_path=db).mirror_write_succeeded
        activated=activate_target_profile_authority(db, source)
        assert activated == original and is_target_profile_sqlite_authoritative(db)
        changed={**original, 'current_trip_target':'Crappie', 'updated_at':'2026-07-27T01:00:00'}
        saved=save_target_profile_sqlite_authoritative(changed, db, source)
        assert saved == changed and json.loads(source.read_text()) == changed
        mirror = mirror_target_profile(changed, source, db_path=db)
        assert not mirror.mirror_write_succeeded and "SQLite-authoritative" in (mirror.error or "")
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT authority FROM data_authority WHERE domain='target_profile'").fetchone()[0] == 'sqlite'
            assert conn.execute("SELECT current_trip_target FROM target_profiles WHERE id='current'").fetchone()[0] == 'Crappie'
            assert '"status":"ok"' in conn.execute("SELECT value_json FROM app_settings WHERE key='v7.target_profile.compatibility_export'").fetchone()[0]
    print('PASS: V7.3.1 target profile authority QC')
    return 0
if __name__ == '__main__': raise SystemExit(main())
