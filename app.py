from flask import Flask, request, jsonify, render_template
import json
from pathlib import Path
from datetime import datetime, timedelta
import uuid
from collections import Counter

from intelligence.location import get_coords
from intelligence.weather import get_weather, f_temp, mph, inhg
from intelligence.waters import detect_water, infer_area_type
from intelligence.species import SPECIES, score_species
from intelligence.lures import choose_lure
from intelligence.scoring import overall_score, time_blocks, rating, hourly_bite_forecast
from intelligence.smart_intelligence import build_smart_intelligence
from intelligence.app_health_sqlite import get_sqlite_health_for_app
from intelligence.app_health_backup import get_backup_health_for_app
from intelligence.app_health_versions import get_version_health_for_app
from intelligence.app_health_intelligence import get_smart_intelligence_health_for_app

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


APP_VERSION = "v4.6.1-smart-intelligence-hardening"

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


def slugify_species(name):
    return (
        name.lower()
        .replace("/", " ")
        .replace("-", " ")
        .replace(" ", "_")
    )


def fish_image(name):
    return f"/static/fish/{slugify_species(name)}.svg"


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

    if not catches:
        return {
            "total": 0,
            "local_total": 0,
            "top_species": [],
            "top_lures": [],
            "message": "No catches logged yet. Once you log catches, Angler Intel will start showing your personal patterns."
        }

    local = [c for c in catches if c.get("zip") == zip_code]

    species_counts = Counter(
        c.get("species", "Unknown")
        for c in catches
        if c.get("species")
    )

    lure_counts = Counter(
        c.get("lure", "Unknown")
        for c in catches
        if c.get("lure")
    )

    local_species_counts = Counter(
        c.get("species", "Unknown")
        for c in local
        if c.get("species")
    )

    return {
        "total": len(catches),
        "local_total": len(local),
        "top_species": [
            {"name": name, "count": count}
            for name, count in species_counts.most_common(5)
        ],
        "top_lures": [
            {"name": name, "count": count}
            for name, count in lure_counts.most_common(5)
        ],
        "local_top_species": [
            {"name": name, "count": count}
            for name, count in local_species_counts.most_common(3)
        ],
        "message": "Personal catch history is active."
    }


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
    top = species_ranked[0]

    cards = top["lures"].get("cards", {})
    best_lure = None

    if cards:
        if best_time["label"] == "Morning":
            best_lure = cards.get("morning")
        elif best_time["label"] == "Midday":
            best_lure = cards.get("midday")
        else:
            best_lure = cards.get("evening")

    if not best_lure:
        best_lure = {
            "name": top["lures"].get("evening", "Spinnerbait"),
            "image": "/static/lures/spinnerbait.svg",
            "speed": "Medium speed",
            "size": "3/8 oz",
            "colors": ["White", "Chartreuse"],
            "why": "Best general recommendation based on current species and bite window."
        }

    reasons = []

    if base_score >= 80:
        reasons.append("Overall conditions are excellent.")
    elif base_score >= 65:
        reasons.append("Overall conditions are good.")
    else:
        reasons.append("Conditions are workable, but fish may be selective.")

    if 5 <= wind_mph <= 15:
        reasons.append("Wind is in the productive range for shallow feeding activity.")
    elif wind_mph > 20:
        reasons.append("Wind is high, so protected banks and heavier presentations are better.")

    if pressure_inhg < 29.9:
        reasons.append("Lower pressure can encourage feeding movement.")
    elif pressure_inhg > 30.25:
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
        if c.get("zip") == zip_code and c.get("species") == top["name"]
    ]

    if matching:
        reasons.append(f"Your catch log already has {len(matching)} local catch record(s) for {top['name']}.")

    return {
        "species": top["name"],
        "species_score": top["score"],
        "fish_image": top["fish_image"],
        "time_label": best_time["label"],
        "time_range": best_time["time"],
        "best_hour": format_hour_label(best_hour["hour"]) if best_hour else None,
        "lure_name": best_lure["name"],
        "lure_image": best_lure["image"],
        "speed": best_lure["speed"],
        "size": best_lure["size"],
        "colors": best_lure["colors"],
        "why": best_lure["why"],
        "reasons": reasons
    }


def build_intel(zip_code):
    zip_code = zip_code.strip()
    loc = get_coords(zip_code)

    if not loc:
        return None

    weather_error = None
    try:
        weather = get_weather(loc["lat"], loc["lon"])
        weather["source"] = weather.get("source", "open-meteo")
        weather["fallback"] = False
    except Exception as exc:
        weather_error = str(exc)
        weather = fallback_weather_payload()

    current = weather["current"]

    temp_f = f_temp(current["temperature_2m"])
    wind_mph = mph(current["wind_speed_10m"])
    pressure_inhg = inhg(current["pressure_msl"])
    cloud = current.get("cloud_cover", 0)

    waters = detect_water(loc["lat"], loc["lon"])
    area_type = infer_area_type(waters)

    base = overall_score(temp_f, wind_mph, pressure_inhg, cloud)
    blocks = time_blocks(base, temp_f, wind_mph)
    best_block = max(blocks, key=lambda x: x["score"])

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
        species_ranked.append({
            "name": sp["name"],
            "score": sp_score,
            "rating": rating(sp_score),
            "lures": choose_lure(sp["name"]),
            "habitat": ", ".join(sp["habitat"]),
            "fish_image": fish_image(sp["name"])
        })

    species_ranked.sort(key=lambda x: x["score"], reverse=True)

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

    daily = weather.get("daily", {})
    forecast = []

    for i, date in enumerate(daily.get("time", [])[:7]):
        max_f = f_temp(daily["temperature_2m_max"][i])
        min_f = f_temp(daily["temperature_2m_min"][i])
        avg_f = (max_f + min_f) / 2
        max_wind = mph(daily["wind_speed_10m_max"][i])
        day_score = overall_score(avg_f, max_wind, pressure_inhg, cloud)

        forecast.append({
            "date": date,
            "score": day_score,
            "rating": rating(day_score),
            "high": round(max_f),
            "low": round(min_f),
            "wind": round(max_wind)
        })

    weather_summary = {
        "temp": round(temp_f, 1),
        "wind": round(wind_mph, 1),
        "pressure": round(pressure_inhg, 2),
        "cloud": cloud,
        "source": weather.get("source", "unknown"),
        "fallback": bool(weather.get("fallback")),
        "error": weather_error,
    }
    insights = catch_insights(zip_code)
    smart_intelligence = build_smart_intelligence(
        zip_code=zip_code,
        location=loc,
        weather=weather_summary,
        area_type=area_type,
        best_bet=best_bet,
        best_time=best_block,
        catch_insights=insights,
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
        "forecast": forecast,
        "catch_insights": insights,
        "smart_intelligence": smart_intelligence
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/snapshot")
def snapshot():
    zip_code = request.args.get("zip", "60543")
    data = build_intel(zip_code)

    if not data:
        return "<h1>Invalid ZIP code</h1>", 400

    return render_template("snapshot.html", data=data)


@app.route("/api/intel")
def api_intel():
    zip_code = request.args.get("zip", "60543")
    data = build_intel(zip_code)

    if not data:
        return jsonify({"error": "Invalid ZIP code"}), 400

    return jsonify(data)


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
    catches.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify(catches)


@app.route("/api/catches", methods=["POST"])
def api_add_catch():
    payload = request.get_json(force=True)

    catch = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        "zip": str(payload.get("zip", "")).strip(),
        "species": str(payload.get("species", "")).strip(),
        "lure": str(payload.get("lure", "")).strip(),
        "notes": str(payload.get("notes", "")).strip()
    }

    if not catch["species"]:
        return jsonify({"error": "Species is required"}), 400

    catches = load_catches()
    catches.append(catch)
    save_catches(catches)

    return jsonify(catch)


@app.route("/api/catches/<catch_id>", methods=["DELETE"])
def api_delete_catch(catch_id):
    catches = load_catches()
    catches = [c for c in catches if c.get("id") != catch_id]
    save_catches(catches)
    return jsonify(catches)


@app.route("/health")
def health():
    return {
        "status": "ok",
        "version": APP_VERSION
    }


if __name__ == "__main__":
    print(f"Starting Angler Intel {APP_VERSION}...")
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
