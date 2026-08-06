"""SQLite-authoritative trip completion records for V7.5.0."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical_json import canonical_dumps
from .connection import DEFAULT_DB, connect

FOLLOWED_PLAN_VALUES = {"exact", "partial", "substituted", "changed_water", "changed_target", "unknown", "did_not_fish"}


class TripCompletionError(ValueError):
    """Raised for user-fixable trip completion input errors."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _optional_timestamp(value: Any, label: str) -> str | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat(timespec="seconds")
    except ValueError as exc:
        raise TripCompletionError(f"{label} must be a valid date and time") from exc


def _optional_date(value: Any, label: str) -> str | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw[:10]).date().isoformat()
    except ValueError as exc:
        raise TripCompletionError(f"{label} must use YYYY-MM-DD format") from exc


def _optional_count(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise TripCompletionError("catch_count must be a whole number") from exc
    if count < 0:
        raise TripCompletionError("catch_count cannot be negative")
    return count


def _optional_rating(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        rating = int(value)
    except (TypeError, ValueError) as exc:
        raise TripCompletionError("satisfaction must be a number from 1 to 5") from exc
    if not 1 <= rating <= 5:
        raise TripCompletionError("satisfaction must be a number from 1 to 5")
    return rating


def _normalize_completion(payload: dict[str, Any]) -> dict[str, Any]:
    report_id = _text(payload.get("report_id"))
    if not report_id or "/" in report_id or "\\" in report_id or ".." in report_id:
        raise TripCompletionError("A valid saved report is required")
    occurred_raw = payload.get("trip_occurred", True)
    occurred = occurred_raw if isinstance(occurred_raw, bool) else str(occurred_raw).strip().lower() not in {"0", "false", "no", "off"}
    followed = _text(payload.get("followed_plan") or "unknown").lower()
    if followed not in FOLLOWED_PLAN_VALUES:
        raise TripCompletionError("followed_plan is not recognized")
    if not occurred:
        followed = "did_not_fish"
    catch_count = _optional_count(payload.get("catch_count"))
    if not occurred:
        catch_count = 0
    outcome = "did_not_fish" if not occurred else ("no_catch" if catch_count == 0 else "completed")
    gear_refs = payload.get("gear_refs") if isinstance(payload.get("gear_refs"), dict) else {}
    return {
        "report_id": report_id,
        "trip_occurred": 1 if occurred else 0,
        "outcome": outcome,
        "actual_waterbody": _text(payload.get("actual_waterbody")),
        "actual_target_species": _text(payload.get("actual_target_species")),
        "actual_trip_date": _optional_date(payload.get("actual_trip_date"), "actual_trip_date"),
        "started_at": _optional_timestamp(payload.get("started_at"), "started_at"),
        "ended_at": _optional_timestamp(payload.get("ended_at"), "ended_at"),
        "followed_plan": followed,
        "catch_count": catch_count,
        "satisfaction": _optional_rating(payload.get("satisfaction")),
        "gear_refs": {str(key): _text(value) for key, value in gear_refs.items() if _text(value)},
        "notes": _text(payload.get("notes")),
    }


def record_trip_completion(
    payload: dict[str, Any],
    db_path: str | Path = DEFAULT_DB,
    *,
    manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create or update the latest outcome for an active authoritative report."""
    completion = _normalize_completion(payload)
    now = _now()
    with connect(db_path) as conn:
        with conn:
            report = conn.execute(
                "SELECT id, trip_id, zip, selected_forecast_date FROM trip_reports WHERE id=? AND status='active'",
                (completion["report_id"],),
            ).fetchone()
            if not report:
                raise TripCompletionError("Saved report was not found or is deleted")
            trip_id = _text(report["trip_id"])
            latest = conn.execute(
                "SELECT id, completed_at FROM trip_outcomes WHERE report_id=? ORDER BY completed_at DESC, id DESC LIMIT 1",
                (completion["report_id"],),
            ).fetchone()
            legacy = {
                "schema": "v7.5.1.1-adherence-hardening",
                "report_id": completion["report_id"],
                "trip_id": trip_id or None,
                "saved_at": now,
                **completion,
            }
            values = (
                trip_id or None,
                completion["report_id"],
                completion["outcome"],
                completion["notes"],
                canonical_dumps(legacy),
                completion["trip_occurred"],
                completion["actual_waterbody"] or None,
                completion["actual_target_species"] or None,
                completion["actual_trip_date"],
                completion["started_at"],
                completion["ended_at"],
                completion["followed_plan"],
                completion["catch_count"],
                completion["satisfaction"],
                canonical_dumps(completion["gear_refs"]),
                _text(latest["completed_at"]) if latest and _text(latest["completed_at"]) else now,
                now,
            )
            if latest:
                conn.execute(
                    """UPDATE trip_outcomes SET trip_id=?, report_id=?, outcome=?, notes=?, legacy_payload_json=?,
                       trip_occurred=?, actual_waterbody=?, actual_target_species=?, actual_trip_date=?, started_at=?, ended_at=?,
                       followed_plan=?, catch_count=?, satisfaction=?, gear_refs_json=?, completed_at=?, updated_at=?
                       WHERE id=?""",
                    (*values, latest["id"]),
                )
                outcome_id = int(latest["id"])
            else:
                cursor = conn.execute(
                    """INSERT INTO trip_outcomes(trip_id, report_id, outcome, notes, legacy_payload_json,
                       trip_occurred, actual_waterbody, actual_target_species, actual_trip_date, started_at, ended_at,
                       followed_plan, catch_count, satisfaction, gear_refs_json, completed_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    values,
                )
                outcome_id = int(cursor.lastrowid)
            from .recommendations_authority import sync_recommendation_adherence
            try:
                adherence = sync_recommendation_adherence(
                    conn,
                    report_id=completion["report_id"],
                    trip_id=trip_id or None,
                    trip_outcome_id=outcome_id,
                    adherence=completion["followed_plan"],
                    trip_occurred=bool(completion["trip_occurred"]),
                    outcome=completion["outcome"],
                    catch_count=completion["catch_count"],
                    satisfaction=completion["satisfaction"],
                    notes=completion["notes"],
                    db_path=db_path,
                    manifest_path=manifest_path,
                )
            except Exception as exc:
                adherence = {
                    "status": "unavailable",
                    "reason": f"Recommendation adherence was not recorded: {type(exc).__name__}",
                    "report_id": completion["report_id"],
                    "recommendation_id": f"{completion['report_id']}-best-bet",
                }
    return {
        "ok": True, "id": outcome_id, "trip_id": trip_id or None,
        "report_id": completion["report_id"], **completion,
        "completed_at": _text(latest["completed_at"]) if latest and _text(latest["completed_at"]) else now,
        "updated_at": now,
        "recommendation_adherence": adherence,
    }


def load_trip_completion(report_id: str, db_path: str | Path = DEFAULT_DB) -> dict[str, Any] | None:
    with connect(db_path, read_only=True) as conn:
        row = conn.execute(
            """SELECT id, trip_id, report_id, outcome, notes, trip_occurred, actual_waterbody,
               actual_target_species, actual_trip_date, started_at, ended_at, followed_plan, catch_count, satisfaction,
               gear_refs_json, completed_at, updated_at
               FROM trip_outcomes WHERE report_id=? ORDER BY completed_at DESC, id DESC LIMIT 1""",
            (report_id,),
        ).fetchone()
    if not row:
        return None
    payload = dict(row)
    try:
        payload["gear_refs"] = json.loads(payload.pop("gear_refs_json") or "{}")
    except json.JSONDecodeError:
        payload["gear_refs"] = {}
    payload["trip_occurred"] = bool(payload.get("trip_occurred"))
    return payload
