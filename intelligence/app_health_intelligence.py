from __future__ import annotations

from typing import Any

try:
    from intelligence.smart_intelligence import TRANSITION_DIRECTION, build_smart_intelligence
except Exception:
    TRANSITION_DIRECTION = {}
    build_smart_intelligence = None


def get_smart_intelligence_health_for_app() -> dict[str, Any]:
    """
    Read-only App Health readiness summary for Smart Intelligence.

    v4.6.1 keeps the current layer transitional while documenting the updated
    direction: map-driven dashboard and deliberate SQLite authority migration
    only after backup/export/rollback tools are ready.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if build_smart_intelligence is None:
        return {
            "ok": False,
            "summary": "Smart Intelligence helper unavailable",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation",
            "transition_direction": TRANSITION_DIRECTION,
            "warnings": warnings,
            "errors": ["Smart Intelligence module could not be imported."],
        }

    try:
        sample = build_smart_intelligence(
            zip_code="60543",
            location={"city": "Oswego", "state": "Illinois"},
            weather={"source": "sample"},
            area_type="lake",
            best_bet={
                "species": "Largemouth Bass",
                "species_score": 82,
                "lure_name": "White/chartreuse spinnerbait",
                "why": "sample health check",
            },
            best_time={"label": "Evening"},
            catch_insights={"total": 0, "local_total": 0, "top_species": []},
        )
    except Exception as exc:
        return {
            "ok": False,
            "summary": "Smart Intelligence health check failed",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation",
            "transition_direction": TRANSITION_DIRECTION,
            "warnings": warnings,
            "errors": [str(exc)],
        }

    input_quality = sample.get("input_quality", {})
    if input_quality.get("missing"):
        warnings.append("Sample check confirms missing weather inputs are handled without crashing.")

    if not sample.get("transition_direction", {}).get("map_dashboard_planned"):
        errors.append("Map dashboard direction is not declared.")

    if not sample.get("transition_direction", {}).get("sqlite_authority_allowed_after_migration"):
        errors.append("SQLite authority transition direction is not declared.")

    return {
        "ok": not errors,
        "summary": "Smart Intelligence hardened and transitional",
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
        "version": sample.get("hardened_version"),
        "input_quality": input_quality,
        "transition_direction": sample.get("transition_direction", TRANSITION_DIRECTION),
        "warnings": warnings,
        "errors": errors,
    }
