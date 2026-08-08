"""SQLite-first report creation for the staged V7.3.5 authority transition.

Production report routes remain JSON-authoritative until V7.3.5e.  This module
is intentionally isolated so its transaction and artifact behavior can be
exercised before any production read/write cutover.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical_json import canonical_dumps
from .canonical_json import record_hash
from .connection import DEFAULT_DB, connect
from .report_authority_contract import ReportAuthorityPlan, build_report_authority_plan
from .runtime_paths import BASE_DIR

EXPORT_STATUS_KEY = "v7.reports.compatibility_export"
READ_FALLBACK_KEY = "v7.reports.read_fallback"
REPAIR_STATUS_KEY = "v7.reports.artifact_repair"
DELETION_STATUS_KEY = "v7.reports.deletion"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class ReportSaveResult:
    meta: dict[str, Any]
    authority: str
    compatibility_export: str
    html_export: str
    warning: str | None = None

    def response_meta(self) -> dict[str, Any]:
        result = dict(self.meta)
        result.update({
            "authority": self.authority,
            "compatibility_export": self.compatibility_export,
            "html_export": self.html_export,
        })
        if self.warning:
            result["warning"] = self.warning
        return result


@dataclass(frozen=True, slots=True)
class AuthoritativeReport:
    meta: dict[str, Any]
    wrapped_snapshot: dict[str, Any]
    status: str
    compatibility_export_status: str
    html_export_status: str


@dataclass(frozen=True, slots=True)
class ReportDeletionResult:
    report_id: str
    trip_id: str
    status: str
    deleted_files: tuple[str, ...]
    warning: str | None = None


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".v7-export.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _payload_fields(wrapped: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    payload = wrapped.get("payload") if isinstance(wrapped.get("payload"), dict) else {}
    summary = wrapped.get("summary") if isinstance(wrapped.get("summary"), dict) else {}
    intel = payload.get("intel") if isinstance(payload.get("intel"), dict) else {}
    return payload, summary, intel


def _selected_fields(meta: dict[str, Any], payload: dict[str, Any]) -> tuple[str, str, int | None]:
    date = _text(meta.get("selected_forecast_date") or payload.get("selected_forecast_date") or payload.get("forecast_date"))
    label = _text(meta.get("selected_forecast_label") or payload.get("selected_forecast_label"))
    raw_index = meta.get("forecast_day_index", payload.get("forecast_day_index"))
    try:
        index = int(raw_index) if raw_index not in (None, "") else None
    except (TypeError, ValueError):
        index = None
    return date, label, index


def _upsert_authoritative_report(conn, plan: ReportAuthorityPlan, meta: dict[str, Any], wrapped: dict[str, Any]) -> None:
    payload, summary, intel = _payload_fields(wrapped)
    selected_date, selected_label, forecast_index = _selected_fields(meta, payload)
    created_at = _text(meta.get("created") or payload.get("saved_at")) or _utc_now()
    target_species = _text(payload.get("target_species") or summary.get("target_species") or intel.get("target_species"))
    focus_waterbody_id = _text(payload.get("focus_waterbody_id") or summary.get("focus_waterbody_id") or intel.get("focus_waterbody_id"))
    zip_code = _text(meta.get("zip") or payload.get("zip") or summary.get("zip") or intel.get("zip"))
    title = _text(meta.get("title") or payload.get("title")) or "Trip Report"
    json_path = f"reports/{plan.json_filename}"
    html_path = f"reports/{plan.html_filename}"

    conn.execute(
        """
        INSERT INTO trips(
          id, title, zip, target_species, focus_waterbody_id, selected_forecast_date,
          selected_forecast_label, forecast_day_index, started_at, updated_at,
          legacy_payload_json, source_path, source_hash, source_key
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          title=excluded.title, zip=excluded.zip, target_species=excluded.target_species,
          focus_waterbody_id=excluded.focus_waterbody_id,
          selected_forecast_date=excluded.selected_forecast_date,
          selected_forecast_label=excluded.selected_forecast_label,
          forecast_day_index=excluded.forecast_day_index, updated_at=excluded.updated_at,
          legacy_payload_json=excluded.legacy_payload_json, source_hash=excluded.source_hash
        """,
        (
            plan.trip_id, title, zip_code, target_species, focus_waterbody_id, selected_date,
            selected_label, forecast_index, created_at, _utc_now(),
            canonical_dumps({"report_meta": meta, "snapshot": wrapped}), json_path,
            plan.authoritative_payload_hash, plan.report_id,
        ),
    )
    conn.execute(
        """
        INSERT INTO trip_reports(
          id, trip_id, report_title, zip, selected_forecast_date,
          selected_forecast_label, forecast_day_index, json_path, html_path, view_url,
          legacy_payload_json, created_at, updated_at, status, deleted_at,
          snapshot_payload_json, authoritative_payload_hash,
          compatibility_export_hash, compatibility_export_status,
          compatibility_exported_at, html_export_hash, html_export_status,
          html_exported_at, artifact_error
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', NULL, ?, ?, NULL, 'pending', NULL, NULL, 'pending', NULL, NULL)
        ON CONFLICT(id) DO UPDATE SET
          trip_id=excluded.trip_id, report_title=excluded.report_title, zip=excluded.zip,
          selected_forecast_date=excluded.selected_forecast_date,
          selected_forecast_label=excluded.selected_forecast_label,
          forecast_day_index=excluded.forecast_day_index, json_path=excluded.json_path,
          html_path=excluded.html_path, view_url=excluded.view_url,
          legacy_payload_json=excluded.legacy_payload_json,
          updated_at=excluded.updated_at, status='active', deleted_at=NULL,
          snapshot_payload_json=excluded.snapshot_payload_json,
          authoritative_payload_hash=excluded.authoritative_payload_hash,
          compatibility_export_hash=NULL, compatibility_export_status='pending',
          compatibility_exported_at=NULL, html_export_hash=NULL,
          html_export_status='pending', html_exported_at=NULL, artifact_error=NULL
        """,
        (
            plan.report_id, plan.trip_id, title, zip_code, selected_date, selected_label,
            forecast_index, json_path, html_path, _text(meta.get("view_url")) or f"/api/reports/view/{plan.report_id}",
            canonical_dumps(meta), created_at, _utc_now(), plan.snapshot_payload_json,
            plan.authoritative_payload_hash,
        ),
    )
    recommendation_authority = conn.execute(
        "SELECT authority FROM data_authority WHERE domain='recommendations'"
    ).fetchone()
    if recommendation_authority and str(recommendation_authority["authority"]) == "sqlite":
        # Recommendation history is a persisted companion to the report
        # snapshot. Live Smart Intelligence remains computed by the app.
        from .recommendations_authority import persist_report_recommendation_history

        persist_report_recommendation_history(
            conn,
            report_id=plan.report_id,
            trip_id=plan.trip_id,
            meta=meta,
            wrapped_snapshot=wrapped,
        )


def _active_report_index(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT legacy_payload_json FROM trip_reports WHERE status = 'active' ORDER BY created_at DESC, id DESC"
    ).fetchall()
    records: list[dict[str, Any]] = []
    for row in rows:
        try:
            item = json.loads(row["legacy_payload_json"] or "{}")
        except Exception:
            item = {}
        if isinstance(item, dict):
            records.append(item)
    return records


def _safe_artifact_paths(meta: dict[str, Any], report_id: str, reports_dir: Path) -> list[Path]:
    expected = (f"{report_id}.json", f"{report_id}.html")
    configured = (str(meta.get("json_file") or expected[0]), str(meta.get("html_file") or expected[1]))
    if configured != expected:
        raise ValueError("SQLite report artifact filenames are invalid")
    return [reports_dir / filename for filename in expected]


def _record_lifecycle_status(db_path: str | Path, payload: dict[str, Any]) -> None:
    now = _utc_now()
    with connect(db_path) as conn:
        with conn:
            conn.execute(
                """INSERT INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
                (DELETION_STATUS_KEY, canonical_dumps(payload), now),
            )


def _cleanup_report_artifacts(meta: dict[str, Any], report_id: str, *, db_path: str | Path, index_path: str | Path, reports_dir: str | Path) -> tuple[list[str], str | None]:
    """Remove generated artifacts only after the authoritative state changed."""
    deleted: list[str] = []
    errors: list[str] = []
    try:
        for path in _safe_artifact_paths(meta, report_id, Path(reports_dir)):
            if path.exists():
                path.unlink()
                deleted.append(path.name)
    except Exception as exc:
        errors.append(f"artifact file cleanup failed: {exc}")
    try:
        with connect(db_path, read_only=True) as conn:
            active_index = _active_report_index(conn)
        _atomic_write(Path(index_path), json.dumps(active_index, indent=2, ensure_ascii=False))
    except Exception as exc:
        errors.append(f"report index cleanup failed: {exc}")
    return deleted, "; ".join(errors) or None


def soft_delete_authoritative_report(
    report_id: str,
    *,
    db_path: str | Path = DEFAULT_DB,
    index_path: str | Path,
    reports_dir: str | Path,
) -> ReportDeletionResult:
    """Mark one report deleted before removing any generated artifacts.

    Trips remain untouched. A later restore can reactivate the report and
    regenerate JSON/HTML from its retained snapshot.
    """
    report_id = _text(report_id)
    if not report_id or "/" in report_id or "\\" in report_id or ".." in report_id:
        raise ValueError("Invalid report id")
    database = Path(db_path)
    with connect(database) as conn:
        with conn:
            row = conn.execute("SELECT id, trip_id, legacy_payload_json FROM trip_reports WHERE id = ?", (report_id,)).fetchone()
            if row is None:
                raise LookupError("SQLite report not found")
            if conn.execute("SELECT status FROM trip_reports WHERE id = ?", (report_id,)).fetchone()["status"] != "active":
                raise LookupError("SQLite report is not active")
            try:
                meta = json.loads(row["legacy_payload_json"] or "{}")
            except Exception:
                meta = {}
            if not isinstance(meta, dict):
                meta = {}
            deleted_at = _utc_now()
            conn.execute(
                """UPDATE trip_reports SET status='deleted', deleted_at=?, updated_at=?,
                   compatibility_export_status='pending', html_export_status='pending', artifact_error=NULL WHERE id=?""",
                (deleted_at, deleted_at, report_id),
            )

    deleted_files, cleanup_error = _cleanup_report_artifacts(meta, report_id, db_path=database, index_path=index_path, reports_dir=reports_dir)
    _set_artifact_status(
        database, report_id,
        json_status="not_applicable" if not cleanup_error else "failed",
        html_status="not_applicable" if not cleanup_error else "failed",
        error=cleanup_error,
    )
    result = ReportDeletionResult(report_id, _text(row["trip_id"]), "deleted", tuple(deleted_files), cleanup_error)
    _record_lifecycle_status(database, {
        "action": "delete", "report_id": report_id, "trip_id": result.trip_id,
        "status": result.status, "deleted_files": deleted_files, "error": cleanup_error, "at": _utc_now(),
    })
    return result


def soft_delete_all_authoritative_reports(
    *,
    db_path: str | Path = DEFAULT_DB,
    index_path: str | Path,
    reports_dir: str | Path,
) -> list[ReportDeletionResult]:
    """Soft-delete all active reports before any JSON/HTML cleanup begins."""
    database = Path(db_path)
    with connect(database, read_only=True) as conn:
        ids = [str(row["id"]) for row in conn.execute("SELECT id FROM trip_reports WHERE status='active' ORDER BY created_at, id")]
    return [soft_delete_authoritative_report(report_id, db_path=database, index_path=index_path, reports_dir=reports_dir) for report_id in ids]


def restore_authoritative_report(
    report_id: str,
    *,
    render_html,
    db_path: str | Path = DEFAULT_DB,
    index_path: str | Path,
    reports_dir: str | Path,
) -> ReportSaveResult:
    """Reactivate a soft-deleted report and regenerate its compatibility artifacts."""
    report_id = _text(report_id)
    if not report_id or "/" in report_id or "\\" in report_id or ".." in report_id:
        raise ValueError("Invalid report id")
    database = Path(db_path)
    with connect(database) as conn:
        with conn:
            row = conn.execute("SELECT id FROM trip_reports WHERE id = ? AND status = 'deleted'", (report_id,)).fetchone()
            if row is None:
                raise LookupError("Deleted SQLite report not found")
            conn.execute(
                "UPDATE trip_reports SET status='active', deleted_at=NULL, updated_at=?, artifact_error=NULL WHERE id=?",
                (_utc_now(), report_id),
            )
    result = repair_report_artifacts(report_id, render_html=render_html, db_path=database, index_path=index_path, reports_dir=reports_dir)
    _record_lifecycle_status(database, {
        "action": "restore", "report_id": report_id, "status": "active",
        "error": result.warning, "at": _utc_now(),
    })
    return result


def list_authoritative_report_metadata(db_path: str | Path = DEFAULT_DB) -> list[dict[str, Any]]:
    """Return active report metadata from SQLite without requiring artifacts."""
    with connect(db_path, read_only=True) as conn:
        return _active_report_index(conn)


def reconcile_legacy_report_snapshots(
    *,
    db_path: str | Path = DEFAULT_DB,
    index_path: str | Path,
    reports_dir: str | Path,
) -> dict[str, Any]:
    """Hydrate imported legacy report rows with their complete JSON snapshots.

    This is a pre-transition reconciliation step. JSON remains authoritative
    while it runs, and no JSON or HTML artifact is modified.
    """
    index = Path(index_path)
    directory = Path(reports_dir)
    try:
        index_payload = json.loads(index.read_text(encoding="utf-8")) if index.exists() else []
    except Exception as exc:
        raise ValueError(f"Reports index is unreadable: {exc}") from exc
    if isinstance(index_payload, dict):
        index_payload = index_payload.get("reports", [])
    if not isinstance(index_payload, list):
        raise ValueError("Reports index must be a list or object with reports list")
    hydrated: list[str] = []
    errors: list[str] = []
    database = Path(db_path)
    with connect(database) as conn:
        with conn:
            for item in index_payload:
                if not isinstance(item, dict):
                    continue
                report_id = _text(item.get("id"))
                if not report_id:
                    errors.append("Report index contains an item without an id")
                    continue
                json_file = str(item.get("json_file") or f"{report_id}.json")
                if json_file != f"{report_id}.json":
                    errors.append(f"{report_id}: invalid JSON artifact filename")
                    continue
                path = directory / json_file
                if not path.exists():
                    errors.append(f"{report_id}: snapshot JSON is missing")
                    continue
                try:
                    wrapped = json.loads(path.read_text(encoding="utf-8"))
                    if not isinstance(wrapped, dict):
                        raise ValueError("snapshot is not an object")
                    payload = wrapped.get("payload") if isinstance(wrapped.get("payload"), dict) else None
                    if payload is None:
                        raise ValueError("snapshot payload is missing")
                    if not isinstance(wrapped.get("meta"), dict):
                        wrapped["meta"] = dict(item)
                    if not isinstance(wrapped.get("summary"), dict):
                        wrapped["summary"] = {}
                except Exception as exc:
                    errors.append(f"{report_id}: snapshot JSON is invalid: {exc}")
                    continue
                row = conn.execute("SELECT id FROM trip_reports WHERE id = ?", (report_id,)).fetchone()
                if row is None:
                    errors.append(f"{report_id}: report is absent from SQLite")
                    continue
                conn.execute(
                    """UPDATE trip_reports SET snapshot_payload_json=?, authoritative_payload_hash=?,
                       legacy_payload_json=?, updated_at=? WHERE id=?""",
                    (canonical_dumps(wrapped), record_hash(wrapped), canonical_dumps(item), _utc_now(), report_id),
                )
                hydrated.append(report_id)
    return {"hydrated": hydrated, "errors": errors, "ok": not errors}


def report_transition_preflight(db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    """Return report-specific transition blockers without changing state."""
    with connect(db_path, read_only=True) as conn:
        authority_row = conn.execute("SELECT authority FROM data_authority WHERE domain='reports'").fetchone()
        rows = [dict(row) for row in conn.execute("SELECT id, status, snapshot_payload_json, json_path, html_path FROM trip_reports WHERE status='active' ORDER BY id")]
    missing_snapshots = [str(row["id"]) for row in rows if not row["snapshot_payload_json"]]
    invalid_paths = [str(row["id"]) for row in rows if not _text(row["json_path"]).endswith(f"{row['id']}.json") or not _text(row["html_path"]).endswith(f"{row['id']}.html")]
    return {
        "authority": str(authority_row["authority"]) if authority_row else "missing",
        "active_report_count": len(rows),
        "missing_snapshot_ids": missing_snapshots,
        "invalid_artifact_path_ids": invalid_paths,
        "ready": not missing_snapshots and not invalid_paths,
    }


def activate_reports_authority(
    *,
    render_html,
    db_path: str | Path = DEFAULT_DB,
    index_path: str | Path,
    reports_dir: str | Path,
) -> list[ReportSaveResult]:
    """Activate report authority, regenerate artifacts, and leave manifest work to caller.

    If artifact generation fails after the database marker changes, callers must
    leave the external authority manifest unchanged. That deliberate marker
    conflict fail-closes report writes until an operator repairs the state.
    """
    database = Path(db_path)
    preflight = report_transition_preflight(database)
    if preflight["authority"] != "json":
        raise ValueError(f"Reports must be JSON-authoritative before transition, found {preflight['authority']!r}")
    if not preflight["ready"]:
        raise ValueError(f"Report transition preflight failed: {preflight}")
    with connect(database) as conn:
        with conn:
            conn.execute(
                """UPDATE data_authority SET authority='sqlite', note=?, updated_at=? WHERE domain='reports'""",
                ("SQLite is authoritative for report identity, metadata, trip links, and deletion; JSON/HTML are compatibility artifacts.", _utc_now()),
            )
    results: list[ReportSaveResult] = []
    try:
        for meta in list_authoritative_report_metadata(database):
            results.append(repair_report_artifacts(str(meta.get("id") or ""), render_html=render_html, db_path=database, index_path=index_path, reports_dir=reports_dir))
    except Exception:
        raise
    failures = [result for result in results if result.warning]
    if failures:
        raise RuntimeError(f"Compatibility artifact export failed for {len(failures)} report(s)")
    return results


def _normalize_snapshot(row: Any) -> dict[str, Any]:
    raw = json.loads(row["snapshot_payload_json"] or "{}")
    if not isinstance(raw, dict):
        raise ValueError("SQLite report snapshot must be an object")
    legacy_meta = json.loads(row["legacy_payload_json"] or "{}")
    if not isinstance(legacy_meta, dict):
        legacy_meta = {}
    if not isinstance(raw.get("meta"), dict):
        raw["meta"] = legacy_meta
    if not isinstance(raw.get("payload"), dict):
        # Older snapshot envelopes may have stored the user payload directly.
        raw = {"meta": legacy_meta, "payload": raw, "summary": {}}
    if not isinstance(raw.get("summary"), dict):
        raw["summary"] = {}
    return raw


def load_authoritative_report(report_id: str, db_path: str | Path = DEFAULT_DB) -> AuthoritativeReport:
    """Load a complete active report snapshot from SQLite.

    A legacy mirrored report without a full snapshot intentionally raises
    ``LookupError`` so callers can use their explicitly-labelled JSON fallback
    during the staged-read period.
    """
    with connect(db_path, read_only=True) as conn:
        row = conn.execute(
            "SELECT * FROM trip_reports WHERE id = ? AND status = 'active'", (report_id,)
        ).fetchone()
    if row is None:
        raise LookupError(f"SQLite report not found: {report_id}")
    if not row["snapshot_payload_json"]:
        raise LookupError(f"SQLite report snapshot is unavailable for legacy report: {report_id}")
    snapshot = _normalize_snapshot(row)
    meta = snapshot.get("meta") if isinstance(snapshot.get("meta"), dict) else {}
    if not meta:
        meta = json.loads(row["legacy_payload_json"] or "{}")
    if not isinstance(meta, dict):
        raise ValueError("SQLite report metadata is invalid")
    return AuthoritativeReport(
        meta=meta,
        wrapped_snapshot=snapshot,
        status=str(row["status"] or "active"),
        compatibility_export_status=str(row["compatibility_export_status"] or "not_applicable"),
        html_export_status=str(row["html_export_status"] or "not_applicable"),
    )


def record_json_read_fallback(report_id: str, reason: str, db_path: str | Path = DEFAULT_DB) -> None:
    """Record a visible staged-read fallback without changing report data."""
    now = _utc_now()
    with connect(db_path) as conn:
        with conn:
            conn.execute(
                """INSERT INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
                (READ_FALLBACK_KEY, canonical_dumps({"report_id": report_id, "reason": reason, "at": now}), now),
            )


def repair_report_artifacts(
    report_id: str,
    *,
    render_html,
    db_path: str | Path = DEFAULT_DB,
    index_path: str | Path,
    reports_dir: str | Path,
) -> ReportSaveResult:
    """Regenerate compatibility JSON and printable HTML from an SQLite snapshot."""
    report = load_authoritative_report(report_id, db_path)
    meta = report.meta
    snapshot = report.wrapped_snapshot
    report_id = str(meta.get("id") or report_id)
    json_filename = str(meta.get("json_file") or f"{report_id}.json")
    html_filename = str(meta.get("html_file") or f"{report_id}.html")
    if json_filename != f"{report_id}.json" or html_filename != f"{report_id}.html":
        raise ValueError("SQLite report artifact filenames are invalid")
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
    selected_date = _text(meta.get("selected_forecast_date") or payload.get("selected_forecast_date"))
    rendered_html = render_html(meta, payload, selected_forecast_date=selected_date)
    plan = build_report_authority_plan(meta, snapshot, rendered_html)
    database, index, directory = Path(db_path), Path(index_path), Path(reports_dir)

    json_status, html_status = "pending", "pending"
    errors: list[str] = []
    try:
        with connect(database, read_only=True) as conn:
            active_index = _active_report_index(conn)
        _atomic_write(directory / json_filename, json.dumps(snapshot, indent=2, ensure_ascii=False))
        _atomic_write(index, json.dumps(active_index, indent=2, ensure_ascii=False))
        json_status = "ok"
    except Exception as exc:
        json_status = "failed"
        errors.append(f"Compatibility JSON repair failed: {exc}")
    try:
        _atomic_write(directory / html_filename, rendered_html)
        html_status = "ok"
    except Exception as exc:
        html_status = "failed"
        errors.append(f"Printable HTML repair failed: {exc}")
    error = "; ".join(errors) or None
    _set_artifact_status(
        database, report_id, json_status=json_status, html_status=html_status,
        json_hash=plan.authoritative_payload_hash if json_status == "ok" else None,
        html_hash=plan.html_export_hash if html_status == "ok" else None, error=error,
    )
    now = _utc_now()
    with connect(database) as conn:
        with conn:
            conn.execute(
                """INSERT INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
                (REPAIR_STATUS_KEY, canonical_dumps({"report_id": report_id, "json": json_status, "html": html_status, "error": error, "at": now}), now),
            )
    return ReportSaveResult(dict(meta), "sqlite", json_status, html_status, error)


def _set_artifact_status(
    db_path: str | Path,
    report_id: str,
    *,
    json_status: str,
    html_status: str,
    json_hash: str | None = None,
    html_hash: str | None = None,
    error: str | None = None,
) -> None:
    now = _utc_now()
    with connect(db_path) as conn:
        with conn:
            conn.execute(
                """
                UPDATE trip_reports SET compatibility_export_status=?, compatibility_export_hash=?,
                  compatibility_exported_at=?, html_export_status=?, html_export_hash=?,
                  html_exported_at=?, artifact_error=?, updated_at=? WHERE id=?
                """,
                (
                    json_status, json_hash, now if json_status == "ok" else None,
                    html_status, html_hash, now if html_status == "ok" else None,
                    error, now, report_id,
                ),
            )
            status_payload = {
                "domain": "reports", "report_id": report_id,
                "status": "ok" if json_status == "ok" and html_status == "ok" else "failed",
                "compatibility_export": json_status, "html_export": html_status,
                "error": error,
            }
            conn.execute(
                """INSERT INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
                (EXPORT_STATUS_KEY, canonical_dumps(status_payload), now),
            )


def save_report_sqlite_authoritative(
    meta: dict[str, Any],
    wrapped_snapshot: dict[str, Any],
    rendered_html: str,
    *,
    db_path: str | Path = DEFAULT_DB,
    index_path: str | Path,
    reports_dir: str | Path,
) -> ReportSaveResult:
    """Commit a report snapshot, then produce repairable compatibility artifacts."""
    plan = build_report_authority_plan(meta, wrapped_snapshot, rendered_html)
    database = Path(db_path)
    index = Path(index_path)
    directory = Path(reports_dir)
    with connect(database) as conn:
        with conn:
            _upsert_authoritative_report(conn, plan, meta, wrapped_snapshot)

    json_status = "pending"
    html_status = "pending"
    error_parts: list[str] = []
    try:
        with connect(database, read_only=True) as conn:
            active_index = _active_report_index(conn)
        _atomic_write(directory / plan.json_filename, json.dumps(wrapped_snapshot, indent=2, ensure_ascii=False))
        _atomic_write(index, json.dumps(active_index, indent=2, ensure_ascii=False))
        json_status = "ok"
    except Exception as exc:
        json_status = "failed"
        error_parts.append(f"Compatibility JSON export failed: {exc}")

    try:
        _atomic_write(directory / plan.html_filename, rendered_html)
        html_status = "ok"
    except Exception as exc:
        html_status = "failed"
        error_parts.append(f"Printable HTML export failed: {exc}")

    error = "; ".join(error_parts) or None
    _set_artifact_status(
        database,
        plan.report_id,
        json_status=json_status,
        html_status=html_status,
        json_hash=plan.authoritative_payload_hash if json_status == "ok" else None,
        html_hash=plan.html_export_hash if html_status == "ok" else None,
        error=error,
    )
    # Queue only completed local artifacts. Drive remains an optional secondary
    # export, so any queue/upload issue is intentionally outside this save.
    cloud_warning: str | None = None
    if json_status == "ok" and html_status == "ok":
        cloud_auto_enabled = False
        try:
            from integrations.google_drive import get_config, queue_report_export, upload_pending

            cloud_auto_enabled = get_config().auto_reports
            queue_report_export(plan.report_id, db_path=database, reports_dir=directory)
            if cloud_auto_enabled:
                cloud_result = upload_pending(db_path=database, object_id=plan.report_id)
                if not cloud_result.get("ok"):
                    cloud_warning = "Report saved locally; Google Drive export is pending repair."
        except Exception:
            if cloud_auto_enabled:
                cloud_warning = "Report saved locally; Google Drive export could not be queued."
    warning = "; ".join(part for part in (error, cloud_warning) if part) or None
    return ReportSaveResult(
        meta=dict(meta), authority="sqlite", compatibility_export=json_status,
        html_export=html_status, warning=warning,
    )
