"""Read-only personal analytics API for the V7.4 query-layer foundation."""
from __future__ import annotations

import os
from pathlib import Path

from flask import jsonify, request

from persistence.authority_resolution import resolve_authority
from persistence.connection import DEFAULT_DB
from persistence.personal_analytics import AnalyticsInputError, build_catch_water_analytics, build_personal_analytics


def _analytics_db_path() -> Path:
    return Path(os.environ.get("AI_SQLITE_DB_PATH", str(DEFAULT_DB)))


def _unavailable_response():
    resolution = resolve_authority("catches", _analytics_db_path())
    if resolution.effective_authority == "sqlite":
        return None
    status = 503 if resolution.effective_authority == "sqlite_unavailable" else 409
    return jsonify({
        "ok": False,
        "error": "Personal analytics are unavailable until the catches authority store is healthy.",
        "authority": resolution.effective_authority,
        "authority_status": resolution.status,
        "source": "unavailable",
    }), status


def register_analytics_routes_v74(app):
    @app.route("/api/analytics/status")
    def analytics_status():
        resolution = resolve_authority("catches", _analytics_db_path())
        return jsonify({
            "ok": resolution.effective_authority == "sqlite",
            "domain": "catches",
            "authority": resolution.effective_authority,
            "status": resolution.status,
            "source": "sqlite" if resolution.effective_authority == "sqlite" else "unavailable",
        })

    @app.route("/api/analytics/personal")
    def personal_analytics():
        unavailable = _unavailable_response()
        if unavailable is not None:
            return unavailable
        try:
            payload = build_personal_analytics(
                _analytics_db_path(),
                date_from=request.args.get("date_from"),
                date_to=request.args.get("date_to"),
                species=request.args.get("species"),
                waterbody=request.args.get("waterbody"),
                limit=request.args.get("limit", 5),
            )
        except AnalyticsInputError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": f"Personal analytics query failed: {type(exc).__name__}"}), 503
        return jsonify(payload)

    @app.route("/api/analytics/catch-water")
    def catch_water_analytics():
        unavailable = _unavailable_response()
        if unavailable is not None:
            return unavailable
        try:
            payload = build_catch_water_analytics(
                _analytics_db_path(),
                date_from=request.args.get("date_from"),
                date_to=request.args.get("date_to"),
                species=request.args.get("species"),
                waterbody=request.args.get("waterbody"),
                limit=request.args.get("limit", 5),
            )
        except AnalyticsInputError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": f"Catch and water analytics query failed: {type(exc).__name__}"}), 503
        return jsonify(payload)
