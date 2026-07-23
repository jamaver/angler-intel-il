#!/usr/bin/env python3
"""Focused QC for V7.1.6 reconciliation queue and status diagnostics."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
from persistence.mirror import (
    get_reconciliation_summary,
    request_reconciliation,
    resolve_reconciliation_requests,
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-1-6-qc-") as temp_dir:
        db = Path(temp_dir) / "mirror.sqlite3"
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
        assert request_reconciliation("reports", reason="QC recovery", operation_id="qc-report", db_path=db)
        with connect(db) as conn, conn:
            summary = get_reconciliation_summary(conn)
            assert summary["pending_total"] == 1
            assert resolve_reconciliation_requests(conn, "reports") == 1
            assert get_reconciliation_summary(conn)["pending_total"] == 0
            conn.execute(
                """INSERT INTO mirror_operations(
                    domain, operation_id, status, source_write_succeeded,
                    mirror_write_succeeded, details_json, started_at
                ) VALUES('reports', 'qc-stale', 'running', 1, 0, '{}', '2000-01-01T00:00:00')"""
            )
            assert get_reconciliation_summary(conn)["stale_total"] == 1

    source = (ROOT / "tools" / "v7_1_reconcile.py").read_text(encoding="utf-8")
    assert 'selection.add_argument("--all"' in source
    assert "resolve_reconciliation_requests" in source
    print("PASS: V7.1.6 reconciliation and soak diagnostics QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
