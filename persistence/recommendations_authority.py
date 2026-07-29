"""SQLite authority services for persisted recommendation and intelligence history.

Live Smart Intelligence remains application-computed.  This module owns only
the durable snapshots and feedback associated with SQLite-authoritative reports.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical_json import canonical_dumps, record_hash
from .connection import DEFAULT_DB, connect


FEEDBACK_STATUS_KEY = "v7.recommendations.feedback"
RECONCILIATION_STATUS_KEY = "v7.recommendations.reconciliation"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _wrapped_snapshot(value: Any, legacy_meta: Any = None) -> dict[str, Any]:
    wrapped = _as_dict(value)
    meta = _as_dict(wrapped.get("meta")) or _as_dict(legacy_meta)
    payload = _as_dict(wrapped.get("payload"))
    if not payload and wrapped:
        payload = dict(wrapped)
    summary = _as_dict(wrapped.get("summary"))
    return {"meta": meta, "payload": payload, "summary": summary}


def _recommendation_source(wrapped: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    payload = _as_dict(wrapped.get("payload"))
    summary = _as_dict(wrapped.get("summary"))
    intel = _as_dict(payload.get("intel"))
    best_bet = _as_dict(summary.get("best_bet"))
    if not best_bet:
        best_bet = _as_dict(intel.get("best_bet"))
    return payload, intel, best_bet


def _recommendations_authoritative(conn) -> bool:
    row = conn.execute("SELECT authority FROM data_authority WHERE domain='recommendations'").fetchone()
    return bool(row and str(row["authority"]) == "sqlite")


def persist_report_recommendation_history(
    conn,
    *,
    report_id: str,
    trip_id: str,
    meta: dict[str, Any],
    wrapped_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Upsert deterministic intelligence and best-bet records for one report.

    Callers own the surrounding SQLite transaction. Feedback is intentionally
    retained across a report refresh because it describes the user's outcome,
    not an implementation detail of an individual export pass.
    """
    wrapped = _wrapped_snapshot(wrapped_snapshot, meta)
    payload, intelligence, best_bet = _recommendation_source(wrapped)
    snapshot_id = f"{report_id}-intel"
    recommendation_id = f"{report_id}-best-bet"
    created_at = _text(meta.get("created") or payload.get("saved_at")) or _now()
    target_species = _text(
        payload.get("target_species")
        or _as_dict(payload.get("summary")).get("target_species")
        or intelligence.get("target_species")
        or best_bet.get("species")
    )
    zip_code = _text(meta.get("zip") or payload.get("zip") or intelligence.get("zip"))

    if intelligence:
        conn.execute(
            """
            INSERT INTO intelligence_snapshots(
              id, trip_id, report_id, zip, target_species, source_path,
              source_hash, summary_json, legacy_payload_json, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              trip_id=excluded.trip_id, report_id=excluded.report_id, zip=excluded.zip,
              target_species=excluded.target_species, source_path=excluded.source_path,
              source_hash=excluded.source_hash, summary_json=excluded.summary_json,
              legacy_payload_json=excluded.legacy_payload_json
            """,
            (
                snapshot_id,
                trip_id or None,
                report_id,
                zip_code,
                target_species,
                f"sqlite:trip_reports/{report_id}",
                record_hash(intelligence),
                canonical_dumps(intelligence.get("summary") or intelligence),
                canonical_dumps(intelligence),
                created_at,
            ),
        )

    if best_bet:
        reasons = best_bet.get("reasons") if isinstance(best_bet.get("reasons"), list) else []
        caution = best_bet.get("caution") if isinstance(best_bet.get("caution"), list) else []
        conn.execute(
            """
            INSERT INTO recommendations(
              id, intelligence_snapshot_id, target_species, lure_type, lure_label,
              fit_label, score, confidence, reasons_json, caution_json,
              legacy_payload_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              intelligence_snapshot_id=excluded.intelligence_snapshot_id,
              target_species=excluded.target_species, lure_type=excluded.lure_type,
              lure_label=excluded.lure_label, fit_label=excluded.fit_label,
              score=excluded.score, confidence=excluded.confidence,
              reasons_json=excluded.reasons_json, caution_json=excluded.caution_json,
              legacy_payload_json=excluded.legacy_payload_json, updated_at=excluded.updated_at
            """,
            (
                recommendation_id,
                snapshot_id if intelligence else None,
                _text(best_bet.get("species") or target_species),
                _text(best_bet.get("lure_type")),
                _text(best_bet.get("lure_name") or best_bet.get("lure")),
                _text(best_bet.get("fit_label")),
                best_bet.get("species_score") if best_bet.get("species_score") is not None else best_bet.get("score"),
                _text(best_bet.get("confidence")),
                canonical_dumps(reasons),
                canonical_dumps(caution),
                canonical_dumps(best_bet),
                created_at,
                _now(),
            ),
        )
        conn.execute("DELETE FROM recommendation_explanations WHERE recommendation_id=?", (recommendation_id,))
        for reason in reasons:
            if _text(reason):
                conn.execute(
                    "INSERT INTO recommendation_explanations(recommendation_id, explanation_type, body, source_path) VALUES(?, ?, ?, ?)",
                    (recommendation_id, "reason", _text(reason), f"sqlite:trip_reports/{report_id}"),
                )
        for item in caution:
            if _text(item):
                conn.execute(
                    "INSERT INTO recommendation_explanations(recommendation_id, explanation_type, body, source_path) VALUES(?, ?, ?, ?)",
                    (recommendation_id, "caution", _text(item), f"sqlite:trip_reports/{report_id}"),
                )
    return {
        "report_id": report_id,
        "snapshot_id": snapshot_id if intelligence else None,
        "recommendation_id": recommendation_id if best_bet else None,
    }


def reconcile_authoritative_report_recommendations(db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    """Derive durable history from active SQLite report snapshots without JSON reads."""
    reconciled: list[str] = []
    errors: list[str] = []
    with connect(db_path) as conn:
        with conn:
            rows = conn.execute(
                "SELECT id, trip_id, legacy_payload_json, snapshot_payload_json FROM trip_reports WHERE status='active' ORDER BY id"
            ).fetchall()
            for row in rows:
                report_id = str(row["id"])
                try:
                    raw_snapshot = json.loads(row["snapshot_payload_json"] or "{}")
                    raw_meta = json.loads(row["legacy_payload_json"] or "{}")
                    if not isinstance(raw_snapshot, dict):
                        raise ValueError("report snapshot is not an object")
                    wrapped = _wrapped_snapshot(raw_snapshot, raw_meta)
                    if not wrapped["payload"]:
                        raise ValueError("report snapshot payload is missing")
                    persist_report_recommendation_history(
                        conn,
                        report_id=report_id,
                        trip_id=_text(row["trip_id"]),
                        meta=_as_dict(raw_meta),
                        wrapped_snapshot=wrapped,
                    )
                    reconciled.append(report_id)
                except Exception as exc:
                    errors.append(f"{report_id}: {exc}")
            conn.execute(
                """INSERT INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
                (RECONCILIATION_STATUS_KEY, canonical_dumps({"reports": reconciled, "errors": errors, "at": _now()}), _now()),
            )
    return {"reconciled": reconciled, "errors": errors, "ok": not errors}


def recommendation_transition_preflight(db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    with connect(db_path, read_only=True) as conn:
        authority = conn.execute("SELECT authority FROM data_authority WHERE domain='recommendations'").fetchone()
        reports = conn.execute("SELECT id, snapshot_payload_json FROM trip_reports WHERE status='active' ORDER BY id").fetchall()
        snapshot_count = conn.execute("SELECT count(*) FROM intelligence_snapshots").fetchone()[0]
        recommendation_count = conn.execute("SELECT count(*) FROM recommendations").fetchone()[0]
    missing = [str(row["id"]) for row in reports if not row["snapshot_payload_json"]]
    return {
        "authority": str(authority["authority"]) if authority else "missing",
        "active_report_count": len(reports),
        "missing_snapshot_ids": missing,
        "intelligence_snapshot_count": int(snapshot_count),
        "recommendation_count": int(recommendation_count),
        "ready": not missing,
    }


def activate_recommendations_authority(db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    """Activate only persisted recommendation/intelligence history authority."""
    preflight = recommendation_transition_preflight(db_path)
    if preflight["authority"] != "json":
        raise ValueError(f"Recommendations must be JSON-authoritative before transition, found {preflight['authority']!r}")
    if not preflight["ready"]:
        raise ValueError(f"Recommendation transition preflight failed: {preflight}")
    reconciled = reconcile_authoritative_report_recommendations(db_path)
    if not reconciled["ok"]:
        raise RuntimeError(f"Recommendation reconciliation failed: {reconciled['errors']}")
    with connect(db_path) as conn:
        with conn:
            conn.execute(
                "UPDATE data_authority SET authority='sqlite', note=?, updated_at=? WHERE domain='recommendations'",
                ("SQLite is authoritative for persisted intelligence snapshots, recommendations, explanations, and feedback. Live Smart Intelligence remains application-computed.", _now()),
            )
    return {"preflight": preflight, "reconciled": reconciled, "authority": "sqlite"}


def list_authoritative_recommendation_history(db_path: str | Path = DEFAULT_DB) -> list[dict[str, Any]]:
    with connect(db_path, read_only=True) as conn:
        rows = conn.execute(
            """SELECT r.id, r.intelligence_snapshot_id, r.target_species, r.lure_type,
                      r.lure_label, r.fit_label, r.score, r.confidence,
                      r.reasons_json, r.caution_json, r.legacy_payload_json,
                      r.created_at, r.updated_at, s.report_id
                 FROM recommendations r
                 LEFT JOIN intelligence_snapshots s ON s.id=r.intelligence_snapshot_id
                 ORDER BY r.created_at DESC, r.id DESC"""
        ).fetchall()
    history: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["legacy_payload_json"] or "{}")
        except Exception:
            payload = {}
        history.append({
            "id": str(row["id"]),
            "report_id": _text(row["report_id"]),
            "snapshot_id": _text(row["intelligence_snapshot_id"]),
            "target_species": _text(row["target_species"]),
            "lure_type": _text(row["lure_type"]),
            "lure_label": _text(row["lure_label"]),
            "fit_label": _text(row["fit_label"]),
            "score": row["score"],
            "confidence": _text(row["confidence"]),
            "reasons": json.loads(row["reasons_json"] or "[]"),
            "caution": json.loads(row["caution_json"] or "[]"),
            "payload": payload if isinstance(payload, dict) else {},
            "created_at": _text(row["created_at"]),
            "updated_at": _text(row["updated_at"]),
        })
    return history


def record_recommendation_feedback(
    recommendation_id: str,
    *,
    feedback_type: str,
    rating: int | None = None,
    notes: str = "",
    db_path: str | Path = DEFAULT_DB,
) -> dict[str, Any]:
    recommendation_id = _text(recommendation_id)
    feedback_type = _text(feedback_type).lower().replace(" ", "_")
    if not recommendation_id or len(recommendation_id) > 160:
        raise ValueError("A valid recommendation id is required")
    if not feedback_type or len(feedback_type) > 80:
        raise ValueError("A valid feedback type is required")
    if rating is not None and (not isinstance(rating, int) or rating < 1 or rating > 5):
        raise ValueError("Rating must be an integer from 1 to 5")
    notes = _text(notes)
    if len(notes) > 2000:
        raise ValueError("Feedback notes are too long")
    with connect(db_path) as conn:
        with conn:
            if not _recommendations_authoritative(conn):
                raise RuntimeError("Recommendation feedback is unavailable until SQLite recommendation authority is active")
            if conn.execute("SELECT 1 FROM recommendations WHERE id=?", (recommendation_id,)).fetchone() is None:
                raise LookupError("Recommendation not found")
            cursor = conn.execute(
                "INSERT INTO recommendation_feedback(recommendation_id, feedback_type, rating, notes, created_at) VALUES(?, ?, ?, ?, ?)",
                (recommendation_id, feedback_type, rating, notes or None, _now()),
            )
            result = {"id": int(cursor.lastrowid), "recommendation_id": recommendation_id, "feedback_type": feedback_type, "rating": rating, "notes": notes}
            conn.execute(
                """INSERT INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
                (FEEDBACK_STATUS_KEY, canonical_dumps({**result, "at": _now()}), _now()),
            )
    return result
