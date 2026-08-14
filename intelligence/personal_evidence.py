"""Bounded, explainable personal evidence queries for V7.7.

These calculations are deliberately observational.  They never alter a live
recommendation score; callers receive both the raw evidence and a conservative
shrunk estimate so the UI can make that distinction explicit.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from persistence.connection import DEFAULT_DB, connect

MAX_ROWS = 5000
LEVELS = (
    ("species+waterbody+season+lure", ("species", "waterbody", "season", "lure_family")),
    ("species+waterbody+season", ("species", "waterbody", "season")),
    ("species+waterbody", ("species", "waterbody")),
    ("species+season", ("species", "season")),
    ("species", ("species",)),
    ("global_personal_baseline", ()),
)


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm(value: object) -> str:
    return " ".join(_text(value).casefold().split())


def _season(value: object) -> str:
    try:
        month = datetime.fromisoformat(_text(value).replace("Z", "+00:00")).month
    except ValueError:
        return "unknown"
    return "winter" if month in (12, 1, 2) else "spring" if month in (3, 4, 5) else "summer" if month in (6, 7, 8) else "fall"


def _quality(count: int) -> str:
    return "none" if count < 3 else "exploratory" if count < 8 else "useful" if count < 15 else "strong"


def _rows(db_path: str | Path) -> list[dict[str, Any]]:
    with connect(db_path, read_only=True) as conn:
        result = [dict(row) for row in conn.execute(
            """SELECT o.id, o.trip_occurred, o.catch_count, o.completed_at, o.actual_waterbody,
                      o.actual_target_species, o.outcome, a.adherence,
                      r.target_species AS recommendation_species, r.lure_type, r.lure_label, r.score
                 FROM trip_outcomes o
                 JOIN recommendation_adherence a ON a.trip_outcome_id=o.id
                 JOIN recommendations r ON r.id=a.recommendation_id
                 WHERE o.trip_occurred=1 AND a.adherence IN ('exact', 'partial')
                 ORDER BY o.completed_at DESC, o.id DESC LIMIT ?""",
            (MAX_ROWS,),
        )]
    for row in result:
        row["species"] = _norm(row.get("actual_target_species") or row.get("recommendation_species"))
        row["waterbody"] = _norm(row.get("actual_waterbody"))
        row["season"] = _season(row.get("completed_at"))
        row["lure_family"] = _norm(row.get("lure_type"))
        row["success"] = int(row.get("catch_count") or 0) > 0
    return result


def _matches(row: dict[str, Any], context: dict[str, str], keys: tuple[str, ...]) -> bool:
    return all(context.get(key) and row.get(key) == context[key] for key in keys)


def _estimate(rows: list[dict[str, Any]], prior_rows: list[dict[str, Any]]) -> dict[str, Any]:
    trips = len(rows)
    successes = sum(1 for row in rows if row["success"])
    raw = successes / trips if trips else None
    # A modest broader-context prior prevents small perfect samples from reading as certainty.
    base_trials = len(prior_rows)
    base_successes = sum(1 for row in prior_rows if row["success"])
    prior_rate = (base_successes / base_trials) if base_trials else 0.5
    alpha, beta = 2 + prior_rate * 4, 2 + (1 - prior_rate) * 4
    adjusted = (successes + alpha) / (trips + alpha + beta) if trips else prior_rate
    return {
        "comparable_trips": trips,
        "successes": successes,
        "no_catch": trips - successes,
        "raw_success_rate": round(raw, 3) if raw is not None else None,
        "adjusted_success_rate": round(adjusted, 3),
        "quality": _quality(trips),
        "prior_source": "broader personal baseline" if base_trials else "neutral conservative prior",
    }


def build_contextual_personal_evidence(
    db_path: str | Path = DEFAULT_DB, *, species: object = None, waterbody: object = None,
    season: object = None, lure_family: object = None,
) -> dict[str, Any]:
    """Return the strongest non-empty contextual evidence level, shadow-only."""
    rows = _rows(db_path)
    context = {
        "species": _norm(species), "waterbody": _norm(waterbody),
        "season": _norm(season), "lure_family": _norm(lure_family),
    }
    selected_name, selected_keys, selected_rows = LEVELS[-1][0], LEVELS[-1][1], rows
    for name, keys in LEVELS[:-1]:
        if not all(context.get(key) for key in keys):
            continue
        matches = [row for row in rows if _matches(row, context, keys)]
        if matches:
            selected_name, selected_keys, selected_rows = name, keys, matches
            break
    broader = rows if selected_keys else []
    estimate = _estimate(selected_rows, broader)
    return {
        "ok": True, "source": "sqlite", "live_applied": False,
        "context": {key: value for key, value in context.items() if value},
        "match_level": selected_name, "comparable_trip_definition": (
            "Fished trips with a persisted recommendation and direct adherence recorded as exact or partial."
        ),
        "excluded_outcomes": "Did-not-fish, changed-plan, missing completion, and unlinked recommendation records are excluded.",
        **estimate,
    }


def build_forecast_calibration(db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    """Summarize followed-trip outcomes by the saved recommendation score band."""
    rows = _rows(db_path)
    bands = ((0, 39), (40, 59), (60, 69), (70, 79), (80, 89), (90, 100))
    result = []
    for low, high in bands:
        matched = [row for row in rows if row.get("score") is not None and low <= float(row["score"]) <= high]
        successes = sum(1 for row in matched if row["success"])
        count = len(matched)
        proxy = ((low + high) / 2) / 100
        observed = successes / count if count else None
        result.append({
            "band": f"{low}-{high}", "followed_trips": count, "catch_positive_trips": successes,
            "no_catch_trips": count - successes, "observed_success_rate": round(observed, 3) if observed is not None else None,
            "mean_catch_count": round(sum(int(row.get("catch_count") or 0) for row in matched) / count, 2) if count else None,
            "score_calibration_indicator": round(observed - proxy, 3) if observed is not None else None,
            "sample_quality": _quality(count),
        })
    return {"ok": True, "source": "sqlite", "live_ranking_changed": False, "buckets": result,
            "note": "This compares score bands with outcomes; the fishing score is not a probability."}


def contextual_shadow_adjustment(evidence: dict[str, Any]) -> dict[str, Any]:
    """Translate shrunk contextual evidence into a capped display-only adjustment."""
    count = int(evidence.get("comparable_trips") or 0)
    adjusted = evidence.get("adjusted_success_rate")
    if count < 3 or adjusted is None:
        adjustment = 0
    else:
        adjustment = max(-5, min(5, round((float(adjusted) - 0.5) * 10)))
    return {**evidence, "proposed_adjustment": adjustment, "maximum_allowed_adjustment": 5,
            "live_applied": False, "note": "Contextual personal evidence is shadow-only and is not applied to live ranking."}
