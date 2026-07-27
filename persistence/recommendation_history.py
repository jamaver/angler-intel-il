"""Read-only comparison of saved-report recommendation history in V7.2.6."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical_json import canonicalize, record_hash
from .connection import DEFAULT_DB, connect


def json_recommendation_history(reports_dir: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(Path(reports_dir).glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        report_id = str((payload.get("meta") or {}).get("id") or path.stem).strip()
        best_bet = (payload.get("summary") or {}).get("best_bet")
        if report_id and isinstance(best_bet, dict):
            records.append({"id": f"{report_id}-best-bet", "report_id": report_id, "payload": canonicalize(best_bet)})
    return records


def sqlite_recommendation_history(db_path: str | Path = DEFAULT_DB) -> list[dict[str, Any]]:
    with connect(db_path, read_only=True) as conn:
        rows = conn.execute("SELECT id, intelligence_snapshot_id, legacy_payload_json FROM recommendations ORDER BY created_at DESC, id").fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["legacy_payload_json"] or "{}")
        except Exception:
            payload = {}
        output.append({"id": str(row["id"]), "snapshot_id": row["intelligence_snapshot_id"], "payload": canonicalize(payload)})
    return output


def compare_recommendation_history(reports_dir: str | Path, db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    expected = {row["id"]: record_hash(row["payload"]) for row in json_recommendation_history(reports_dir)}
    actual = {row["id"]: record_hash(row["payload"]) for row in sqlite_recommendation_history(db_path)}
    differences: list[str] = []
    if set(expected) != set(actual):
        differences.append("recommendation_ids")
    for recommendation_id in sorted(set(expected).intersection(actual)):
        if expected[recommendation_id] != actual[recommendation_id]:
            differences.append(f"recommendation:{recommendation_id}")
    return {"status": "exact" if not differences else "changed", "differences": differences, "json_count": len(expected), "sqlite_count": len(actual)}
