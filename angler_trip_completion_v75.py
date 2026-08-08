"""V7.5.0 API routes for deliberate trip completion records."""
from __future__ import annotations

import os
from pathlib import Path

from flask import jsonify, request

from persistence.authority_resolution import AuthorityWriteError, require_write_authority, resolve_authority
from persistence.connection import DEFAULT_DB
from persistence.recommendations_authority import load_recommendation_adherence
from persistence.trip_completion import TripCompletionError, load_trip_completion, record_trip_completion


def _db_path() -> Path:
    return Path(os.environ.get("AI_SQLITE_DB_PATH", str(DEFAULT_DB)))


def register_trip_completion_routes_v75(app):
    @app.route("/api/trips/completion")
    def get_trip_completion():
        report_id = str(request.args.get("report_id") or "").strip()
        if not report_id:
            return jsonify({"ok": False, "error": "report_id is required"}), 400
        resolution = resolve_authority("reports", _db_path())
        if resolution.effective_authority != "sqlite":
            return jsonify({"ok": False, "error": "Trip completion is unavailable until reports SQLite authority is healthy.", "authority": resolution.effective_authority}), 503
        adherence = None
        recommendation_resolution = resolve_authority("recommendations", _db_path())
        if recommendation_resolution.effective_authority == "sqlite":
            adherence = load_recommendation_adherence(report_id, _db_path()) or {
                "status": "not_linked",
                "reason": "This legacy report has no stored Best Bet to link.",
            }
        else:
            adherence = {
                "status": "unavailable",
                "reason": "Recommendation feedback was not loaded because its authority markers need attention.",
                "authority": recommendation_resolution.effective_authority,
            }
        return jsonify({"ok": True, "completion": load_trip_completion(report_id, _db_path()), "recommendation_adherence": adherence})

    @app.route("/api/trips/completion", methods=["POST"])
    def save_trip_completion():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Trip completion JSON is required"}), 400
        try:
            require_write_authority("reports", _db_path())
            completion = record_trip_completion(payload, _db_path())
        except AuthorityWriteError as exc:
            return jsonify({"ok": False, "error": str(exc), "authority": exc.resolution.effective_authority}), exc.http_status
        except TripCompletionError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify(completion)
