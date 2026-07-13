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


def _build_report_context(report_meta: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
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
        "best_time": {
            "label": _compact_text(best_bet.get("time_label"), "Any time"),
            "range": _compact_text(best_bet.get("time_range"), "Any time"),
            "best_hour": _compact_text(best_bet.get("best_hour"), ""),
        },
        "best_bet": best_bet_ctx,
        "conditions": condition_rows,
        "smart_intelligence": {
            "headline": _compact_text(smart.get("headline"), "Fishing pattern"),
            "summary": _compact_text(smart.get("summary"), ""),
            "condition_labels": smart_condition_labels,
            "clarity_label": _compact_text(smart_clarity.get("label"), "unknown"),
            "clarity_basis": _compact_text(smart_clarity.get("basis"), ""),
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


def _render_report_html(report_meta: dict[str, Any], payload: dict[str, Any]) -> str:
    return render_template("snapshot.html", report=_build_report_context(report_meta, payload))


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

    wrapped = {
        "meta": meta,
        "payload": payload,
        "summary": summary,
    }

    json_path = REPORTS_DIR / json_name
    html_path = REPORTS_DIR / html_name

    _write_json(json_path, wrapped)
    html_path.write_text(_render_report_html(meta, payload), encoding="utf-8")

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
        return """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Angler Intel - Saved Reports</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/css/style.css">
  <style>
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 2rem;
      max-width: 1100px;
      line-height: 1.45;
      background: #0b1710;
      color: #f4fff6;
    }
    .page-title {
      margin-top: 1rem;
    }
    .card {
      border: 1px solid rgba(166, 232, 182, 0.35);
      border-radius: 12px;
      padding: 1rem;
      margin: 1rem 0;
      background: #f8fff9;
      color: #102417;
    }
    input, button {
      font-size: 1rem;
      padding: 0.5rem;
      margin: 0.2rem 0;
    }
    input {
      width: 100%;
      max-width: 420px;
      border-radius: 8px;
      border: 1px solid #8bbd96;
    }
    button {
      border-radius: 8px;
      border: 1px solid #5fa66f;
      cursor: pointer;
      background: #e9f8ee;
      color: #102417;
      font-weight: 700;
    }
    pre {
      background: #102417;
      color: #f4fff6;
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      white-space: pre-wrap;
    }
    .muted {
      color: #5b6b60;
    }
    .report-row {
      border-top: 1px solid #dceee1;
      padding: 0.75rem 0;
    }
    a {
      color: #1f8f45;
      font-weight: 700;
    }

    .ai-main-tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 0.45rem;
      align-items: center;
      margin: 0.75rem 0 1rem 0;
      padding: 0.65rem;
      border: 1px solid #2f6f45;
      border-radius: 14px;
      background: #102417;
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.18);
    }
    .ai-main-tab {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 2.25rem;
      padding: 0.45rem 0.75rem;
      border-radius: 999px;
      border: 1px solid #5fa66f;
      text-decoration: none;
      font-weight: 800;
      line-height: 1;
      color: #102417;
      background: #f4fff6;
    }
    .ai-main-tab:visited {
      color: #102417;
    }
    .ai-main-tab:hover,
    .ai-main-tab:focus {
      text-decoration: none;
      background: #dff6e5;
      color: #06150a;
      border-color: #7ad08d;
      transform: translateY(-1px);
    }
    .ai-main-tab.active {
      background: #1f8f45;
      color: #ffffff;
      border-color: #a6e8b6;
    }
    .ai-main-tab.active:visited {
      color: #ffffff;
    }
    @media (max-width: 640px) {
      body {
        margin: 1rem;
      }
      .ai-main-tabs {
        gap: 0.35rem;
        padding: 0.5rem;
      }
      .ai-main-tab {
        flex: 1 1 calc(50% - 0.5rem);
        padding: 0.55rem 0.5rem;
      }
    }
  </style>
</head>
<body>
  <nav class="ai-main-tabs" aria-label="Angler Intel navigation">
    <a class="ai-main-tab" href="/">Dashboard</a>
    <a class="ai-main-tab" href="/waters">Local Waters</a>
    <a class="ai-main-tab active" href="/reports">Saved Reports</a>
    <a class="ai-main-tab" href="/app-health">App Health</a>
  </nav>

  <h1 class="page-title">Saved Offline Reports</h1>
  <p>Saved reports keep local fishing trip snapshots on this Pi using your current Angler Intel data.</p>

  <div class="card">
    <h2>Create report from ZIP</h2>
    <p class="muted">This calls your existing <code>/api/intel?zip=...</code> endpoint and saves the result locally.</p>

    <label>
      ZIP code<br>
      <input id="zipInput" placeholder="60543" value="60543">
    </label>
    <br>

    <label>
      Report title<br>
      <input id="titleInput" placeholder="Evening bass trip">
    </label>
    <br>

    <button onclick="createReport()">Create saved report</button>
    <pre id="createResult">No report created yet.</pre>
  </div>

  <div class="card">
    <h2>Existing reports</h2>
    <button onclick="loadReports()">Refresh reports</button>
    <div id="reportsList">Loading...</div>
  </div>

  <p>
    <a href="/">Back to dashboard</a> |
    <a href="/app-health">App Health</a>
  </p>

<script>
async function createReport() {
  const zip = document.getElementById("zipInput").value.trim();
  const title = document.getElementById("titleInput").value.trim();
  const box = document.getElementById("createResult");

  if (!zip) {
    box.textContent = "Enter a ZIP code first.";
    return;
  }

  box.textContent = "Creating report...";

  const params = new URLSearchParams({zip});
  if (title) params.set("title", title);

  try {
    const res = await fetch("/api/reports/create?" + params.toString(), {method: "POST"});
    const data = await res.json();
    box.textContent = JSON.stringify(data, null, 2);
    loadReports();
  } catch (err) {
    box.textContent = "Report failed: " + err;
  }
}

async function loadReports() {
  const box = document.getElementById("reportsList");
  box.textContent = "Loading...";

  try {
    const res = await fetch("/api/reports");
    const data = await res.json();

    if (!data.reports || data.reports.length === 0) {
      box.innerHTML = "<p class='muted'>No saved reports yet.</p>";
      return;
    }

    box.innerHTML = data.reports.map(r => `
      <div class="report-row">
        <strong>${escapeHtml(r.title || "Untitled report")}</strong><br>
        <span class="muted">${escapeHtml(r.created || "")} ${r.zip ? " ZIP " + escapeHtml(r.zip) : ""}</span><br>
        <a href="${r.view_url}">View</a> |
        <a href="${r.html_url}">Download HTML</a> |
        <a href="${r.json_url}">Download JSON</a>
      </div>
    `).join("");
  } catch (err) {
    box.textContent = "Unable to load reports: " + err;
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadReports();
</script>
</body>
</html>
"""


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
                existing.append(item)
            elif html_file and (REPORTS_DIR / html_file).exists():
                existing.append(item)

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

        payload = {
            "title": title or f"Trip Report ZIP {zip_code}",
            "zip": zip_code,
            "source": f"/api/intel?{query}",
            "saved_at": _now().isoformat(timespec="seconds"),
            "intel": intel,
        }

        meta = _save_report(payload, title=title, zip_code=zip_code)

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

        zip_code = (
            request.args.get("zip")
            or payload.get("zip")
            or payload.get("zipcode")
            or payload.get("postal_code")
            or ""
        )

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

        return _render_report_html(match, payload)

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
                "/api/reports/view/<report_id>",
            ],
        })
