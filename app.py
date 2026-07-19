from flask import Flask, request, jsonify, render_template, redirect
import json
from pathlib import Path
from datetime import datetime, timedelta
import uuid

from intelligence.catch_learning import build_catch_learning_summary
from intelligence.location import get_coords
from intelligence.weather import get_weather, f_temp, mph, inhg
from intelligence.waters import detect_water, infer_area_type
from intelligence.species import SPECIES, score_species
from intelligence.species_assets import get_species_image
from intelligence.lure_assets import resolve_lure_asset
from intelligence.gear_intelligence import recommend_owned_setup, build_trip_packing_list, summarize_gear_maintenance, summarize_gear_usage
from intelligence.lures import choose_lure
from intelligence.scoring import overall_score, time_blocks, rating, hourly_bite_forecast
from intelligence.smart_intelligence import build_smart_intelligence, build_smart_intelligence_fallback
from intelligence.target_profile import (
    available_target_species,
    load_target_profile,
    resolve_target_species,
    save_target_profile,
    species_fit_bonus,
)
from intelligence.app_health_sqlite import get_sqlite_health_for_app
from intelligence.app_health_backup import get_backup_health_for_app
from intelligence.app_health_versions import get_version_health_for_app
from intelligence.app_health_intelligence import get_smart_intelligence_health_for_app
from intelligence.app_health_sqlite_transition import get_sqlite_transition_health_for_app
from intelligence.app_health_map_data import get_map_data_health_for_app
from intelligence.map_data import get_map_data_readiness
from intelligence.water_registry import append_custom_water_record, load_water_catalog, get_water_record_by_id
from gear.inventory import get_item as get_gear_item, record_item_usage as record_gear_item_usage

app = Flask(__name__)

# --- Angler Intel IL v4.4.3 App Health backup routes ---
try:
    from angler_health_backup_v443 import register_health_backup_routes_v443
    register_health_backup_routes_v443(app)
except Exception as exc:
    print(f"[angler-intel v4.4.3 health backups disabled] {exc}")
# --- end v4.4.3 App Health backup routes ---


# --- Angler Intel IL v4.4 smart recommendation routes ---
try:
    from angler_recommendations_v44 import register_recommendation_routes_v44
    register_recommendation_routes_v44(app)
except Exception as exc:
    print(f"[angler-intel v4.4 recommendations disabled] {exc}")
# --- end v4.4 smart recommendation routes ---


# --- Angler Intel IL v4.3.1 cleanup/readiness routes ---
try:
    from angler_cleanup_v431 import register_cleanup_routes_v431
    register_cleanup_routes_v431(app)
except Exception as exc:
    print(f"[angler-intel v4.3.1 cleanup disabled] {exc}")
# --- end v4.3.1 cleanup/readiness routes ---


# --- Angler Intel IL v4.3 species and rig routes ---
try:
    from angler_species_rigs_v43 import register_species_rig_routes_v43
    register_species_rig_routes_v43(app)
except Exception as exc:
    print(f"[angler-intel v4.3 species/rigs disabled] {exc}")
# --- end v4.3 species and rig routes ---


# --- Angler Intel IL v4.0 local waters routes ---
try:
    from angler_waters_v40 import register_local_waters_routes_v40
    register_local_waters_routes_v40(app)
except Exception as exc:
    print(f"[angler-intel v4.0 local waters disabled] {exc}")
# --- end v4.0 local waters routes ---


# --- Angler Intel IL v3.10 admin routes ---
try:
    from angler_admin_v310 import register_admin_routes_v310
    register_admin_routes_v310(app)
except Exception as exc:
    print(f"[angler-intel v3.10 admin disabled] {exc}")
# --- end v3.10 admin routes ---


# --- Angler Intel IL v3.9 app health routes ---
try:
    from angler_health_v39 import register_health_routes_v39
    register_health_routes_v39(app)
except Exception as exc:
    print(f"[angler-intel v3.9 health disabled] {exc}")
# --- end v3.9 app health routes ---


# --- Angler Intel IL v3.8 saved offline report routes ---
try:
    from angler_reports_v38 import register_report_routes_v38
    register_report_routes_v38(app)
except Exception as exc:
    print(f"[angler-intel v3.8 reports disabled] {exc}")
# --- end v3.8 saved offline report routes ---


# --- Angler Intel IL v3.7 backup/export routes ---
try:
    from angler_exports_v37 import register_export_routes_v37
    register_export_routes_v37(app)
except Exception as exc:
    print(f"[angler-intel v3.7 exports disabled] {exc}")
# --- end v3.7 backup/export routes ---


APP_VERSION = "v6.13-gear-intelligence-packing-catch-linking"
APP_RELEASE = "v6.13-gear-intelligence-packing-catch-linking"
app.config["APP_VERSION"] = APP_VERSION
app.config["APP_RELEASE"] = APP_RELEASE
# Keep the core version marker stable for compatibility while surfacing the
# current visible release label in the UI.
# modern_ui_refresh compatibility marker
# v6.10-tackle-locker compatibility marker
# v6.11-gear-catalog-flexible-search compatibility marker
# v6.13-gear-intelligence-packing-catch-linking compatibility marker


@app.context_processor
def inject_app_version():
    return {
        "app_version": app.config.get("APP_RELEASE", APP_VERSION),
        "target_species_options": available_target_species(),
        "fish_image": fish_image,
    }

DATA_DIR = Path("data")
FAVORITES_FILE = DATA_DIR / "favorites.json"
CATCHES_FILE = DATA_DIR / "catches.json"


def ensure_data():
    DATA_DIR.mkdir(exist_ok=True)

    if not FAVORITES_FILE.exists():
        FAVORITES_FILE.write_text(json.dumps([
            {"name": "Home Area", "zip": "60543"}
        ], indent=2))

    if not CATCHES_FILE.exists():
        CATCHES_FILE.write_text(json.dumps([], indent=2))


def read_json(path, fallback):
    ensure_data()
    try:
        return json.loads(path.read_text())
    except Exception:
        return fallback


def write_json(path, data):
    ensure_data()
    path.write_text(json.dumps(data, indent=2))


def load_favorites():
    return read_json(FAVORITES_FILE, [])


def save_favorites(favorites):
    write_json(FAVORITES_FILE, favorites)


def load_catches():
    return read_json(CATCHES_FILE, [])


def save_catches(catches):
    write_json(CATCHES_FILE, catches)


def _catch_gear_fields(payload):
    fields = {}
    labels = {}
    for key in ("rod", "reel", "line", "lure", "terminal"):
        ref = str(payload.get(f"{key}_id", "")).strip()
        if not ref:
            continue
        fields[key] = ref
        item = get_gear_item(ref)
        if item:
            labels[key] = item.get("display_name") or item.get("brand") or key.title()
    return fields, labels


def _enrich_catch_record(catch):
    record = dict(catch or {})
    gear_refs = record.get("gear_refs") if isinstance(record.get("gear_refs"), dict) else {}
    gear_labels = record.get("gear_labels") if isinstance(record.get("gear_labels"), dict) else {}

    if not gear_refs:
        gear_refs = {}
        for key in ("rod", "reel", "line", "lure", "terminal"):
            value = str(record.get(f"{key}_id", "")).strip()
            if value:
                gear_refs[key] = value

    if not gear_labels and gear_refs:
        for key, ref in gear_refs.items():
            item = get_gear_item(ref)
            if item:
                gear_labels[key] = item.get("display_name") or item.get("brand") or key.title()

    if gear_refs:
        record["gear_refs"] = gear_refs
    if gear_labels:
        record["gear_labels"] = gear_labels
        record["gear_summary"] = ", ".join(
            f"{label}: {gear_labels[label]}"
            for label in ("rod", "reel", "line", "lure", "terminal")
            if gear_labels.get(label)
        )
    return record


def slugify_species(name):
    return (
        name.lower()
        .replace("/", " ")
        .replace("-", " ")
        .replace(" ", "_")
    )


def fish_image(name):
    return get_species_image(name)


def species_key(name):
    return slugify_species(name).replace("_", "-")


def compact_text(value, fallback=""):
    text = " ".join(str(value or "").split()).strip()
    return text or fallback


def format_report_datetime(value):
    if not value:
        return "Unknown time"

    if isinstance(value, datetime):
        return value.strftime("%b %d, %Y %I:%M %p")

    text = compact_text(value)
    for fmt in ("%b %d, %Y %I:%M %p", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).strftime("%b %d, %Y %I:%M %p")
        except Exception:
            pass
    return text


def report_lure_label(item):
    asset = item.get("lure_asset") if isinstance(item, dict) else {}
    if isinstance(asset, dict) and asset.get("label"):
        return compact_text(asset.get("label"))
    return compact_text(item.get("name") or item.get("lure_name") or item.get("label") or "Lure", "Lure")


def report_lure_image(item):
    asset = item.get("lure_asset") if isinstance(item, dict) else {}
    if isinstance(asset, dict) and asset.get("path"):
        return asset.get("path")
    return item.get("image") or "/static/lures/generic_lure.png"


def report_species_lure(item, preferred_window="evening"):
    lures = item.get("lures") if isinstance(item, dict) else {}
    cards = lures.get("cards", {}) if isinstance(lures, dict) else {}
    if isinstance(cards, dict):
        for key in (preferred_window, "evening", "morning", "midday"):
            card = cards.get(key)
            if isinstance(card, dict):
                return card
    return {}


def report_species_rows(species_rows, best_bet=None, best_time=None):
    preferred_window = "evening"
    if isinstance(best_time, dict):
        label = compact_text(best_time.get("label")).lower()
        if "morning" in label:
            preferred_window = "morning"
        elif "midday" in label:
            preferred_window = "midday"

    rows = []
    best_name = compact_text((best_bet or {}).get("species")).lower()

    for item in species_rows or []:
        if not isinstance(item, dict):
            continue
        lure_card = report_species_lure(item, preferred_window)
        rows.append({
            "name": compact_text(item.get("name"), "Species"),
            "score": item.get("score"),
            "rating": compact_text(item.get("rating"), "Good"),
            "fish_image": item.get("fish_image") or fish_image(item.get("name")),
            "habitat": compact_text(item.get("habitat"), "Mixed habitat"),
            "lure_label": report_lure_label(lure_card) if lure_card else "",
            "lure_image": report_lure_image(lure_card) if lure_card else "",
            "why": compact_text(lure_card.get("why") if isinstance(lure_card, dict) else "", ""),
            "target_fit": "Current trip target" if compact_text(item.get("name")).lower() == best_name else "",
        })

    return rows


def report_lure_rows(lure_rows):
    rows = []
    for item in lure_rows or []:
        if not isinstance(item, dict):
            continue
        rows.append({
            "species": compact_text(item.get("species"), "Species"),
            "species_score": item.get("species_score"),
            "name": report_lure_label(item),
            "image": report_lure_image(item),
            "type": compact_text(item.get("type"), ""),
            "color": compact_text(item.get("color"), ""),
            "speed": compact_text(item.get("speed"), ""),
            "size": compact_text(item.get("size"), ""),
            "why": compact_text(item.get("why"), ""),
            "top_pick": bool(item.get("top_pick")),
        })
    return rows


def report_outlook_rows(forecast_rows):
    rows = []
    for item in forecast_rows or []:
        if not isinstance(item, dict):
            continue
        pretty_date = ""
        if item.get("date"):
            try:
                pretty_date = datetime.strptime(item.get("date"), "%Y-%m-%d").strftime("%a, %b %d")
            except Exception:
                pretty_date = compact_text(item.get("date"), "")
        rows.append({
            "date": compact_text(item.get("date"), ""),
            "pretty_date": pretty_date,
            "score": item.get("score"),
            "rating": compact_text(item.get("rating"), ""),
            "high": item.get("high"),
            "low": item.get("low"),
            "wind": item.get("wind"),
            "selected": False,
        })
    return rows


def forecast_label(date_text):
    value = compact_text(date_text, "")
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%A, %B %d, %Y")
    except Exception:
        return value


def selected_forecast_context(forecast_rows, selected_date=None, fallback_date=None):
    rows = [row for row in forecast_rows if isinstance(row, dict)]
    selected_text = compact_text(selected_date, "")
    selected_row = None
    selected_index = None

    if selected_text:
        for idx, row in enumerate(rows):
            if compact_text(row.get("date"), "") == selected_text:
                selected_row = row
                selected_index = idx
                break

    if selected_row is None and rows:
        selected_row = rows[0]
        selected_index = 0
        selected_text = compact_text(selected_row.get("date"), selected_text)

    if not selected_text:
        selected_text = compact_text(fallback_date, "")

    label = forecast_label(selected_text) or compact_text(fallback_date, "")
    if not label and selected_row:
        label = compact_text(selected_row.get("pretty_date"), "") or compact_text(selected_row.get("date"), "")

    focus = {
        "date": compact_text(selected_row.get("date"), selected_text) if selected_row else selected_text,
        "pretty_date": compact_text(selected_row.get("pretty_date"), label) if selected_row else label,
        "rating": compact_text(selected_row.get("rating"), "") if selected_row else "",
        "high": selected_row.get("high") if selected_row else None,
        "low": selected_row.get("low") if selected_row else None,
        "wind": selected_row.get("wind") if selected_row else None,
        "score": selected_row.get("score") if selected_row else None,
    }

    return {
        "selected_forecast_date": selected_text,
        "selected_forecast_label": label,
        "forecast_day_index": selected_index if selected_index is not None else "",
        "forecast_focus": focus,
        "forecast_rows": rows,
    }


def report_water_rows(water_rows):
    rows = []
    for item in water_rows or []:
        if not isinstance(item, dict):
            continue
        rows.append({
            "name": compact_text(item.get("name"), "Waterbody"),
            "count": item.get("count"),
            "type": compact_text(item.get("type"), ""),
        })
    return rows


def build_snapshot_report(data, selected_forecast_date=None):
    best_bet = data.get("best_bet", {}) if isinstance(data, dict) else {}
    weather = data.get("weather", {}) if isinstance(data, dict) else {}
    smart = data.get("smart_intelligence", {}) if isinstance(data, dict) else {}
    catch_insights = data.get("catch_insights", {}) if isinstance(data, dict) else {}
    target_species = compact_text(data.get("selected_species") or data.get("target_species"), "Auto")
    forecast_rows = report_outlook_rows(data.get("forecast", []))
    forecast_selection = selected_forecast_context(
        forecast_rows,
        selected_date=selected_forecast_date or data.get("selected_forecast_date"),
        fallback_date=data.get("generated_at"),
    )
    for row in forecast_rows:
        row["selected"] = compact_text(row.get("date"), "") == forecast_selection["selected_forecast_date"] if forecast_selection["selected_forecast_date"] else False

    raw_json = json.dumps(data, indent=2, sort_keys=True, default=str)

    return {
        "title": f"Trip Report ZIP {compact_text(data.get('location', {}).get('zip'), '')}".strip(),
        "subtitle": "Saved by Angler Intel",
        "generated_at": format_report_datetime(data.get("generated_at")),
        "location_label": compact_text(
            ", ".join(part for part in [data.get("location", {}).get("city"), data.get("location", {}).get("state")] if part),
            compact_text(data.get("location", {}).get("zip"), "Unknown location"),
        ),
        "zip_code": compact_text(data.get("location", {}).get("zip"), ""),
        "target_species": target_species,
        "overall_score": data.get("overall", {}).get("score"),
        "overall_rating": compact_text(data.get("overall", {}).get("rating"), ""),
        "selected_forecast_date": forecast_selection["selected_forecast_date"],
        "selected_forecast_label": forecast_selection["selected_forecast_label"],
        "forecast_focus": forecast_selection["forecast_focus"],
        "best_time": {
            "label": compact_text(best_bet.get("time_label"), "Any time"),
            "range": compact_text(best_bet.get("time_range"), "Any time"),
            "best_hour": compact_text(best_bet.get("best_hour"), ""),
        },
        "best_bet": {
            "species": compact_text(best_bet.get("species"), "Target Species"),
            "species_score": best_bet.get("species_score"),
            "fish_image": best_bet.get("fish_image") or "/static/fish/generic_fish.png",
            "lure_name": report_lure_label(best_bet),
            "lure_image": report_lure_image(best_bet),
            "speed": compact_text(best_bet.get("speed"), ""),
            "size": compact_text(best_bet.get("size"), ""),
            "why": compact_text(best_bet.get("why"), ""),
            "reasons": [compact_text(item, "") for item in best_bet.get("reasons", []) if compact_text(item, "")],
        },
        "conditions": (
            [
                {"label": "Forecast date", "value": forecast_selection["selected_forecast_label"]},
                {"label": "Forecast rating", "value": compact_text(forecast_selection["forecast_focus"].get("rating"), compact_text(data.get("overall", {}).get("rating"), "Unknown"))},
                {"label": "High / Low", "value": f"{forecast_selection['forecast_focus'].get('high', '?')}° / {forecast_selection['forecast_focus'].get('low', '?')}°"},
                {"label": "Wind", "value": f"{forecast_selection['forecast_focus'].get('wind', '?')} mph"},
                {"label": "Score", "value": forecast_selection["forecast_focus"].get("score")},
                {"label": "Source", "value": "Open-Meteo forecast"},
            ]
            if forecast_rows
            else [
                {"label": "Temperature", "value": f"{weather.get('temp', '?')}°F"},
                {"label": "Wind", "value": f"{weather.get('wind', '?')} mph"},
                {"label": "Pressure", "value": f"{weather.get('pressure', '?')} inHg"},
                {"label": "Cloud Cover", "value": f"{weather.get('cloud', '?')}%"},
                {"label": "Source", "value": compact_text(weather.get("source"), "unknown")},
            ]
        ),
        "smart_intelligence": {
            "headline": compact_text(smart.get("headline"), "Fishing pattern"),
            "summary": compact_text(smart.get("summary"), ""),
            "condition_labels": [compact_text(item, "") for item in smart.get("condition_labels", []) if compact_text(item, "")],
            "clarity_label": compact_text((smart.get("clarity_signal") or {}).get("label"), "unknown"),
            "clarity_basis": compact_text((smart.get("clarity_signal") or {}).get("basis"), ""),
            "ranking_factors": [
                {
                    "label": compact_text(item.get("label"), ""),
                    "value": compact_text(item.get("value"), ""),
                    "why": compact_text(item.get("why"), ""),
                }
                for item in (smart.get("ranking_factors") or [])
                if isinstance(item, dict) and (compact_text(item.get("label"), "") or compact_text(item.get("why"), ""))
            ],
            "explanation_sections": [
                {
                    "label": compact_text(item.get("label"), ""),
                    "value": compact_text(item.get("value"), ""),
                    "why": compact_text(item.get("why"), ""),
                    "details": [compact_text(detail, "") for detail in (item.get("details") or []) if compact_text(detail, "")],
                }
                for item in (smart.get("explanation_sections") or [])
                if isinstance(item, dict) and (compact_text(item.get("label"), "") or compact_text(item.get("why"), ""))
            ],
            "decision_factors": [compact_text(item, "") for item in smart.get("decision_factors", []) if compact_text(item, "")],
            "strategy": [compact_text(item, "") for item in smart.get("strategy", []) if compact_text(item, "")],
            "positive_signals": [compact_text(item, "") for item in smart.get("positive_signals", []) if compact_text(item, "")],
            "caution_signals": [compact_text(item, "") for item in smart.get("caution_signals", []) if compact_text(item, "")],
        },
        "species_ranking": report_species_rows(data.get("species", []), best_bet=best_bet, best_time=data.get("best_time")),
        "recommended_lures": report_lure_rows(data.get("lure_cards", [])),
        "nearby_waters": report_water_rows((catch_insights or {}).get("top_waterbodies", [])),
        "forecast": forecast_rows,
        "catch_insights": catch_insights,
        "raw_json": raw_json,
    }


def find_species_entry(name):
    target = species_key(name)
    for species in SPECIES:
        if species_key(species.get("name", "")) == target:
            return species
    return None


def format_hour_label(hour):
    if hour is None:
        return None

    suffix = "PM" if hour >= 12 else "AM"
    h = hour % 12
    if h == 0:
        h = 12
    return f"{h} {suffix}"


def catch_insights(zip_code):
    catches = load_catches()
    return build_catch_learning_summary(catches, zip_code=zip_code)


def fallback_weather_payload():
    """Pi-safe weather fallback used only when the live weather feed is unavailable."""
    today = datetime.now().date()
    hourly_times = [
        f"{today.isoformat()}T{hour:02d}:00"
        for hour in range(24)
    ]
    daily_times = [
        (today + timedelta(days=idx)).isoformat()
        for idx in range(7)
    ]

    return {
        "source": "fallback",
        "fallback": True,
        "current": {
            "temperature_2m": 18.3,
            "wind_speed_10m": 12.9,
            "pressure_msl": 1015.9,
            "cloud_cover": 50,
        },
        "hourly": {
            "time": hourly_times,
            "temperature_2m": [18.3 for _ in hourly_times],
            "wind_speed_10m": [12.9 for _ in hourly_times],
            "pressure_msl": [1015.9 for _ in hourly_times],
            "cloud_cover": [50 for _ in hourly_times],
        },
        "daily": {
            "time": daily_times,
            "temperature_2m_max": [22.2 for _ in daily_times],
            "temperature_2m_min": [13.9 for _ in daily_times],
            "wind_speed_10m_max": [16.1 for _ in daily_times],
        },
    }


def build_best_bet(species_ranked, best_time, best_hour, base_score, temp_f, wind_mph, pressure_inhg, area_type, zip_code):
    if not species_ranked:
        safe_best_time = best_time if isinstance(best_time, dict) else {}
        safe_best_hour = best_hour if isinstance(best_hour, dict) else {}
        lure_asset = resolve_lure_asset(
            recommendation_text="General-purpose lure",
            lure_type="soft_plastic_worm",
            color="green_pumpkin",
        )
        return {
            "species": "Target Species",
            "species_score": 0,
            "fish_image": "/static/fish/largemouth_bass.png",
            "time_label": safe_best_time.get("label") or "Any time",
            "time_range": safe_best_time.get("time") or "Any time",
            "best_hour": format_hour_label(safe_best_hour.get("hour")) if safe_best_hour else None,
            "lure_name": "General-purpose lure",
            "lure_image": lure_asset["path"],
            "lure_asset": lure_asset,
            "lure_type": "soft_plastic_worm",
            "lure_color": "green_pumpkin",
            "speed": "Slow speed",
            "size": "3-5 in",
            "colors": ["Natural", "White"],
            "why": "Species intelligence is unavailable, so use a simple general-purpose pattern.",
            "reasons": [
                "Species guidance is unavailable for this search.",
                "Use a simple bait and let local conditions drive the first adjustment.",
            ],
        }

    top = species_ranked[0]
    safe_best_time = best_time if isinstance(best_time, dict) else {}
    safe_best_hour = best_hour if isinstance(best_hour, dict) else {}
    lures = top.get("lures") if isinstance(top.get("lures"), dict) else {}
    top_name = top.get("name", "Target Species")
    top_score = top.get("score", 0)
    top_image = top.get("fish_image", "/static/fish/generic_fish.png")

    cards = lures.get("cards", {})
    best_lure = None

    if cards:
        if safe_best_time.get("label") == "Morning":
            best_lure = cards.get("morning")
        elif safe_best_time.get("label") == "Midday":
            best_lure = cards.get("midday")
        else:
            best_lure = cards.get("evening")

    if not best_lure:
        best_lure = {
            "name": lures.get("evening", "Spinnerbait"),
            "type": "spinnerbait",
            "color": "chartreuse_white",
            "speed": "Medium speed",
            "size": "3/8 oz",
            "colors": ["White", "Chartreuse"],
            "why": "Best general recommendation based on current species and bite window."
        }

    lure_asset = resolve_lure_asset(
        recommendation_text=best_lure.get("name"),
        lure_type=best_lure.get("type"),
        color=best_lure.get("color"),
    )

    reasons = []

    if base_score >= 80:
        reasons.append("Overall conditions are excellent.")
    elif base_score >= 65:
        reasons.append("Overall conditions are good.")
    else:
        reasons.append("Conditions are workable, but fish may be selective.")

    if wind_mph is not None and 5 <= wind_mph <= 15:
        reasons.append("Wind is in the productive range for shallow feeding activity.")
    elif wind_mph is not None and wind_mph > 20:
        reasons.append("Wind is high, so protected banks and heavier presentations are better.")

    if pressure_inhg is not None and pressure_inhg < 29.9:
        reasons.append("Lower pressure can encourage feeding movement.")
    elif pressure_inhg is not None and pressure_inhg > 30.25:
        reasons.append("Higher pressure may slow the bite; finesse presentations may help.")

    if area_type == "pond":
        reasons.append("Detected pond-style habitat favors bass, bluegill, crappie, carp, and channel catfish.")
    elif area_type == "river":
        reasons.append("Detected river-style habitat improves smallmouth, walleye, sauger, catfish, and white bass potential.")
    elif area_type == "lake":
        reasons.append("Detected lake-style habitat supports a wider multi-species pattern.")

    catches = load_catches()
    matching = [
        c for c in catches
        if c.get("zip") == zip_code and c.get("species") == top_name
    ]

    if matching:
        reasons.append(f"Your catch log already has {len(matching)} local catch record(s) for {top_name}.")

    return {
        "species": top_name,
        "species_score": top_score,
        "fish_image": top_image,
        "time_label": safe_best_time.get("label") or "Any time",
        "time_range": safe_best_time.get("time") or "Any time",
        "best_hour": format_hour_label(safe_best_hour.get("hour")) if safe_best_hour else None,
        "lure_name": best_lure["name"],
        "lure_image": lure_asset["path"],
        "lure_asset": lure_asset,
        "lure_type": best_lure.get("type"),
        "lure_color": best_lure.get("color"),
        "speed": best_lure["speed"],
        "size": best_lure["size"],
        "colors": best_lure["colors"],
        "why": best_lure["why"],
        "reasons": reasons
    }


def _weather_summary_for_coords(lat, lon):
    weather_error = None
    try:
        weather = get_weather(lat, lon)
        weather["source"] = weather.get("source", "open-meteo")
        weather["fallback"] = False
    except Exception as exc:
        weather_error = str(exc)
        weather = fallback_weather_payload()

    current = weather.get("current", {}) if isinstance(weather, dict) else {}
    required_weather_keys = ("temperature_2m", "wind_speed_10m", "pressure_msl", "cloud_cover")
    if not isinstance(current, dict) or any(key not in current or current.get(key) is None for key in required_weather_keys):
        if weather_error is None:
            weather_error = "Live weather payload was incomplete, so fallback weather was used."
        weather = fallback_weather_payload()
        weather["error"] = weather_error
        current = weather["current"]

    temp_f = f_temp(current["temperature_2m"])
    wind_mph = mph(current["wind_speed_10m"])
    pressure_inhg = inhg(current["pressure_msl"])
    cloud = current.get("cloud_cover", 0)

    daily = weather.get("daily", {}) if isinstance(weather, dict) else {}
    required_daily_keys = ("time", "temperature_2m_max", "temperature_2m_min", "wind_speed_10m_max")
    if not isinstance(daily, dict) or any(
        key not in daily or not isinstance(daily.get(key), list) or not daily.get(key)
        for key in required_daily_keys
    ):
        if weather_error is None:
            weather_error = "Live weather forecast payload was incomplete, so fallback weather was used."
        weather = fallback_weather_payload()
        weather["error"] = weather_error
        current = weather["current"]
        temp_f = f_temp(current["temperature_2m"])
        wind_mph = mph(current["wind_speed_10m"])
        pressure_inhg = inhg(current["pressure_msl"])
        cloud = current.get("cloud_cover", 0)
        daily = weather["daily"]

    weather_summary = {
        "temp": round(temp_f, 1),
        "wind": round(wind_mph, 1),
        "pressure": round(pressure_inhg, 2),
        "cloud": cloud,
        "source": weather.get("source", "unknown"),
        "fallback": bool(weather.get("fallback")),
        "error": weather_error,
    }

    return weather, weather_summary


def _build_forecast_rows(weather, pressure_inhg, cloud):
    """Build the dashboard's seven-day contract from an already-validated weather payload."""
    daily = weather.get("daily", {}) if isinstance(weather, dict) else {}
    dates = daily.get("time", []) if isinstance(daily, dict) else []
    highs = daily.get("temperature_2m_max", []) if isinstance(daily, dict) else []
    lows = daily.get("temperature_2m_min", []) if isinstance(daily, dict) else []
    winds = daily.get("wind_speed_10m_max", []) if isinstance(daily, dict) else []

    forecast = []
    for date, high, low, wind in zip(dates[:7], highs[:7], lows[:7], winds[:7]):
        max_f = f_temp(high)
        min_f = f_temp(low)
        avg_f = (max_f + min_f) / 2
        max_wind = mph(wind)
        day_score = overall_score(avg_f, max_wind, pressure_inhg, cloud)
        forecast.append({
            "date": date,
            "score": day_score,
            "rating": rating(day_score),
            "high": round(max_f),
            "low": round(min_f),
            "wind": round(max_wind),
        })

    return forecast


def build_water_intel(water, target_species="", zip_code=""):
    water = water if isinstance(water, dict) else {}
    profile = load_target_profile()
    resolved_target_species, target_species_source = resolve_target_species(target_species, profile)
    lat = water.get("lat")
    lon = water.get("lon")
    has_coords = lat is not None and lon is not None

    if has_coords:
        weather, weather_summary = _weather_summary_for_coords(lat, lon)
    else:
        weather = fallback_weather_payload()
        weather_summary = {
            "temp": round(f_temp(weather["current"]["temperature_2m"]), 1),
            "wind": round(mph(weather["current"]["wind_speed_10m"]), 1),
            "pressure": round(inhg(weather["current"]["pressure_msl"]), 2),
            "cloud": weather["current"].get("cloud_cover", 0),
            "source": "fallback",
            "fallback": True,
            "error": "Waterbody has no coordinates, so fallback weather is shown until it is mapped.",
        }

    temp_f = weather_summary["temp"]
    wind_mph = weather_summary["wind"]
    pressure_inhg = weather_summary["pressure"]
    cloud = weather_summary["cloud"]

    water_type = str(water.get("type") or "water").strip() or "water"
    area_type = water_type.lower()
    base = overall_score(temp_f, wind_mph, pressure_inhg, cloud)
    blocks = time_blocks(base, temp_f, wind_mph)
    best_block = max(blocks, key=lambda x: x["score"]) if blocks else {
        "label": "Any time",
        "time": "Any time",
        "score": base,
    }

    hourly = hourly_bite_forecast(
        weather.get("hourly", {}),
        f_temp,
        mph,
        inhg,
    )
    best_hour = max(hourly, key=lambda x: x["score"]) if hourly else None
    forecast = _build_forecast_rows(weather, pressure_inhg, cloud)

    water_species = [
        str(item).strip()
        for item in (water.get("species") or [])
        if str(item).strip()
    ]
    water_species_keys = {species_key(item) for item in water_species}
    target_species_key = species_key(resolved_target_species) if resolved_target_species else ""
    target_fit = species_fit_bonus(water, resolved_target_species)

    species_ranked = []
    for sp in SPECIES:
        sp_score = score_species(sp, temp_f, wind_mph, pressure_inhg, area_type)
        sp_key = species_key(sp.get("name", ""))
        if target_species_key and sp_key == target_species_key:
            sp_score += 12
        elif water_species_keys and sp_key in water_species_keys:
            sp_score += 8

        species_ranked.append({
            "name": sp["name"],
            "score": sp_score,
            "rating": rating(sp_score),
            "lures": choose_lure(sp["name"]),
            "habitat": ", ".join(sp["habitat"]),
            "fish_image": fish_image(sp["name"]),
        })

    species_ranked.sort(key=lambda x: x["score"], reverse=True)

    if target_species_key:
        for index, item in enumerate(species_ranked):
            if species_key(item.get("name", "")) == target_species_key:
                species_ranked.insert(0, species_ranked.pop(index))
                break
    elif water_species_keys:
        for index, item in enumerate(species_ranked):
            if species_key(item.get("name", "")) in water_species_keys:
                species_ranked.insert(0, species_ranked.pop(index))
                break

    top_lure_cards = []
    for sp in species_ranked[:4]:
        cards = sp["lures"].get("cards", {})
        if cards:
            best_card = cards.get("evening") or cards.get("morning")
            top_lure_cards.append({
                "species": sp["name"],
                "species_score": sp["score"],
                "fish_image": sp["fish_image"],
                "top_pick": True if len(top_lure_cards) == 0 else False,
                **best_card
            })

    best_bet = build_best_bet(
        species_ranked,
        best_block,
        best_hour,
        base,
        temp_f,
        wind_mph,
        pressure_inhg,
        area_type,
        zip_code or "",
    )

    if water.get("city") or water.get("state"):
        location_label = ", ".join(
            part
            for part in (water.get("city"), water.get("state"))
            if part
        )
    else:
        location_label = str(water.get("name") or "Selected waterbody")

    insights = catch_insights(zip_code or "")
    try:
        smart_intelligence = build_smart_intelligence(
            zip_code=zip_code or "",
            location={
                "city": water.get("city", ""),
                "state": water.get("state", ""),
            },
            weather=weather_summary,
            area_type=area_type,
            best_bet=best_bet,
            best_time=best_block,
            catch_insights=insights,
        )
    except Exception as exc:
        smart_intelligence = build_smart_intelligence_fallback(
            zip_code=zip_code or "",
            location={
                "city": water.get("city", ""),
                "state": water.get("state", ""),
            },
            weather=weather_summary,
            area_type=area_type,
            best_bet=best_bet,
            best_time=best_block,
            catch_insights=insights,
            error=str(exc),
        )

    smart_intelligence["location_label"] = location_label

    water_badges = []
    if water.get("manual") or str(water.get("source") or "").lower() == "manual":
        water_badges.append("Manual waterbody")
    if water.get("favorite"):
        water_badges.append("Favorite")
    if water.get("stocked_trout"):
        water_badges.append("Stocked trout")
    if water.get("catch_history_count"):
        water_badges.append(f"Catch history {water.get('catch_history_count')}")
    if has_coords:
        water_badges.append("Mapped")
    else:
        water_badges.append("Unmapped")

    target_fit_score = target_fit.get("score", 0)
    target_fit_label = target_fit.get("label", "Auto")

    enriched_water = dict(water)
    # A focused waterbody does not pass through the Local Waters ranker. Keep
    # the dashboard brief meaningful by exposing its target-fit score here.
    enriched_water["local_score"] = target_fit_score

    return {
        "version": APP_VERSION,
        "generated_at": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "water": enriched_water,
        "target_species": resolved_target_species or "",
        "target_species_source": target_species_source,
        "target_profile": profile,
        "target_fit": target_fit,
        "water_badges": water_badges,
        "water_profile": {
            "location_label": location_label,
            "mapped": has_coords,
            "source": water.get("source") or ("manual" if water.get("manual") else "starter"),
            "manual": bool(water.get("manual") or str(water.get("source") or "").lower() == "manual"),
            "favorite": bool(water.get("favorite")),
            "stocked_trout": bool(water.get("stocked_trout")),
            "catch_history_count": int(water.get("catch_history_count") or 0),
            "target_fit_score": target_fit_score,
            "target_fit_label": target_fit_label,
        },
        "detail_actions": {
            "back_to_map": "/map",
            "smart_picks": "/recommendations",
            "snapshot": f"/snapshot?zip={zip_code}" if zip_code else "/snapshot",
        },
        "selected_species": best_bet["species"],
        "overall": {
            "score": base,
            "rating": rating(base),
        },
        "best_bet": best_bet,
        "weather": weather_summary,
        "area_type": area_type,
        "time_blocks": blocks,
        "hourly": hourly,
        "best_time": best_block,
        "best_hour": best_hour,
        "forecast": forecast,
        "lure_cards": top_lure_cards,
        "species": species_ranked,
        "smart_intelligence": smart_intelligence,
        "catch_insights": insights,
    }


def build_intel(zip_code, target_species=""):
    zip_code = zip_code.strip()
    loc = get_coords(zip_code)

    if not loc:
        return None

    weather, weather_summary = _weather_summary_for_coords(loc["lat"], loc["lon"])
    temp_f = weather_summary["temp"]
    wind_mph = weather_summary["wind"]
    pressure_inhg = weather_summary["pressure"]
    cloud = weather_summary["cloud"]

    waters = detect_water(loc["lat"], loc["lon"])
    area_type = infer_area_type(waters)
    profile = load_target_profile()
    resolved_target_species, target_species_source = resolve_target_species(target_species, profile)

    base = overall_score(temp_f, wind_mph, pressure_inhg, cloud)
    blocks = time_blocks(base, temp_f, wind_mph)
    best_block = max(blocks, key=lambda x: x["score"]) if blocks else {
        "label": "Any time",
        "time": "Any time",
        "score": base,
    }

    hourly = hourly_bite_forecast(
        weather.get("hourly", {}),
        f_temp,
        mph,
        inhg
    )

    best_hour = max(hourly, key=lambda x: x["score"]) if hourly else None

    species_ranked = []
    for sp in SPECIES:
        sp_score = score_species(sp, temp_f, wind_mph, pressure_inhg, area_type)
        sp_key = species_key(sp.get("name", ""))
        if resolved_target_species and sp_key == species_key(resolved_target_species):
            sp_score += 12
        species_ranked.append({
            "name": sp["name"],
            "score": sp_score,
            "rating": rating(sp_score),
            "lures": choose_lure(sp["name"]),
            "habitat": ", ".join(sp["habitat"]),
            "fish_image": fish_image(sp["name"])
        })

    species_ranked.sort(key=lambda x: x["score"], reverse=True)
    if resolved_target_species:
        for index, item in enumerate(species_ranked):
            if species_key(item.get("name", "")) == species_key(resolved_target_species):
                species_ranked.insert(0, species_ranked.pop(index))
                break

    top_lure_cards = []
    for sp in species_ranked[:4]:
        cards = sp["lures"].get("cards", {})
        if cards:
            best_card = cards.get("evening") or cards.get("morning")
            top_lure_cards.append({
                "species": sp["name"],
                "species_score": sp["score"],
                "fish_image": sp["fish_image"],
                "top_pick": True if len(top_lure_cards) == 0 else False,
                **best_card
            })

    best_bet = build_best_bet(
        species_ranked,
        best_block,
        best_hour,
        base,
        temp_f,
        wind_mph,
        pressure_inhg,
        area_type,
        zip_code
    )

    forecast = _build_forecast_rows(weather, pressure_inhg, cloud)

    insights = catch_insights(zip_code)
    try:
        smart_intelligence = build_smart_intelligence(
            zip_code=zip_code,
            location=loc,
            weather=weather_summary,
            area_type=area_type,
            best_bet=best_bet,
            best_time=best_block,
            catch_insights=insights,
        )
    except Exception as exc:
        smart_intelligence = build_smart_intelligence_fallback(
            zip_code=zip_code,
            location=loc,
            weather=weather_summary,
            area_type=area_type,
            best_bet=best_bet,
            best_time=best_block,
            catch_insights=insights,
            error=str(exc),
        )

    return {
        "version": APP_VERSION,
        "generated_at": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "location": loc,
        "weather": weather_summary,
        "overall": {
            "score": base,
            "rating": rating(base)
        },
        "best_bet": best_bet,
        "time_blocks": blocks,
        "hourly": hourly,
        "best_hour": best_hour,
        "best_time": best_block,
        "species": species_ranked,
        "lure_cards": top_lure_cards,
        "waters": waters,
        "area_type": area_type,
        "target_species": resolved_target_species,
        "target_species_source": target_species_source,
        "target_profile": profile,
        "forecast": forecast,
        "catch_insights": insights,
        "smart_intelligence": smart_intelligence
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/map")
def map_dashboard():
    return render_template("map.html")


@app.route("/api/water-intel")
def api_water_intel():
    water_id = str(request.args.get("water_id", "")).strip()
    target_species = str(request.args.get("target_species", "")).strip()
    zip_code = str(request.args.get("zip", "")).strip()

    if not water_id:
        return jsonify({"ok": False, "error": "water_id is required"}), 400

    water = get_water_record_by_id(water_id)
    if not water:
        return jsonify({"ok": False, "error": "Waterbody not found"}), 404

    payload = build_water_intel(water, target_species=target_species, zip_code=zip_code)
    payload["ok"] = True
    return jsonify(payload)


@app.route("/water/<water_id>")
def water_detail(water_id):
    target_species = str(request.args.get("target_species") or request.args.get("species") or "").strip()
    zip_code = str(request.args.get("zip", "")).strip()

    water = get_water_record_by_id(water_id)
    if not water:
        return "<h1>Waterbody not found</h1>", 404

    payload = build_water_intel(water, target_species=target_species, zip_code=zip_code)
    return render_template("water.html", data=payload)


@app.route("/maps")
def maps_alias():
    return redirect("/map", code=308)


@app.route("/snapshot")
def snapshot():
    zip_code = request.args.get("zip", "60543")
    selected_forecast_date = request.args.get("selected_forecast_date") or request.args.get("forecast_date")
    data = build_intel(zip_code)

    if not data:
        return "<h1>Invalid ZIP code</h1>", 400

    return render_template("snapshot.html", data=data, report=build_snapshot_report(data, selected_forecast_date=selected_forecast_date))


@app.route("/api/intel")
def api_intel():
    zip_code = request.args.get("zip", "60543")
    target_species = str(request.args.get("target_species", "")).strip()
    water_id = str(request.args.get("water_id", "")).strip()

    if water_id:
        water = get_water_record_by_id(water_id)
        if not water:
            return jsonify({"error": "Waterbody not found"}), 404

        data = build_water_intel(water, target_species=target_species, zip_code=zip_code)
    else:
        data = build_intel(zip_code, target_species=target_species)

    if not data:
        return jsonify({"error": "Invalid ZIP code"}), 400

    return jsonify(data)


@app.route("/api/target-profile", methods=["GET", "POST"])
def api_target_profile():
    if request.method == "GET":
        return jsonify({
            "ok": True,
            "version": APP_VERSION,
            "profile": load_target_profile(),
            "options": available_target_species(),
        })

    payload = request.get_json(silent=True) or {}
    try:
        profile = save_target_profile(payload)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Could not save target profile: {exc}"}), 500

    return jsonify({
        "ok": True,
        "version": APP_VERSION,
        "profile": profile,
        "options": available_target_species(),
    })


@app.route("/api/favorites", methods=["GET"])
def api_get_favorites():
    return jsonify(load_favorites())


@app.route("/api/favorites", methods=["POST"])
def api_add_favorite():
    payload = request.get_json(force=True)
    name = str(payload.get("name", "")).strip()
    zip_code = str(payload.get("zip", "")).strip()

    if not name or not zip_code:
        return jsonify({"error": "Name and ZIP are required"}), 400

    if not get_coords(zip_code):
        return jsonify({"error": "Invalid ZIP code"}), 400

    favorites = load_favorites()

    favorites = [
        f for f in favorites
        if f.get("zip") != zip_code and f.get("name", "").lower() != name.lower()
    ]

    favorites.append({
        "name": name,
        "zip": zip_code
    })

    save_favorites(favorites)
    return jsonify(favorites)


@app.route("/api/favorites/<zip_code>", methods=["DELETE"])
def api_delete_favorite(zip_code):
    favorites = load_favorites()
    favorites = [f for f in favorites if f.get("zip") != zip_code]
    save_favorites(favorites)
    return jsonify(favorites)


@app.route("/api/catches", methods=["GET"])
def api_get_catches():
    catches = load_catches()
    catches = [_enrich_catch_record(catch) for catch in catches if isinstance(catch, dict)]
    catches.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify(catches)


@app.route("/api/catches", methods=["POST"])
def api_add_catch():
    payload = request.get_json(force=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    gear_refs, gear_labels = _catch_gear_fields(payload if isinstance(payload, dict) else {})

    catch = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        "zip": str(payload.get("zip", "")).strip(),
        "species": str(payload.get("species", "")).strip(),
        "lure": str(payload.get("lure", "")).strip(),
        "waterbody": str(payload.get("waterbody", "")).strip(),
        "notes": str(payload.get("notes", "")).strip(),
        "setup_name": str(payload.get("setup_name", "")).strip(),
        "gear_refs": gear_refs,
        "gear_labels": gear_labels,
    }

    if not catch["species"]:
        return jsonify({"error": "Species is required"}), 400

    catches = load_catches()
    catches.append(catch)
    save_catches(catches)

    try:
        used_at = catch.get("timestamp")
        for ref in set(gear_refs.values()):
            record_gear_item_usage(ref, used_at=used_at, trips=1, catches=1)
    except Exception:
        pass

    return jsonify(_enrich_catch_record(catch))


@app.route("/api/catches/<catch_id>", methods=["DELETE"])
def api_delete_catch(catch_id):
    catches = load_catches()
    catches = [c for c in catches if c.get("id") != catch_id]
    save_catches(catches)
    return jsonify(catches)


@app.route("/api/waters/custom", methods=["POST"])
def api_add_custom_water():
    payload = request.get_json(silent=True) or {}

    try:
        water = append_custom_water_record(payload)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Could not save waterbody: {exc}"}), 500

    catalog = load_water_catalog()

    return jsonify({
        "ok": True,
        "version": APP_VERSION,
        "water": water,
        "custom_count": catalog.get("custom_count", 0),
        "total_waters": catalog.get("total_count", 0),
        "database": {
            "path": catalog.get("source_path"),
            "custom_path": catalog.get("custom_source_path"),
        },
    }), 201


@app.route("/health")
def health():
    return {
        "status": "ok",
        "version": APP_VERSION
    }


@app.route("/api/map-data")
def api_map_data():
    """Read-only map data endpoint for staged map dashboard work."""
    target_species = str(request.args.get("target_species", "")).strip()
    profile = load_target_profile()
    resolved_target_species, target_species_source = resolve_target_species(target_species, profile)
    readiness = get_map_data_readiness()
    waters = []
    for water in readiness.get("records", []):
        item = dict(water)
        item["target_fit"] = species_fit_bonus(item, resolved_target_species)
        waters.append(item)

    top_waters = sorted(
        waters,
        key=lambda item: (
            int(item.get("target_fit", {}).get("score", 0) or 0),
            int(item.get("catch_history_count", 0) or 0),
        ),
        reverse=True,
    )[:10]

    return jsonify({
        "ok": bool(readiness.get("ok")),
        "version": readiness.get("version"),
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
        "record_count": readiness.get("record_count", 0),
        "base_count": readiness.get("base_count", 0),
        "custom_count": readiness.get("custom_count", 0),
        "manual_waterbody_entry_enabled": readiness.get("manual_waterbody_entry_enabled", True),
        "bounds": readiness.get("bounds"),
        "warnings": readiness.get("warnings", []),
        "source_path": readiness.get("source_path"),
        "custom_source_path": readiness.get("custom_source_path"),
        "target_species": resolved_target_species,
        "target_species_source": target_species_source,
        "target_profile": profile,
        "target_ranking_enabled": bool(resolved_target_species),
        "top_waters": top_waters,
        "waters": waters,
    })


if __name__ == "__main__":
    print(f"Starting Angler Intel {APP_RELEASE}...")
    app.run(host="0.0.0.0", port=5000)


def app_health_sqlite_status():
    """Small read-only SQLite status payload for App Health."""
    try:
        return get_sqlite_health_for_app()
    except Exception as exc:
        return {
            "ok": False,
            "available": False,
            "summary": "SQLite status unavailable",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation",
            "errors": [str(exc)],
        }


def app_health_backup_status():
    """Small read-only backup status payload for App Health."""
    try:
        return get_backup_health_for_app()
    except Exception as exc:
        return {
            "ok": False,
            "available": False,
            "summary": "Backup status unavailable",
            "errors": [str(exc)],
            "json_source_of_truth": True,
        }


def app_health_version_status():
    """Small read-only version ledger payload for App Health."""
    try:
        return get_version_health_for_app()
    except Exception as exc:
        return {
            "ok": False,
            "summary": "Version ledger unavailable",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation",
            "errors": [str(exc)],
        }


def app_health_intelligence_status():
    """Small read-only Smart Intelligence readiness payload for App Health."""
    try:
        return get_smart_intelligence_health_for_app()
    except Exception as exc:
        return {
            "ok": False,
            "summary": "Smart Intelligence readiness unavailable",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation",
            "errors": [str(exc)],
        }


def app_health_sqlite_transition_status():
    """Small read-only SQLite authority transition payload for App Health."""
    try:
        return get_sqlite_transition_health_for_app()
    except Exception as exc:
        return {
            "ok": False,
            "summary": "SQLite transition readiness unavailable",
            "json_source_of_truth": True,
            "current_authority": "json",
            "sqlite_role": "mirror/read-only foundation",
            "errors": [str(exc)],
        }


def app_health_map_data_status():
    """Small read-only map data readiness payload for App Health."""
    try:
        return get_map_data_health_for_app()
    except Exception as exc:
        return {
            "ok": False,
            "summary": "Map data readiness unavailable",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation",
            "errors": [str(exc)],
        }
