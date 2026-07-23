from __future__ import annotations

import html
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from flask import jsonify, render_template, request, send_file
from persistence.reports_mirror import mirror_reports


BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
DATA_DIR = BASE_DIR / "data"
INDEX_PATH = DATA_DIR / "reports_index.json"


def _now() -> datetime:
    return datetime.now()


def _now_stamp() -> str:
    return _now().strftime("%Y%m%d-%H%M%S")


def _safe_slug(value: str, fallback: str = "report") -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or fallback


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _index() -> list[dict[str, Any]]:
    data = _read_json(INDEX_PATH, [])
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("reports"), list):
        return data["reports"]
    return []


def _save_index(items: list[dict[str, Any]]) -> None:
    items = sorted(items, key=lambda x: x.get("created", ""), reverse=True)
    _write_json(INDEX_PATH, items)
    # JSON report files/index remain authoritative; mirror errors are non-fatal.
    mirror_reports(INDEX_PATH, REPORTS_DIR)


def _delete_report_assets(report_id: str) -> dict[str, Any]:
    if "/" in report_id or "\\" in report_id or ".." in report_id:
        raise ValueError("Invalid report id")

    items = _index()
    match = None
    remaining = []

    for item in items:
        if item.get("id") == report_id:
            match = item
        else:
            remaining.append(item)

    if not match:
        raise FileNotFoundError("Report not found")

    deleted_files: list[str] = []
    for key in ("html_file", "json_file"):
        filename = str(match.get(key) or "").strip()
        if not filename:
            continue
        path = _safe_report_file(filename)
        if path is None:
            continue
        if path.exists():
            path.unlink()
            deleted_files.append(path.name)

    _save_index(remaining)

    return {
        "report": match,
        "deleted_files": deleted_files,
        "remaining_count": len(remaining),
    }


def _delete_all_report_assets() -> dict[str, Any]:
    """Delete saved report artifacts and reset the local report index.

    Report artifacts are limited to JSON and HTML files directly under the
    app-owned reports directory. No caller-supplied path is accepted.
    """
    items = _index()
    report_files: set[Path] = set()

    for item in items:
        if not isinstance(item, dict):
            continue
        for key in ("html_file", "json_file"):
            filename = str(item.get(key) or "").strip()
            path = _safe_report_file(filename)
            if path is not None:
                report_files.add(path)

    # Include orphaned app report artifacts so a bulk delete actually leaves
    # the reports store empty, while remaining constrained to this directory.
    if REPORTS_DIR.exists():
        for path in REPORTS_DIR.iterdir():
            if path.is_file() and path.suffix.lower() in {".json", ".html"}:
                report_files.add(path)

    deleted_files: list[str] = []
    for path in sorted(report_files, key=lambda item: item.name):
        path.unlink()
        deleted_files.append(path.name)

    _save_index([])
    return {
        "deleted_report_count": len(items),
        "deleted_files": deleted_files,
        "remaining_count": 0,
    }


def _first_present(data: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, "", [], {}):
            return data[key]
    return default


def _extract_summary(payload: dict[str, Any]) -> dict[str, Any]:
    intel = payload.get("intel") if isinstance(payload.get("intel"), dict) else payload

    zip_code = str(_first_present(payload, ["zip", "zipcode", "postal_code"], "") or "")
    if not zip_code:
        zip_code = str(_first_present(intel, ["zip", "zipcode", "postal_code"], "") or "")

    best_bet = _first_present(
        intel,
        ["best_bet", "bestBet", "best_bet_today", "bestBetToday", "recommendation"],
        {},
    )

    weather = _first_present(
        intel,
        ["weather", "conditions", "current_conditions", "currentConditions"],
        {},
    )

    species = _first_present(
        intel,
        ["species", "species_ranking", "speciesRanking", "rankings"],
        [],
    )

    lures = _first_present(
        intel,
        ["lures", "lure_cards", "lureCards", "recommended_lures", "recommendedLures"],
        [],
    )

    waters = _first_present(
        intel,
        ["nearby_waters", "nearbyWaters", "waters", "waterbodies"],
        [],
    )

    forecast = _first_present(
        intel,
        ["forecast", "daily_forecast", "seven_day", "sevenDayForecast", "days"],
        [],
    )

    return {
        "zip": zip_code,
        "best_bet": best_bet,
        "weather": weather,
        "species": species,
        "lures": lures,
        "waters": waters,
        "forecast": forecast,
    }


def _compact_text(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value or "").split()).strip()
    return text or fallback


def _short_text(value: Any, limit: int = 240) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _format_report_datetime(value: Any) -> str:
    if not value:
        return "Unknown time"
    if isinstance(value, datetime):
        return value.strftime("%b %d, %Y %I:%M %p")
    text = _compact_text(value)
    for fmt in ("%b %d, %Y %I:%M %p", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).strftime("%b %d, %Y %I:%M %p")
        except Exception:
            continue
    return text


def _fit_label(score: Any) -> str:
    try:
        value = float(score)
    except Exception:
        return "Exploratory fit"
    if value >= 80:
        return "Strong target fit"
    if value >= 65:
        return "Good target fit"
    if value >= 50:
        return "Moderate target fit"
    return "Exploratory fit"


def _lure_label(item: Any) -> str:
    if not isinstance(item, dict):
        return "Lure"
    asset = item.get("lure_asset") if isinstance(item.get("lure_asset"), dict) else {}
    if asset and asset.get("label"):
        return _compact_text(asset.get("label"), "Lure")
    return _compact_text(
        item.get("name") or item.get("lure_name") or item.get("label") or "Lure",
        "Lure",
    )


def _lure_image(item: Any) -> str:
    if not isinstance(item, dict):
        return "/static/lures/generic_lure.png"
    asset = item.get("lure_asset") if isinstance(item.get("lure_asset"), dict) else {}
    if asset and asset.get("path"):
        return asset.get("path")
    return item.get("image") or "/static/lures/generic_lure.png"


def _best_time_label(best_bet: dict[str, Any]) -> str:
    parts = [
        _compact_text(best_bet.get("time_label"), ""),
        _compact_text(best_bet.get("time_range"), ""),
    ]
    parts = [part for part in parts if part]
    return " · ".join(parts) or "Any time"


def _condition_rows(weather: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    if not isinstance(weather, dict):
        return rows
    rows.append({"label": "Temperature", "value": f"{weather.get('temp', '?')}°F"})
    rows.append({"label": "Wind", "value": f"{weather.get('wind', '?')} mph"})
    rows.append({"label": "Pressure", "value": f"{weather.get('pressure', '?')} inHg"})
    rows.append({"label": "Cloud Cover", "value": f"{weather.get('cloud', '?')}%"})
    source = _compact_text(weather.get("source"), "")
    if source:
        rows.append({"label": "Source", "value": source})
    return rows


def _best_bet_context(best_bet: dict[str, Any]) -> dict[str, Any]:
    best_bet = best_bet if isinstance(best_bet, dict) else {}
    return {
        "species": _compact_text(best_bet.get("species"), "Target Species"),
        "fish_image": best_bet.get("fish_image") or "/static/fish/generic_fish.png",
        "best_time": _best_time_label(best_bet),
        "best_hour": _compact_text(best_bet.get("best_hour"), ""),
        "lure_name": _lure_label(best_bet),
        "lure_image": _lure_image(best_bet),
        "speed": _compact_text(best_bet.get("speed"), ""),
        "size": _compact_text(best_bet.get("size"), ""),
        "why": _compact_text(best_bet.get("why"), ""),
        "fit_label": _fit_label(best_bet.get("species_score")),
        "reasons": [_compact_text(item, "") for item in best_bet.get("reasons", []) if _compact_text(item, "")],
    }


def _species_rows(species: Any, best_bet: dict[str, Any], best_time: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    best_name = _compact_text(best_bet.get("species"), "").lower()
    preferred_window = "evening"
    if isinstance(best_time, dict):
        label = _compact_text(best_time.get("label"), "").lower()
        if "morning" in label:
            preferred_window = "morning"
        elif "midday" in label:
            preferred_window = "midday"

    for item in species or []:
        if not isinstance(item, dict):
            continue
        lures = item.get("lures") if isinstance(item.get("lures"), dict) else {}
        cards = lures.get("cards") if isinstance(lures.get("cards"), dict) else {}
        lure_card = {}
        if isinstance(cards, dict):
            for key in (preferred_window, "evening", "morning", "midday"):
                candidate = cards.get(key)
                if isinstance(candidate, dict):
                    lure_card = candidate
                    break

        rows.append({
            "name": _compact_text(item.get("name"), "Species"),
            "fish_image": item.get("fish_image") or "/static/fish/generic_fish.png",
            "rating": _compact_text(item.get("rating"), ""),
            "habitat": _compact_text(item.get("habitat"), "Mixed habitat"),
            "lure_label": _lure_label(lure_card) if lure_card else "",
            "lure_image": _lure_image(lure_card) if lure_card else "",
            "why": _compact_text(lure_card.get("why") if isinstance(lure_card, dict) else "", ""),
            "fit_label": _fit_label(item.get("score")),
            "target_fit": _fit_label(item.get("score")),
            "selected": _compact_text(item.get("name"), "").lower() == best_name,
        })
    return rows


def _lure_rows(lures: Any) -> list[dict[str, Any]]:
    rows = []
    for item in lures or []:
        if not isinstance(item, dict):
            continue
        rows.append({
            "species": _compact_text(item.get("species"), "Species"),
            "name": _lure_label(item),
            "image": _lure_image(item),
            "color": _compact_text(item.get("color"), ""),
            "speed": _compact_text(item.get("speed"), ""),
            "size": _compact_text(item.get("size"), ""),
            "why": _compact_text(item.get("why"), ""),
            "fit_label": _fit_label(item.get("species_score")),
            "top_pick": bool(item.get("top_pick")),
        })
    return rows


def _water_rows(waters: Any) -> list[dict[str, Any]]:
    rows = []
    for item in waters or []:
        if not isinstance(item, dict):
            continue
        rows.append({
            "name": _compact_text(item.get("name"), "Waterbody"),
            "count": item.get("count"),
            "type": _compact_text(item.get("type"), ""),
        })
    return rows


def _forecast_rows(forecast: Any) -> list[dict[str, Any]]:
    rows = []
    for item in forecast or []:
        if not isinstance(item, dict):
            continue
        date_text = _compact_text(item.get("date"), "")
        pretty_date = date_text
        if date_text:
            try:
                pretty_date = datetime.strptime(date_text, "%Y-%m-%d").strftime("%a, %b %d")
            except Exception:
                pretty_date = date_text
        rows.append({
            "date": date_text,
            "pretty_date": pretty_date,
            "rating": _compact_text(item.get("rating"), ""),
            "high": item.get("high"),
            "low": item.get("low"),
            "wind": item.get("wind"),
            "score": item.get("score"),
        })
    return rows


def _forecast_label(date_text: Any) -> str:
    value = _compact_text(date_text, "")
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%A, %B %d, %Y")
    except Exception:
        return value


def _default_report_title(zip_code: Any, payload: dict[str, Any], summary: dict[str, Any], selected_forecast_label: Any = "") -> str:
    intel = payload.get("intel") if isinstance(payload.get("intel"), dict) else {}
    best_bet = summary.get("best_bet") if isinstance(summary.get("best_bet"), dict) else {}
    best_bet_ctx = _best_bet_context(best_bet)

    species = _compact_text(
        _first_present(
            intel,
            ["target_species", "targetSpecies", "species", "species_name"],
            "",
        )
        or best_bet_ctx.get("species")
        or payload.get("target_species"),
        "",
    )
    zip_text = _compact_text(zip_code, "")

    if species and zip_text:
        return f"{species} Plan — ZIP {zip_text}"
    if species:
        return f"{species} Plan"
    if zip_text:
        return f"Trip Plan — ZIP {zip_text}"
    if _compact_text(selected_forecast_label, ""):
        return "Trip Plan"
    return "Trip Plan"


def _report_overview(report_meta: dict[str, Any]) -> dict[str, Any]:
    overview = {
        "group": "General",
        "display_title": _compact_text(report_meta.get("title"), "Trip Plan"),
        "display_date": _compact_text(report_meta.get("selected_forecast_label"), ""),
        "zip": _compact_text(report_meta.get("zip"), ""),
        "target_species": "",
        "best_time": "Any time",
        "lure_name": "Lure",
        "lure_image": "/static/lures/generic_lure.png",
        "fish_image": "/static/fish/generic_fish.png",
        "fit_label": "Exploratory fit",
        "why": "",
        "summary": "",
        "rating": "",
        "score": None,
        "forecast_rating": "",
        "forecast_day_index": report_meta.get("forecast_day_index"),
    }

    json_file = _compact_text(report_meta.get("json_file"), "")
    if not json_file:
        return overview

    path = _safe_report_file(json_file)
    if path is None:
        return overview

    try:
        wrapped = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return overview

    payload = wrapped.get("payload") if isinstance(wrapped, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    summary = wrapped.get("summary") if isinstance(wrapped, dict) and isinstance(wrapped.get("summary"), dict) else _extract_summary(payload)

    selected_forecast_date = _compact_text(
        report_meta.get("selected_forecast_date")
        or payload.get("selected_forecast_date")
        or payload.get("forecast_date"),
        "",
    )
    if not selected_forecast_date and isinstance(summary.get("forecast"), list) and summary.get("forecast"):
        first_forecast = summary["forecast"][0]
        if isinstance(first_forecast, dict):
            selected_forecast_date = _compact_text(first_forecast.get("date"), "")

    context = _build_report_context(report_meta, payload, selected_forecast_date=selected_forecast_date)
    best_bet = context.get("best_bet") if isinstance(context.get("best_bet"), dict) else {}
    smart = context.get("smart_intelligence") if isinstance(context.get("smart_intelligence"), dict) else {}
    catch_insights = context.get("catch_insights") if isinstance(context.get("catch_insights"), dict) else {}

    target_species = _compact_text(
        best_bet.get("species")
        or context.get("target_species")
        or _first_present(payload.get("intel") if isinstance(payload.get("intel"), dict) else {}, ["target_species", "targetSpecies"], ""),
        "General",
    )
    if target_species.lower() in {"target species", "species", ""}:
        target_species = "General"

    group = target_species if target_species != "General" else "General"
    selected_label = _compact_text(
        report_meta.get("selected_forecast_label")
        or context.get("selected_forecast_label")
        or _format_report_datetime(report_meta.get("created")),
        "Trip Plan",
    )
    why = _compact_text(best_bet.get("why"), "")
    reasons = best_bet.get("reasons") if isinstance(best_bet.get("reasons"), list) else []
    if not why and reasons:
        why = _compact_text(reasons[0], "")

    overview.update({
        "group": group,
        "display_title": _compact_text(report_meta.get("title"), _default_report_title(overview["zip"], payload, summary, selected_label)),
        "display_date": selected_label,
        "target_species": target_species,
        "best_time": _compact_text(best_bet.get("best_time"), "Any time"),
        "best_time_range": _compact_text(best_bet.get("best_time_range"), ""),
        "lure_name": _compact_text(best_bet.get("lure_name"), "Lure"),
        "lure_image": _compact_text(best_bet.get("lure_image"), "/static/lures/generic_lure.png"),
        "fish_image": _compact_text(best_bet.get("fish_image"), "/static/fish/generic_fish.png"),
        "fit_label": _compact_text(best_bet.get("fit_label"), "Exploratory fit"),
        "why": why,
        "summary": _compact_text(smart.get("summary"), ""),
        "rating": _compact_text(context.get("overall_rating"), ""),
        "score": context.get("overall_score"),
        "forecast_rating": _compact_text(context.get("forecast_focus", {}).get("rating"), ""),
        "learning_summary": _compact_text(catch_insights.get("headline") or catch_insights.get("summary"), ""),
        "learning_takeaway": _compact_text(catch_insights.get("takeaway") or catch_insights.get("weight"), ""),
        "catch_quality": _compact_text(catch_insights.get("sample_quality"), ""),
    })
    return overview


def _selected_forecast_context(forecast_rows: list[dict[str, Any]], selected_date: Any = None, fallback_date: Any = None) -> dict[str, Any]:
    rows = [row for row in forecast_rows if isinstance(row, dict)]
    selected_date_text = _compact_text(selected_date, "")
    selected_row = None
    selected_index = None

    if selected_date_text:
        for idx, row in enumerate(rows):
            if _compact_text(row.get("date"), "") == selected_date_text:
                selected_row = row
                selected_index = idx
                break

    if selected_row is None and rows:
        selected_index = 0
        selected_row = rows[0]
        selected_date_text = _compact_text(selected_row.get("date"), selected_date_text)

    if not selected_date_text:
        selected_date_text = _compact_text(fallback_date, "")

    label = _forecast_label(selected_date_text) or _compact_text(fallback_date, "")
    if not label and selected_row:
        label = _compact_text(selected_row.get("pretty_date"), "") or _compact_text(selected_row.get("date"), "")

    focus = {
        "date": _compact_text(selected_row.get("date"), selected_date_text) if selected_row else selected_date_text,
        "pretty_date": _compact_text(selected_row.get("pretty_date"), label) if selected_row else label,
        "rating": _compact_text(selected_row.get("rating"), "") if selected_row else "",
        "high": selected_row.get("high") if selected_row else None,
        "low": selected_row.get("low") if selected_row else None,
        "wind": selected_row.get("wind") if selected_row else None,
        "score": selected_row.get("score") if selected_row else None,
    }

    return {
        "selected_forecast_date": selected_date_text,
        "selected_forecast_label": label,
        "forecast_day_index": selected_index if selected_index is not None else "",
        "forecast_focus": focus,
        "forecast_rows": rows,
    }


def _render_condition_cards(rows: list[dict[str, str]]) -> str:
    return "".join(
        f'<div class="report-condition"><strong>{html.escape(item["label"])}</strong><div>{html.escape(str(item["value"]))}</div></div>'
        for item in rows
    )


def _render_species_cards(rows: list[dict[str, Any]]) -> str:
    blocks = []
    for item in rows:
        reasons_html = f'<p class="report-muted">{html.escape(item["why"])}</p>' if item.get("why") else ""
        rating_html = f'<p class="report-muted">Rating: {html.escape(item["rating"])}</p>' if item.get("rating") else ""
        lure_html = f'<p class="report-muted"><b>Recommended:</b> {html.escape(item["lure_label"])}</p>' if item.get("lure_label") else ""
        fit_html = f'<span class="report-score-pill">{html.escape(item["fit_label"])}</span>' if item.get("fit_label") else ""
        lure_art = f'<img class="lure-art lure-art-sm report-lure-art" src="{html.escape(item["lure_image"])}" alt="{html.escape(item["lure_label"])}">' if item.get("lure_image") else ""
        blocks.append(
            f'''<article class="report-species-row">
          <div class="report-media">
            <img class="species-icon species-icon-md report-fish-art" src="{html.escape(item["fish_image"])}" alt="{html.escape(item["name"])}">
            <div>
              <div class="report-row-head">
                <h3>{html.escape(item["name"])}</h3>
                {fit_html}
              </div>
              {rating_html}
              <p class="report-muted">Habitat: {html.escape(item["habitat"])}</p>
              {lure_html}
              {reasons_html}
            </div>
          </div>
          {lure_art}
        </article>'''
        )
    return "".join(blocks)


def _render_lure_cards(rows: list[dict[str, Any]]) -> str:
    blocks = []
    for item in rows:
        top_pick_html = '<span class="report-score-pill">Top pick</span>' if item.get("top_pick") else ""
        color_part = f' · {html.escape(item["color"])}' if item.get("color") else ""
        size_part = f' · {html.escape(item["size"])}' if item.get("size") else ""
        why_html = f'<p class="report-muted">{html.escape(item["why"])}</p>' if item.get("why") else ""
        blocks.append(
            f'''<article class="report-lure-row">
          <div class="report-media">
            <img class="lure-art lure-art-md report-lure-art" src="{html.escape(item["image"])}" alt="{html.escape(item["name"])}">
            <div>
              <div class="report-row-head">
                <h3>{html.escape(item["name"])}</h3>
                {top_pick_html}
              </div>
              <p class="report-muted">For {html.escape(item["species"])}{color_part}</p>
              <p class="report-muted">{html.escape(item["speed"])}{size_part}</p>
              {why_html}
            </div>
          </div>
        </article>'''
        )
    return "".join(blocks)


def _render_water_cards(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<p class="report-empty">No nearby waters saved for this report.</p>'
    blocks = []
    for item in rows:
        count_html = f'<span class="report-score-pill">{html.escape(str(item["count"]))}</span>' if item.get("count") is not None else ""
        type_html = f'<p class="report-muted">{html.escape(item["type"])}</p>' if item.get("type") else ""
        blocks.append(
            f'''<article class="report-water-row">
          <div class="report-row-head">
            <h3>{html.escape(item["name"])}</h3>
            {count_html}
          </div>
          {type_html}
        </article>'''
        )
    return f'<div class="report-species-grid">{"".join(blocks)}</div>'


def _render_forecast_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<p class="report-empty">No forecast data saved for this report.</p>'
    body = "".join(
        f'<tr><td>{html.escape(item["pretty_date"] or item["date"])}</td><td>{html.escape(item["rating"])}</td><td>{html.escape(str(item["high"]))}&deg; / {html.escape(str(item["low"]))}&deg;</td><td>{html.escape(str(item["wind"]))} mph</td><td>{html.escape(str(item["score"]))}</td></tr>'
        for item in rows
    )
    return f'''<table class="report-outlook-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Rating</th>
          <th>High / Low</th>
          <th>Wind</th>
          <th>Score</th>
        </tr>
      </thead>
      <tbody>
        {body}
      </tbody>
    </table>'''


def _build_report_context(report_meta: dict[str, Any], payload: dict[str, Any], selected_forecast_date: Any = None) -> dict[str, Any]:
    intel = payload.get("intel") if isinstance(payload.get("intel"), dict) else payload if isinstance(payload, dict) else {}
    location = intel.get("location") if isinstance(intel.get("location"), dict) else {}
    overall = intel.get("overall") if isinstance(intel.get("overall"), dict) else {}
    best_bet = intel.get("best_bet") if isinstance(intel.get("best_bet"), dict) else {}
    best_time = intel.get("best_time") if isinstance(intel.get("best_time"), dict) else {}
    weather = intel.get("weather") if isinstance(intel.get("weather"), dict) else {}
    smart = intel.get("smart_intelligence") if isinstance(intel.get("smart_intelligence"), dict) else {}
    catch_insights = intel.get("catch_insights") if isinstance(intel.get("catch_insights"), dict) else {}

    best_bet_ctx = _best_bet_context(best_bet)
    condition_rows = _condition_rows(weather)
    species_rows = _species_rows(intel.get("species") if isinstance(intel.get("species"), list) else [], best_bet, best_time)
    lure_rows = _lure_rows(intel.get("lure_cards") if isinstance(intel.get("lure_cards"), list) else [])
    water_rows = _water_rows(intel.get("waters") if isinstance(intel.get("waters"), list) else [])
    forecast_rows = _forecast_rows(intel.get("forecast") if isinstance(intel.get("forecast"), list) else [])
    forecast_selection = _selected_forecast_context(
        forecast_rows,
        selected_date=selected_forecast_date or payload.get("selected_forecast_date") or report_meta.get("selected_forecast_date"),
        fallback_date=report_meta.get("created") or payload.get("saved_at") or payload.get("created"),
    )
    selected_forecast_date_text = forecast_selection["selected_forecast_date"]
    selected_forecast_label = forecast_selection["selected_forecast_label"]
    forecast_focus = forecast_selection["forecast_focus"]

    for row in forecast_rows:
        row["selected"] = _compact_text(row.get("date"), "") == selected_forecast_date_text if selected_forecast_date_text else False

    smart_clarity = smart.get("clarity_signal") if isinstance(smart.get("clarity_signal"), dict) else {}
    smart_condition_labels = [_compact_text(item, "") for item in (smart.get("condition_labels") or []) if _compact_text(item, "")]
    smart_positive = [_compact_text(item, "") for item in (smart.get("positive_signals") or []) if _compact_text(item, "")]
    smart_caution = [_compact_text(item, "") for item in (smart.get("caution_signals") or []) if _compact_text(item, "")]
    smart_strategy = [_compact_text(item, "") for item in (smart.get("strategy") or []) if _compact_text(item, "")]

    location_label = _compact_text(
        ", ".join(part for part in [location.get("city"), location.get("state")] if part),
        _compact_text(location.get("zip") or report_meta.get("zip"), "Unknown location"),
    )

    return {
        "title": report_meta.get("title") or "Saved Fishing Report",
        "subtitle": "Saved by Angler Intel",
        "generated_at": _format_report_datetime(report_meta.get("created") or payload.get("saved_at") or payload.get("created")),
        "location_label": location_label,
        "zip_code": _compact_text(report_meta.get("zip") or location.get("zip") or intel.get("zip"), ""),
        "target_species": _compact_text(intel.get("target_species") or payload.get("target_species"), "Auto"),
        "overall_score": overall.get("score"),
        "overall_rating": _compact_text(overall.get("rating"), ""),
        "selected_forecast_date": selected_forecast_date_text,
        "selected_forecast_label": selected_forecast_label,
        "forecast_focus": forecast_focus,
        "best_time": {
            "label": _compact_text(best_bet.get("time_label"), "Any time"),
            "range": _compact_text(best_bet.get("time_range"), "Any time"),
            "best_hour": _compact_text(best_bet.get("best_hour"), ""),
        },
        "best_bet": best_bet_ctx,
        "conditions": (
            [
                {"label": "Forecast date", "value": selected_forecast_label},
                {"label": "Forecast rating", "value": _compact_text(forecast_focus.get("rating"), _compact_text(overall.get("rating"), "Unknown"))},
                {"label": "High / Low", "value": f"{forecast_focus.get('high', '?')}° / {forecast_focus.get('low', '?')}°"},
                {"label": "Wind", "value": f"{forecast_focus.get('wind', '?')} mph"},
                {"label": "Score", "value": forecast_focus.get("score")},
                {"label": "Source", "value": "Open-Meteo forecast"},
            ]
            if forecast_rows
            else condition_rows
        ),
        "smart_intelligence": {
            "headline": _compact_text(smart.get("headline"), "Fishing pattern"),
            "summary": _compact_text(smart.get("summary"), ""),
            "condition_labels": smart_condition_labels,
            "clarity_label": _compact_text(smart_clarity.get("label"), "unknown"),
            "clarity_basis": _compact_text(smart_clarity.get("basis"), ""),
            "ranking_factors": [
                {
                    "label": _compact_text(item.get("label"), ""),
                    "value": _compact_text(item.get("value"), ""),
                    "why": _compact_text(item.get("why"), ""),
                }
                for item in (smart.get("ranking_factors") or [])
                if isinstance(item, dict) and (_compact_text(item.get("label"), "") or _compact_text(item.get("why"), ""))
            ],
            "explanation_sections": [
                {
                    "label": _compact_text(item.get("label"), ""),
                    "value": _compact_text(item.get("value"), ""),
                    "why": _compact_text(item.get("why"), ""),
                    "details": [_compact_text(detail, "") for detail in (item.get("details") or []) if _compact_text(detail, "")],
                }
                for item in (smart.get("explanation_sections") or [])
                if isinstance(item, dict) and (_compact_text(item.get("label"), "") or _compact_text(item.get("why"), ""))
            ],
            "decision_factors": [_compact_text(item, "") for item in smart.get("decision_factors", []) if _compact_text(item, "")],
            "positive_signals": smart_positive,
            "caution_signals": smart_caution,
            "strategy": smart_strategy,
        },
        "species_ranking": species_rows,
        "recommended_lures": lure_rows,
        "nearby_waters": water_rows,
        "forecast": forecast_rows,
        "catch_insights": catch_insights,
        "raw_json": json.dumps(payload, indent=2, ensure_ascii=False),
    }


def _render_report_html(report_meta: dict[str, Any], payload: dict[str, Any], selected_forecast_date: Any = None) -> str:
    return render_template("snapshot.html", report=_build_report_context(report_meta, payload, selected_forecast_date=selected_forecast_date))


def _save_report(payload: dict[str, Any], title: str | None = None, zip_code: str | None = None) -> dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    summary = _extract_summary(payload)

    zip_code = str(zip_code or summary.get("zip") or payload.get("zip") or "").strip()
    title = (title or payload.get("title") or "").strip()

    if not title:
        if zip_code:
            title = f"Trip Report ZIP {zip_code}"
        else:
            title = "Trip Report"

    report_id = f"{_now_stamp()}-{_safe_slug(title)}-{uuid.uuid4().hex[:6]}"
    json_name = f"{report_id}.json"
    html_name = f"{report_id}.html"

    created = _now().isoformat(timespec="seconds")
    selected_forecast_date = _compact_text(
        payload.get("selected_forecast_date") or payload.get("forecast_date"),
        "",
    )
    selected_forecast_label = _compact_text(payload.get("selected_forecast_label"), "")
    forecast_day_index = payload.get("forecast_day_index")

    meta = {
        "id": report_id,
        "title": title,
        "zip": zip_code,
        "created": created,
        "json_file": json_name,
        "html_file": html_name,
        "json_url": f"/api/reports/download/{json_name}",
        "html_url": f"/api/reports/download/{html_name}",
        "view_url": f"/api/reports/view/{report_id}",
    }
    if selected_forecast_date:
        meta["selected_forecast_date"] = selected_forecast_date
    if selected_forecast_label:
        meta["selected_forecast_label"] = selected_forecast_label
    if forecast_day_index not in (None, "", []):
        meta["forecast_day_index"] = forecast_day_index

    wrapped = {
        "meta": meta,
        "payload": payload,
        "summary": summary,
    }

    json_path = REPORTS_DIR / json_name
    html_path = REPORTS_DIR / html_name

    _write_json(json_path, wrapped)
    html_path.write_text(
        _render_report_html(meta, payload, selected_forecast_date=selected_forecast_date),
        encoding="utf-8",
    )

    items = _index()
    items = [x for x in items if x.get("id") != report_id]
    items.insert(0, meta)
    _save_index(items)

    return meta


def _safe_report_file(filename: str) -> Path | None:
    if not filename:
        return None
    if "/" in filename or "\\" in filename or ".." in filename:
        return None
    if not (filename.endswith(".json") or filename.endswith(".html")):
        return None

    path = REPORTS_DIR / filename
    if not path.exists() or not path.is_file():
        return None
    return path


def register_report_routes_v38(app):
    @app.route("/reports")
    def reports_page_v38():
        return render_template("reports.html")


    @app.route("/api/reports")
    def list_reports_v38():
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        items = _index()
        existing = []

        for item in items:
            json_file = item.get("json_file")
            html_file = item.get("html_file")
            if json_file and (REPORTS_DIR / json_file).exists():
                enriched = dict(item)
                enriched["overview"] = _report_overview(enriched)
                enriched["group"] = enriched["overview"].get("group", "General")
                existing.append(enriched)
            elif html_file and (REPORTS_DIR / html_file).exists():
                enriched = dict(item)
                enriched["overview"] = _report_overview(enriched)
                enriched["group"] = enriched["overview"].get("group", "General")
                existing.append(enriched)

        if len(existing) != len(items):
            _save_index(existing)

        return jsonify({
            "ok": True,
            "version": "v3.8",
            "count": len(existing),
            "reports": existing,
            "paths": {
                "reports": str(REPORTS_DIR),
                "index": str(INDEX_PATH),
            },
        })

    @app.route("/api/reports/create", methods=["GET", "POST"])
    def create_report_from_zip_v38():
        zip_code = (
            request.args.get("zip")
            or request.form.get("zip")
            or ""
        ).strip()

        water_id = (
            request.args.get("water_id")
            or request.form.get("water_id")
            or ""
        ).strip()

        title = (
            request.args.get("title")
            or request.form.get("title")
            or ""
        ).strip()
        selected_forecast_date = (
            request.args.get("selected_forecast_date")
            or request.form.get("selected_forecast_date")
            or request.args.get("forecast_date")
            or request.form.get("forecast_date")
            or ""
        ).strip()

        if not zip_code:
            return jsonify({
                "ok": False,
                "error": "Missing ZIP. Use /api/reports/create?zip=60543",
            }), 400

        query_params = {"zip": zip_code}
        if water_id:
            query_params["water_id"] = water_id
        query = urlencode(query_params)

        try:
            with app.test_client() as client:
                resp = client.get(f"/api/intel?{query}")
                status_code = getattr(resp, "status_code", 500)

                if status_code >= 400:
                    return jsonify({
                        "ok": False,
                        "error": f"/api/intel returned HTTP {status_code}",
                        "body": resp.get_data(as_text=True)[:800],
                    }), 502

                intel = resp.get_json(silent=True)
                if intel is None:
                    return jsonify({
                        "ok": False,
                        "error": "/api/intel did not return JSON",
                        "body": resp.get_data(as_text=True)[:800],
                    }), 502

        except Exception as exc:
            return jsonify({
                "ok": False,
                "error": f"Unable to call /api/intel: {exc}",
            }), 500

        forecast_rows = _forecast_rows(intel.get("forecast") if isinstance(intel.get("forecast"), list) else [])
        forecast_selection = _selected_forecast_context(
            forecast_rows,
            selected_date=selected_forecast_date,
            fallback_date=_now().date().isoformat(),
        )
        summary_for_title = _extract_summary({"intel": intel})
        if forecast_rows:
            selected_forecast_date = forecast_selection["selected_forecast_date"]
            selected_forecast_label = forecast_selection["selected_forecast_label"]
            forecast_day_index = forecast_selection["forecast_day_index"]
        else:
            selected_forecast_label = forecast_selection["selected_forecast_label"] or _now().strftime("%A, %B %d, %Y")
            forecast_day_index = ""

        title = title or _default_report_title(zip_code, {"intel": intel}, summary_for_title, selected_forecast_label)

        payload = {
            "title": title,
            "zip": zip_code,
            "source": f"/api/intel?{query}",
            "saved_at": _now().isoformat(timespec="seconds"),
            "intel": intel,
            "selected_forecast_date": selected_forecast_date,
            "selected_forecast_label": selected_forecast_label,
            "forecast_day_index": forecast_day_index,
        }

        meta = _save_report(payload, title=title, zip_code=zip_code)
        meta["selected_forecast_date"] = selected_forecast_date
        meta["selected_forecast_label"] = selected_forecast_label
        meta["forecast_day_index"] = forecast_day_index
        items = _index()
        items = [meta if item.get("id") == meta.get("id") else item for item in items]
        _save_index(items)

        return jsonify({
            "ok": True,
            "version": "v3.8",
            "report": meta,
        })

    @app.route("/api/reports/save", methods=["POST"])
    def save_report_payload_v38():
        payload = request.get_json(silent=True)

        if not isinstance(payload, dict):
            return jsonify({
                "ok": False,
                "error": "POST a JSON object to save a report.",
            }), 400

        title = (
            request.args.get("title")
            or payload.get("title")
            or "Trip Report"
        )
        selected_forecast_date = (
            request.args.get("selected_forecast_date")
            or payload.get("selected_forecast_date")
            or payload.get("forecast_date")
            or ""
        )

        zip_code = (
            request.args.get("zip")
            or payload.get("zip")
            or payload.get("zipcode")
            or payload.get("postal_code")
            or ""
        )

        if selected_forecast_date:
            payload.setdefault("selected_forecast_date", str(selected_forecast_date))

        if not title or title == "Trip Report":
            summary_for_title = _extract_summary(payload)
            title = _default_report_title(zip_code, payload, summary_for_title, payload.get("selected_forecast_label") or "")

        meta = _save_report(payload, title=str(title), zip_code=str(zip_code))

        return jsonify({
            "ok": True,
            "version": "v3.8",
            "report": meta,
        })

    @app.route("/api/reports/download/<filename>")
    def download_report_file_v38(filename: str):
        path = _safe_report_file(filename)
        if path is None:
            return jsonify({"ok": False, "error": "Report not found"}), 404

        mimetype = "application/json" if path.suffix == ".json" else "text/html"

        try:
            return send_file(
                path,
                mimetype=mimetype,
                as_attachment=True,
                download_name=path.name,
            )
        except TypeError:
            return send_file(
                path,
                mimetype=mimetype,
                as_attachment=True,
                attachment_filename=path.name,
            )

    @app.route("/api/reports/delete", methods=["POST"])
    def delete_report_v38():
        payload = request.get_json(silent=True) or {}
        report_id = str(
            payload.get("report_id")
            or payload.get("id")
            or request.args.get("report_id")
            or request.args.get("id")
            or ""
        ).strip()

        try:
            result = _delete_report_assets(report_id)
            return jsonify({
                "ok": True,
                "version": "v3.8",
                "report_id": report_id,
                "deleted_files": result["deleted_files"],
                "remaining_count": result["remaining_count"],
            })
        except FileNotFoundError:
            return jsonify({"ok": False, "error": "Report not found"}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/api/reports/delete-all", methods=["POST"])
    def delete_all_reports_v38():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            payload = {}
        if payload.get("confirm") is not True:
            return jsonify({"ok": False, "error": "Permanent deletion confirmation is required."}), 400

        try:
            result = _delete_all_report_assets()
            return jsonify({
                "ok": True,
                "version": "v3.8",
                "deleted_report_count": result["deleted_report_count"],
                "deleted_files": result["deleted_files"],
                "remaining_count": result["remaining_count"],
            })
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/api/reports/view/<report_id>")
    def view_report_v38(report_id: str):
        if "/" in report_id or "\\" in report_id or ".." in report_id:
            return jsonify({"ok": False, "error": "Invalid report id"}), 400

        items = _index()
        match = None

        for item in items:
            if item.get("id") == report_id:
                match = item
                break

        if not match:
            return jsonify({"ok": False, "error": "Report not found"}), 404

        json_file = match.get("json_file")
        if not json_file:
            return jsonify({"ok": False, "error": "Report JSON not found"}), 404

        path = _safe_report_file(json_file)
        if path is None:
            return jsonify({"ok": False, "error": "Report JSON not found"}), 404

        try:
            wrapped = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return jsonify({"ok": False, "error": f"Report JSON unreadable: {exc}"}), 500

        payload = wrapped.get("payload") if isinstance(wrapped, dict) else None
        if not isinstance(payload, dict):
            payload = wrapped if isinstance(wrapped, dict) else {}

        selected_forecast_date = (
            request.args.get("selected_forecast_date")
            or request.args.get("forecast_date")
            or match.get("selected_forecast_date")
            or payload.get("selected_forecast_date")
            or ""
        ).strip()

        return _render_report_html(match, payload, selected_forecast_date=selected_forecast_date)

    @app.route("/api/reports/status")
    def reports_status_v38():
        items = _index()
        return jsonify({
            "ok": True,
            "version": "v3.8",
            "count": len(items),
            "paths": {
                "reports": str(REPORTS_DIR),
                "index": str(INDEX_PATH),
            },
            "routes": [
                "/reports",
                "/api/reports",
                "/api/reports/status",
                "/api/reports/create?zip=60543",
                "/api/reports/save",
                "/api/reports/download/<filename>",
                "/api/reports/delete",
                "/api/reports/delete-all",
                "/api/reports/view/<report_id>",
            ],
        })
