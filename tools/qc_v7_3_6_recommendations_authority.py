#!/usr/bin/env python3
"""Focused QC for V7.3.6 persisted recommendation authority."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.authority_manifest import write_manifest
from persistence.authority_resolution import resolve_authority
from persistence.connection import connect
from persistence.migrations import migrate
from persistence.recommendations_authority import (
    activate_recommendations_authority,
    list_authoritative_recommendation_history,
    record_recommendation_feedback,
    recommendation_transition_preflight,
)
from persistence.reports_authority import save_report_sqlite_authoritative


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-3-6-qc-") as temp_dir:
        root = Path(temp_dir); data = root / "data"; reports = root / "reports"; data.mkdir(); reports.mkdir()
        db, index, manifest = data / "angler.sqlite3", data / "reports_index.json", data / "authority.json"
        report_id = "recommendation-transition"
        meta = {
            "id": report_id, "title": "Recommendation QC", "zip": "60543",
            "created": "2026-07-28T20:00:00+00:00", "json_file": f"{report_id}.json",
            "html_file": f"{report_id}.html", "view_url": f"/api/reports/view/{report_id}",
        }
        wrapped = {
            "meta": dict(meta),
            "payload": {"zip": "60543", "intel": {"summary": "QC intelligence", "target_species": "Largemouth Bass"}},
            "summary": {"best_bet": {"species": "Largemouth Bass", "lure_type": "jig", "lure_name": "Green Pumpkin Jig", "species_score": 84, "confidence": "high", "reasons": ["QC reason"], "caution": ["QC caution"]}},
        }
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            conn.execute("UPDATE data_authority SET authority='sqlite' WHERE domain='reports'")
            conn.commit()
        write_manifest({"reports": "sqlite"}, manifest)
        saved = save_report_sqlite_authoritative(meta, wrapped, "<html>QC</html>", db_path=db, index_path=index, reports_dir=reports)
        assert not saved.warning
        initial = recommendation_transition_preflight(db)
        assert initial["authority"] == "json" and initial["ready"]
        activated = activate_recommendations_authority(db)
        assert activated["authority"] == "sqlite"
        write_manifest({"reports": "sqlite", "recommendations": "sqlite"}, manifest)
        resolution = resolve_authority("recommendations", db, manifest_path=manifest)
        assert resolution.effective_authority == "sqlite" and resolution.writable
        history = list_authoritative_recommendation_history(db)
        assert len(history) == 1 and history[0]["id"] == f"{report_id}-best-bet"
        feedback = record_recommendation_feedback(history[0]["id"], feedback_type="followed", rating=4, notes="QC", db_path=db)
        assert feedback["rating"] == 4
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT authority FROM data_authority WHERE domain='recommendations'").fetchone()[0] == "sqlite"
            assert conn.execute("SELECT count(*) FROM recommendation_feedback").fetchone()[0] == 1
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []
    print("PASS: V7.3.6 recommendations authority QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
