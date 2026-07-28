#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from persistence.connection import connect
from persistence.migrations import migrate
def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-3-0-qc-") as temp_dir:
        root = Path(temp_dir); db = root / "a.sqlite3"; source = root / "data"; reports = root / "reports"; source.mkdir(); reports.mkdir()
        (source / "target_profile.json").write_text(json.dumps({"default_target_species":"Bass"}), encoding="utf-8")
        manifest = root / "backup.manifest.json"; manifest.write_text(json.dumps({"verified": True, "authority": {"target_profile": {"authority": "json"}}}), encoding="utf-8")
        with connect(db) as conn: migrate(conn, db_path=str(db))
        cmd = [sys.executable, str(ROOT / "tools" / "v7_authority.py"), "preflight", "--domain", "target_profile", "--backup-manifest", str(manifest), "--db", str(db), "--source-root", str(source), "--reports-root", str(reports)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode in (0, 2)
        transition_cmd = [sys.executable, str(ROOT / "tools" / "v7_authority.py"), "transition", "--domain", "target_profile", "--backup-manifest", str(manifest), "--db", str(db), "--source-root", str(source), "--reports-root", str(reports), "--confirm-domain", "target_profile", "--execute"]
        transition = subprocess.run(transition_cmd, capture_output=True, text=True)
        payload = json.loads(transition.stdout)
        assert transition.returncode == 2 and not payload.get("transitioned")
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT authority FROM data_authority WHERE domain='target_profile'").fetchone()[0] == "json"
    print("PASS: V7.3.0 authority command QC")
    return 0
if __name__ == "__main__": raise SystemExit(main())
