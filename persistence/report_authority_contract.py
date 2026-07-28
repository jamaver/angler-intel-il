"""Pure report authority contract helpers for the staged V7.3.5 transition.

This module deliberately has no Flask, filesystem, or route dependencies.
V7.3.5a uses it to define the SQLite record shape and artifact rules without
changing production report writes, reads, or deletion behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical_json import canonical_dumps, record_hash


@dataclass(frozen=True, slots=True)
class ReportAuthorityPlan:
    """Validated material required by a later SQLite-first report save."""

    report_id: str
    trip_id: str
    status: str
    snapshot_payload_json: str
    authoritative_payload_hash: str
    json_filename: str
    html_filename: str
    html_export_hash: str


def _safe_report_id(value: Any) -> str:
    report_id = str(value or "").strip()
    if not report_id or "/" in report_id or "\\" in report_id or ".." in report_id:
        raise ValueError("Report id must be a non-empty safe identifier")
    return report_id


def _artifact_filename(value: Any, report_id: str, suffix: str) -> str:
    filename = str(value or "").strip()
    expected = f"{report_id}{suffix}"
    if filename != expected or "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError(f"Expected safe report artifact filename {expected!r}")
    return filename


def build_report_authority_plan(
    meta: dict[str, Any],
    wrapped_snapshot: dict[str, Any],
    rendered_html: str,
) -> ReportAuthorityPlan:
    """Validate a full snapshot before a future SQLite-first save.

    A report currently maps deterministically to a same-ID trip.  A later
    report revision model may provide an explicit ``trip_id`` while preserving
    this fallback for legacy reports.
    """
    if not isinstance(meta, dict) or not isinstance(wrapped_snapshot, dict):
        raise ValueError("Report metadata and wrapped snapshot must be objects")
    if not isinstance(wrapped_snapshot.get("meta"), dict):
        raise ValueError("Wrapped report snapshot must include metadata")
    if not isinstance(wrapped_snapshot.get("payload"), dict):
        raise ValueError("Wrapped report snapshot must include a payload object")
    if not isinstance(wrapped_snapshot.get("summary"), dict):
        raise ValueError("Wrapped report snapshot must include a summary object")
    if not isinstance(rendered_html, str) or not rendered_html.strip():
        raise ValueError("Rendered report HTML must be non-empty")

    report_id = _safe_report_id(meta.get("id"))
    snapshot_meta = wrapped_snapshot["meta"]
    if _safe_report_id(snapshot_meta.get("id")) != report_id:
        raise ValueError("Report metadata and snapshot metadata IDs disagree")

    trip_id = _safe_report_id(meta.get("trip_id") or snapshot_meta.get("trip_id") or report_id)
    return ReportAuthorityPlan(
        report_id=report_id,
        trip_id=trip_id,
        status="active",
        snapshot_payload_json=canonical_dumps(wrapped_snapshot),
        authoritative_payload_hash=record_hash(wrapped_snapshot),
        json_filename=_artifact_filename(meta.get("json_file"), report_id, ".json"),
        html_filename=_artifact_filename(meta.get("html_file"), report_id, ".html"),
        html_export_hash=record_hash({"html": rendered_html}),
    )
