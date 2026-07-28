"""JSON-first report snapshot mirroring using the V7 normalized importer."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical_json import record_hash
from .connection import DEFAULT_DB, connect
from .importers import import_reports
from .mirror import MirrorResult, mirror_after_json_write
from .provenance import file_sha256

DOMAIN = "reports"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _items(index_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    if isinstance(payload, dict):
        payload = payload.get("reports", [])
    if not isinstance(payload, list):
        raise ValueError("Reports index must be a list or an object with a reports list")
    return [item for item in payload if isinstance(item, dict)]


def _reports_sqlite_authoritative(db_path: str | Path) -> bool:
    """Prevent the legacy JSON mirror from being reused after cutover.

    This is intentionally a database-only guard.  The full fail-closed
    manifest resolver will be wired into report production routes during the
    explicit V7.3.5e authority transition; V7.3.5a does not change those
    routes or report authority.
    """
    database = Path(db_path)
    if not database.exists():
        return False
    try:
        with connect(database, read_only=True) as conn:
            row = conn.execute("SELECT authority FROM data_authority WHERE domain = ?", (DOMAIN,)).fetchone()
            return bool(row and str(row["authority"]) == "sqlite")
    except Exception:
        return False


def mirror_reports(index_path: str | Path, reports_dir: str | Path, *, db_path: str | Path = DEFAULT_DB, force: bool = False) -> MirrorResult:
    index = Path(index_path); directory = Path(reports_dir)
    if _reports_sqlite_authoritative(db_path):
        return MirrorResult(
            DOMAIN,
            "reports-authority-transitioned",
            True,
            False,
            error="Reports are SQLite-authoritative; legacy JSON-to-SQLite mirroring is disabled",
            completed_at=_now(),
        )
    try:
        records = _items(index)
        payload_hash = record_hash(records)
    except Exception as exc:
        return MirrorResult(DOMAIN, f"reports-invalid-{index.name}", True, False, error=f"Invalid reports index: {exc}", completed_at=_now())
    # A report index can legitimately return to a prior payload, for example
    # after deleting the last report twice over its lifetime.  Include the
    # filesystem revision so that distinct successful JSON writes still run a
    # mirror transaction, while retries of the same write remain idempotent.
    revision = index.stat().st_mtime_ns if index.exists() else 0
    operation_id = f"reports-{payload_hash}-{file_sha256(index) or 'missing'}-{revision}"
    if force:
        operation_id = f"{operation_id}-reconcile-{uuid.uuid4().hex}"
    return mirror_after_json_write(
        DOMAIN,
        lambda conn: import_reports(conn, index, directory, commit=False),
        operation_id=operation_id,
        db_path=db_path,
        details={"index_path": str(index), "report_count": len(records), "reports_dir": str(directory)},
    )


def compare_reports(index_path: str | Path, *, db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    index = Path(index_path); result: dict[str, Any] = {"status": "missing_in_sqlite", "differences": []}
    try:
        expected = {str(item.get("id") or ""): record_hash(item) for item in _items(index) if str(item.get("id") or "")}
    except Exception as exc:
        return {"status": "invalid_source", "differences": [str(exc)]}
    if not Path(db_path).exists():
        result["differences"].append("SQLite database is unavailable."); return result
    try:
        with connect(db_path, read_only=True) as conn:
            rows = [dict(row) for row in conn.execute("SELECT id, legacy_payload_json FROM trip_reports")]
            actual = {str(row["id"]): record_hash(json.loads(row["legacy_payload_json"])) for row in rows}
            if set(expected) != set(actual): result["differences"].append("report_ids")
            for report_id in sorted(set(expected).intersection(actual)):
                if expected[report_id] != actual[report_id]: result["differences"].append(f"report:{report_id}")
            result["status"] = "exact" if not result["differences"] else "changed"
            return result
    except Exception as exc:
        return {"status": "invalid_source", "differences": [str(exc)]}
