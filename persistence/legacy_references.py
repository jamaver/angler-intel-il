"""Reviewed mappings for historical catch references that cannot be inferred."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .canonical_json import record_hash

RELATIONSHIPS = {"gear", "waterbody"}
DECISIONS = {"accepted_legacy", "linked"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def catch_payload_hash(conn: sqlite3.Connection, catch_id: str) -> str:
    row = conn.execute("SELECT legacy_payload_json FROM catches WHERE id = ?", (catch_id,)).fetchone()
    if not row:
        raise ValueError(f"Catch not found: {catch_id}")
    try:
        payload = json.loads(row["legacy_payload_json"] or "{}")
    except Exception as exc:
        raise ValueError(f"Catch {catch_id} has an invalid stored legacy payload: {exc}") from exc
    return record_hash(payload)


def record_decision(
    conn: sqlite3.Connection,
    *,
    catch_id: str,
    relationship: str,
    role: str = "",
    original_reference: str,
    decision: str,
    target_id: str | None = None,
    note: str,
    operator_name: str,
) -> dict[str, str]:
    relationship = _text(relationship).lower()
    role = _text(role).lower()
    original_reference = _text(original_reference)
    decision = _text(decision).lower()
    target_id = _text(target_id) or None
    note = _text(note)
    operator_name = _text(operator_name)
    if relationship not in RELATIONSHIPS:
        raise ValueError(f"Unsupported relationship: {relationship}")
    if not original_reference or not note or not operator_name:
        raise ValueError("original reference, note, and operator are required")
    if relationship == "gear" and not role:
        raise ValueError("gear decisions require a role")
    if relationship == "waterbody" and role:
        raise ValueError("waterbody decisions cannot include a role")
    if decision not in DECISIONS:
        raise ValueError(f"Unsupported decision: {decision}")
    if decision == "linked" and not target_id:
        raise ValueError("linked decisions require a target ID")
    if decision == "accepted_legacy" and target_id:
        raise ValueError("accepted legacy decisions cannot have a target ID")
    if decision == "linked":
        table = "gear_items" if relationship == "gear" else "waterbodies"
        if not conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (target_id,)).fetchone():
            raise ValueError(f"Target {relationship} not found: {target_id}")

    payload_hash = catch_payload_hash(conn, catch_id)
    now = utc_now()
    with conn:
        conn.execute(
            """
            INSERT INTO legacy_reference_decisions(
                catch_id, relationship, role, original_reference, catch_payload_hash,
                decision, target_id, note, operator_name, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(catch_id, relationship, role, original_reference) DO UPDATE SET
                catch_payload_hash=excluded.catch_payload_hash, decision=excluded.decision,
                target_id=excluded.target_id, note=excluded.note,
                operator_name=excluded.operator_name, updated_at=excluded.updated_at
            """,
            (catch_id, relationship, role, original_reference, payload_hash, decision, target_id, note, operator_name, now, now),
        )
    return {"catch_id": catch_id, "relationship": relationship, "role": role, "original_reference": original_reference, "decision": decision, "target_id": target_id or ""}


def reviewed_decision(
    conn: sqlite3.Connection,
    *,
    catch_id: str,
    relationship: str,
    role: str = "",
    original_reference: str,
    payload_hash: str,
) -> dict[str, Any] | None:
    try:
        row = conn.execute(
            """
            SELECT decision, target_id, note, operator_name, updated_at
            FROM legacy_reference_decisions
            WHERE catch_id = ? AND relationship = ? AND role = ?
              AND original_reference = ? AND catch_payload_hash = ?
            """,
            (catch_id, relationship, _text(role).lower(), _text(original_reference), payload_hash),
        ).fetchone()
    except sqlite3.OperationalError:
        # Validation remains usable against a pre-0009 inspection database.
        return None
    return dict(row) if row else None


def unresolved_references(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return reference rows that still need an explicit reviewed decision."""
    from .validation import _slug

    gear_ids = {row["id"] for row in conn.execute("SELECT id FROM gear_items")}
    water_ids = {row["id"] for row in conn.execute("SELECT id FROM waterbodies")}
    unresolved: list[dict[str, Any]] = []
    for row in conn.execute("SELECT id, waterbody, gear_refs_json, gear_labels_json, legacy_payload_json FROM catches ORDER BY timestamp DESC, id"):
        catch_id = row["id"]
        try:
            payload_hash = record_hash(json.loads(row["legacy_payload_json"] or "{}"))
            gear_refs = json.loads(row["gear_refs_json"] or "{}")
            gear_labels = json.loads(row["gear_labels_json"] or "{}")
        except Exception:
            continue
        if isinstance(gear_refs, dict):
            for role, reference in gear_refs.items():
                reference = _text(reference)
                if reference and reference not in gear_ids and not reviewed_decision(conn, catch_id=catch_id, relationship="gear", role=str(role), original_reference=reference, payload_hash=payload_hash):
                    unresolved.append({"catch_id": catch_id, "relationship": "gear", "role": _text(role), "reference": reference, "label": _text(gear_labels.get(role))})
        waterbody = _text(row["waterbody"])
        if waterbody and _slug(waterbody, "") not in water_ids and not reviewed_decision(conn, catch_id=catch_id, relationship="waterbody", original_reference=waterbody, payload_hash=payload_hash):
            unresolved.append({"catch_id": catch_id, "relationship": "waterbody", "role": "", "reference": waterbody, "label": waterbody})
    return unresolved


def decision_summary(conn: sqlite3.Connection) -> dict[str, int]:
    """Return decision counts, including reviews invalidated by catch edits."""
    summary = {"total": 0, "accepted_legacy": 0, "linked": 0, "current": 0, "stale": 0}
    try:
        rows = [dict(row) for row in conn.execute(
            "SELECT catch_id, catch_payload_hash, decision FROM legacy_reference_decisions"
        )]
    except sqlite3.OperationalError:
        return summary
    for row in rows:
        summary["total"] += 1
        decision = _text(row.get("decision"))
        if decision in summary:
            summary[decision] += 1
        try:
            current = catch_payload_hash(conn, _text(row.get("catch_id")))
        except ValueError:
            current = ""
        if current and current == _text(row.get("catch_payload_hash")):
            summary["current"] += 1
        else:
            summary["stale"] += 1
    return summary
