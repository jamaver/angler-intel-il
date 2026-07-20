"""JSON-first SQLite mirror-write primitives.

This module is intentionally not wired to production writers in V7.1.0.  A
domain writer calls it only after its existing JSON write has succeeded.
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .authority import V7_DOMAINS, utc_now
from .canonical_json import canonical_dumps
from .connection import DEFAULT_DB, connect

logger = logging.getLogger(__name__)

MirrorCallback = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True, slots=True)
class MirrorResult:
    domain: str
    operation_id: str
    source_write_succeeded: bool
    mirror_write_succeeded: bool
    idempotent: bool = False
    reconciliation_requested: bool = False
    error: str | None = None
    completed_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_operation_id() -> str:
    return f"mirror-{uuid.uuid4()}"


def _validate(domain: str, callback: MirrorCallback | None) -> str | None:
    if domain not in V7_DOMAINS:
        return f"Unsupported mirror domain: {domain}"
    if not callable(callback):
        return "Mirror callback must be callable"
    return None


def _upsert_domain_status(
    conn: sqlite3.Connection,
    domain: str,
    *,
    status: str,
    operation_id: str | None,
    success_at: str | None = None,
    failure_at: str | None = None,
    error: str | None = None,
) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO mirror_domain_status(
            domain, status, last_operation_id, last_success_at, last_failure_at,
            last_error, reconciliation_requested_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, NULL, ?)
        ON CONFLICT(domain) DO UPDATE SET
            status = excluded.status,
            last_operation_id = excluded.last_operation_id,
            last_success_at = COALESCE(excluded.last_success_at, mirror_domain_status.last_success_at),
            last_failure_at = COALESCE(excluded.last_failure_at, mirror_domain_status.last_failure_at),
            last_error = excluded.last_error,
            updated_at = excluded.updated_at
        """,
        (domain, status, operation_id, success_at, failure_at, error, now),
    )


def _record_failure(db_path: Path, domain: str, operation_id: str, error: str) -> bool:
    """Best-effort diagnostic persistence after a callback transaction fails."""
    try:
        with connect(db_path) as conn:
            now = utc_now()
            with conn:
                conn.execute(
                    """
                    UPDATE mirror_operations
                    SET status = 'failed', mirror_write_succeeded = 0, error_text = ?, completed_at = ?
                    WHERE domain = ? AND operation_id = ?
                    """,
                    (error, now, domain, operation_id),
                )
                _upsert_domain_status(
                    conn,
                    domain,
                    status="degraded",
                    operation_id=operation_id,
                    failure_at=now,
                    error=error,
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO mirror_reconciliation_requests(
                        domain, operation_id, reason, status, requested_at
                    ) VALUES(?, ?, ?, 'pending', ?)
                    """,
                    (domain, operation_id, error, now),
                )
        return True
    except Exception as record_exc:  # A locked/unavailable DB cannot record its own failure.
        logger.warning("Unable to record mirror failure for %s: %s", domain, record_exc)
        return False


def mirror_after_json_write(
    domain: str,
    callback: MirrorCallback | None,
    *,
    operation_id: str | None = None,
    db_path: str | Path = DEFAULT_DB,
    source_write_succeeded: bool = True,
    busy_timeout_ms: int | None = None,
    details: dict[str, Any] | None = None,
) -> MirrorResult:
    """Run a domain mirror after an already-successful JSON write.

    The callback owns only normalized SQLite work. It must not write JSON or
    application runtime files. A mirror failure is returned and logged, never
    raised into the JSON write path.
    """
    resolved_operation_id = operation_id or new_operation_id()
    completed_at = utc_now()
    validation_error = _validate(domain, callback)
    if validation_error:
        return MirrorResult(domain, resolved_operation_id, source_write_succeeded, False, error=validation_error, completed_at=completed_at)
    if not source_write_succeeded:
        return MirrorResult(domain, resolved_operation_id, False, False, error="JSON source write did not succeed; mirror skipped", completed_at=completed_at)

    database = Path(db_path)
    if not database.exists():
        error = f"SQLite mirror database is unavailable: {database}"
        logger.warning("%s", error)
        return MirrorResult(domain, resolved_operation_id, True, False, error=error, completed_at=completed_at)

    try:
        with connect(database) as conn:
            if busy_timeout_ms is not None:
                conn.execute(f"PRAGMA busy_timeout = {max(0, int(busy_timeout_ms))}")
            existing = conn.execute(
                "SELECT status FROM mirror_operations WHERE domain = ? AND operation_id = ?",
                (domain, resolved_operation_id),
            ).fetchone()
            if existing and existing["status"] == "success":
                return MirrorResult(domain, resolved_operation_id, True, True, idempotent=True, completed_at=completed_at)

            started_at = utc_now()
            with conn:
                if existing:
                    conn.execute(
                        """
                        UPDATE mirror_operations
                        SET status = 'running', source_write_succeeded = 1, mirror_write_succeeded = 0,
                            attempt_count = attempt_count + 1, error_text = NULL, details_json = ?,
                            started_at = ?, completed_at = NULL
                        WHERE domain = ? AND operation_id = ?
                        """,
                        (canonical_dumps(details or {}), started_at, domain, resolved_operation_id),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO mirror_operations(
                            domain, operation_id, status, source_write_succeeded,
                            mirror_write_succeeded, details_json, started_at
                        ) VALUES(?, ?, 'running', 1, 0, ?, ?)
                        """,
                        (domain, resolved_operation_id, canonical_dumps(details or {}), started_at),
                    )

            try:
                with conn:
                    callback(conn)
                    finished_at = utc_now()
                    conn.execute(
                        """
                        UPDATE mirror_operations
                        SET status = 'success', mirror_write_succeeded = 1, error_text = NULL, completed_at = ?
                        WHERE domain = ? AND operation_id = ?
                        """,
                        (finished_at, domain, resolved_operation_id),
                    )
                    _upsert_domain_status(
                        conn,
                        domain,
                        status="healthy",
                        operation_id=resolved_operation_id,
                        success_at=finished_at,
                    )
                return MirrorResult(domain, resolved_operation_id, True, True, completed_at=finished_at)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                logger.warning("SQLite mirror failed for %s operation %s: %s", domain, resolved_operation_id, error)
                recorded = _record_failure(database, domain, resolved_operation_id, error)
                return MirrorResult(domain, resolved_operation_id, True, False, reconciliation_requested=recorded, error=error, completed_at=utc_now())
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        logger.warning("SQLite mirror unavailable for %s operation %s: %s", domain, resolved_operation_id, error)
        return MirrorResult(domain, resolved_operation_id, True, False, error=error, completed_at=utc_now())


def request_reconciliation(
    domain: str,
    *,
    reason: str,
    operation_id: str | None = None,
    db_path: str | Path = DEFAULT_DB,
) -> bool:
    """Queue a read-side reconciliation request; this never imports data itself."""
    if domain not in V7_DOMAINS or not Path(db_path).exists():
        return False
    try:
        with connect(db_path) as conn, conn:
            now = utc_now()
            conn.execute(
                """
                INSERT OR IGNORE INTO mirror_reconciliation_requests(domain, operation_id, reason, status, requested_at)
                VALUES(?, ?, ?, 'pending', ?)
                """,
                (domain, operation_id, reason, now),
            )
            conn.execute(
                """
                UPDATE mirror_domain_status
                SET reconciliation_requested_at = ?, updated_at = ?
                WHERE domain = ?
                """,
                (now, now, domain),
            )
        return True
    except Exception:
        logger.exception("Unable to request reconciliation for %s", domain)
        return False


def get_mirror_status(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return read-only mirror diagnostics, including domains with no activity."""
    try:
        rows = {row["domain"]: dict(row) for row in conn.execute("SELECT * FROM mirror_domain_status ORDER BY domain")}
    except sqlite3.DatabaseError:
        return []
    return [rows.get(domain, {"domain": domain, "status": "unknown"}) for domain in V7_DOMAINS]
