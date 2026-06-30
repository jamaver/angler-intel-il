from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

from flask import current_app, jsonify, render_template_string, request

from intelligence.water_registry import load_water_catalog, load_water_records


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
WATERS_PATH = DATA_DIR / "illinois_waters.json"
DEFAULT_APP_VERSION = "v4.9.2-map-context-custom-waterbodies"


def _current_app_version() -> str:
    try:
        version = current_app.config.get("APP_VERSION")
        if version:
            return str(version)
    except Exception:
        pass
    return DEFAULT_APP_VERSION


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


def _waters() -> list[dict[str, Any]]:
    return load_water_records()


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_miles = 3958.8

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radius_miles * c


def _normalize_coords(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None

    if isinstance(value, dict):
        lat = value.get("lat") or value.get("latitude")
        lon = value.get("lon") or value.get("lng") or value.get("longitude")
        if lat is not None and lon is not None:
            return float(lat), float(lon)

    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return float(value[0]), float(value[1])

    return None


def _coords_from_zip(zip_code: str) -> tuple[float, float] | None:
    zip_code = (zip_code or "").strip()
    if not zip_code:
        return None

    try:
        from intelligence.location import get_coords
        result = get_coords(zip_code)
        return _normalize_coords(result)
    except Exception:
        return None


def _score_water(water: dict[str, Any], species: str = "") -> int:
    score = 50

    wtype = str(water.get("type", "")).lower()
    if wtype in ("river", "lake", "reservoir", "great lake"):
        score += 5

    access = water.get("access") or []
    if isinstance(access, list):
        if "shore" in access:
            score += 8
        if "boat" in access or "small craft" in access:
            score += 5

    species_query = species.strip().lower()
    water_species = [str(x).lower() for x in water.get("species", []) if x]
    if species_query:
        for item in water_species:
            if species_query in item or item in species_query:
                score += 25
                break

    if water.get("notes"):
        score += 3

    return min(score, 100)


def _filter_rank_waters(
    zip_code: str = "",
    radius: float = 35.0,
    species: str = "",
    q: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    catalog = load_water_catalog()
    waters = catalog["records"]
    coords = _coords_from_zip(zip_code)

    q_l = q.strip().lower()
    species_l = species.strip().lower()

    results = []

    for water in waters:
        lat = water.get("lat")
        lon = water.get("lon")

        if lat is None or lon is None:
            continue

        distance = None
        if coords:
            distance = _haversine_miles(coords[0], coords[1], float(lat), float(lon))
            if distance > radius:
                continue

        searchable = " ".join([
            str(water.get("name", "")),
            str(water.get("city", "")),
            str(water.get("county", "")),
            str(water.get("type", "")),
            " ".join(map(str, water.get("species", []))),
            " ".join(map(str, water.get("habitat", []))),
            str(water.get("notes", "")),
        ]).lower()

        if q_l and q_l not in searchable:
            continue

        if species_l:
            species_list = " ".join(map(str, water.get("species", []))).lower()
            if species_l not in species_list:
                continue

        item = dict(water)
        item["distance_miles"] = round(distance, 1) if distance is not None else None
        item["local_score"] = _score_water(water, species=species)
        item["source"] = "local-waters"

        results.append(item)

    results.sort(
        key=lambda x: (
            x["distance_miles"] if x["distance_miles"] is not None else 9999,
            -x["local_score"],
            x.get("name", ""),
        )
    )

    return {
        "ok": True,
        "version": _current_app_version(),
        "source": "local-starter-and-custom-waters",
        "zip": zip_code,
        "origin": {"lat": coords[0], "lon": coords[1]} if coords else None,
        "radius_miles": radius,
        "species_filter": species,
        "query": q,
        "count": len(results[:limit]),
        "total_matches": len(results),
        "waters": results[:limit],
        "database": {
            "path": catalog.get("source_path"),
            "custom_path": catalog.get("custom_source_path"),
            "total_waters": len(waters),
            "base_waters": catalog.get("base_count", 0),
            "custom_waters": catalog.get("custom_count", 0),
        },
    }


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _render_waters_page() -> str:
    return render_template_string("""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Angler Intel - Local Waters</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 2rem;
      max-width: 1100px;
      line-height: 1.45;
      color: #172018;
    }
    .card {
      border: 1px solid #ddd;
      border-radius: 12px;
      padding: 1rem;
      margin: 1rem 0;
      background: #fff;
    }
    input, button, select {
      font-size: 1rem;
      padding: 0.5rem;
      margin: 0.2rem 0;
    }
    input {
      width: 100%;
      max-width: 420px;
    }
    button {
      border-radius: 8px;
      border: 1px solid #bbb;
      cursor: pointer;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 1rem;
    }
    .water {
      border: 1px solid #eee;
      border-radius: 12px;
      padding: 1rem;
      background: #fafafa;
    }
    .muted { color: #666; }
    .tag {
      display: inline-block;
      padding: 0.15rem 0.4rem;
      margin: 0.12rem;
      border-radius: 999px;
      background: #e9f8ee;
      border: 1px solid #b9ddc5;
      font-size: 0.85rem;
    }
    pre {
      background: #f5f5f5;
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      white-space: pre-wrap;
    }
    a { color: #0b5d2a; }
  </style>
  <link rel="stylesheet" href="/static/css/style.css">
</head>
<body class="local-waters-page">
  <nav class="ai-main-tabs" aria-label="Angler Intel navigation">
  <a class="ai-main-tab" href="/">Dashboard</a>
  <a class="ai-main-tab active" href="/waters">Local Waters</a>
  <a class="ai-main-tab" href="/reports">Saved Reports</a>
  <a class="ai-main-tab" href="/app-health">App Health</a>
</nav>
  <h1>Local Waters</h1>
  <p class="muted release-line">Current release: {{ app_version }}</p>
  <p class="muted">Local waters now uses the starter database plus any manually added waters, with broader ZIP-based detection available alongside it.</p>

  <div class="card">
    <h2>Search waters</h2>
    <label>ZIP<br><input id="zipInput" value="60543" placeholder="60543"></label><br>
    <label>Radius miles<br><input id="radiusInput" value="35" placeholder="35"></label><br>
    <label>Species filter<br><input id="speciesInput" placeholder="bass, walleye, crappie, catfish"></label><br>
    <label>Keyword<br><input id="queryInput" placeholder="river, lake, county, city, habitat"></label><br>
    <button onclick="loadWaters()">Search local waters</button>
    <button onclick="loadAllWaters()">Show all waters</button>
  </div>

  <div class="card waters-results-card">
    <h2>Results</h2>
    <div id="summary" class="muted">Search to load waters.</div>
    <div id="results" class="grid"></div>
  </div>

  <details class="card">
    <summary>Raw API output</summary>
    <pre id="rawBox">No data loaded yet.</pre>
  </details>

  <p>
    <a href="/">Dashboard</a> |
    <a href="/app-health">App Health</a>
  </p>

<script>
async function loadWaters() {
  const zip = document.getElementById("zipInput").value.trim();
  const radius = document.getElementById("radiusInput").value.trim() || "35";
  const species = document.getElementById("speciesInput").value.trim();
  const q = document.getElementById("queryInput").value.trim();

  const params = new URLSearchParams({zip, radius});
  if (species) params.set("species", species);
  if (q) params.set("q", q);

  await fetchAndRender("/api/waters?" + params.toString());
}

async function loadAllWaters() {
  await fetchAndRender("/api/waters/all");
}

async function fetchAndRender(url) {
  const summary = document.getElementById("summary");
  const results = document.getElementById("results");
  const raw = document.getElementById("rawBox");

  summary.textContent = "Loading...";
  results.innerHTML = "";

  try {
    const res = await fetch(url);
    const data = await res.json();
    raw.textContent = JSON.stringify(data, null, 2);

    const waters = data.waters || [];
    summary.textContent = `${waters.length} shown · ${data.database?.total_waters ?? "?"} waters in local catalog`;

    if (!waters.length) {
      results.innerHTML = "<p class='muted'>No local waters matched. Try a larger radius or no species filter.</p>";
      return;
    }

    results.innerHTML = waters.map(w => `
      <div class="water">
        <h3 class="water-title">${esc(w.name)}</h3>
        <p class="muted">
          ${esc(w.type || "")} · ${esc(w.city || "")} · ${esc(w.county || "")}
          ${w.distance_miles !== null && w.distance_miles !== undefined ? " · " + esc(w.distance_miles) + " mi" : ""}
        </p>
        <p><strong>Score:</strong> ${esc(w.local_score ?? "")}</p>
        ${(w.manual || String(w.source || "").toLowerCase() === "manual" || w.favorite || w.stocked_trout || w.catch_history_count)
          ? `<p>${[
              w.manual || String(w.source || "").toLowerCase() === "manual" ? "<span class='tag tag-manual'>Manual</span>" : "",
              w.favorite ? "<span class='tag tag-favorite'>Favorite</span>" : "",
              w.stocked_trout ? "<span class='tag tag-trout'>Stocked trout</span>" : "",
              w.catch_history_count ? "<span class='tag tag-history'>Catch history</span>" : ""
            ].join("")}</p>`
          : ""}
        <p>${(w.species || []).map(s => `<span class="tag">${esc(s)}</span>`).join("")}</p>
        <p><strong>Habitat:</strong> ${(w.habitat || []).map(esc).join(", ")}</p>
        <p>${esc(w.notes || "")}</p>
        <p><a href="/water/${encodeURIComponent(w.id)}">View detail</a></p>
      </div>
    `).join("");
  } catch (err) {
    summary.textContent = "Unable to load local waters: " + err;
  }
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadWaters();
</script>
  <script src="/static/js/global_nav_v433.js"></script>
  <script src="/static/js/ui_polish_v442.js"></script>
</body>
</html>
""", app_version=_current_app_version())


def _render_water_detail(water: dict[str, Any]) -> str:
    species = "".join(f"<span class='tag'>{_esc(x)}</span>" for x in water.get("species", []))
    access = "".join(f"<span class='tag'>{_esc(x)}</span>" for x in water.get("access", []))
    habitat = "".join(f"<span class='tag'>{_esc(x)}</span>" for x in water.get("habitat", []))
    meta_tags = []
    if water.get("manual") or str(water.get("source") or "").lower() == "manual":
        meta_tags.append("<span class='tag tag-manual'>Manual waterbody</span>")
    if water.get("favorite"):
        meta_tags.append("<span class='tag tag-favorite'>Favorite</span>")
    if water.get("stocked_trout"):
        meta_tags.append("<span class='tag tag-trout'>Stocked trout</span>")
    if water.get("catch_history_count"):
        meta_tags.append(f"<span class='tag tag-history'>Catch history {int(water.get('catch_history_count') or 0)}</span>")
    if water.get("confidence"):
        meta_tags.append(f"<span class='tag tag-confidence'>{_esc(water.get('confidence'))}</span>")
    if water.get("source"):
        meta_tags.append(f"<span class='tag tag-source'>{_esc(water.get('source'))}</span>")
    raw = json.dumps(water, indent=2, ensure_ascii=False)

    return render_template_string("""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{ water_name }} - Angler Intel</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 2rem;
      max-width: 900px;
      line-height: 1.45;
      color: #172018;
    }
    .card {
      border: 1px solid #ddd;
      border-radius: 12px;
      padding: 1rem;
      margin: 1rem 0;
    }
    .tag {
      display: inline-block;
      padding: 0.15rem 0.4rem;
      margin: 0.12rem;
      border-radius: 999px;
      background: #e9f8ee;
      border: 1px solid #b9ddc5;
      font-size: 0.85rem;
    }
    .muted { color: #666; }
    pre {
      background: #f5f5f5;
      padding: 1rem;
      border-radius: 8px;
      white-space: pre-wrap;
      overflow-x: auto;
    }
    a { color: #0b5d2a; }
  </style>
</head>
<body class="local-waters-page">
  <h1>{{ water_name }}</h1>
  <p class="muted release-line">Current release: {{ app_version }}</p>
  <p class="muted">{{ water_type }} · {{ water_city }} · {{ water_county }}</p>

  <div class="card">
    <h2>Map Tags</h2>
    <p>{{ meta_html | safe }}</p>
    <p class="muted">Lat {{ water_lat }}, Lon {{ water_lon }}</p>
  </div>

  <div class="card">
    <h2>Species</h2>
    <p>{{ species_html | safe }}</p>
  </div>

  <div class="card">
    <h2>Access</h2>
    <p>{{ access_html | safe }}</p>
  </div>

  <div class="card">
    <h2>Habitat</h2>
    <p>{{ habitat_html | safe }}</p>
  </div>

  <div class="card">
    <h2>Notes</h2>
    <p>{{ notes }}</p>
  </div>

  <details class="card">
    <summary>Raw local water record</summary>
    <pre>{{ raw }}</pre>
  </details>

  <p>
    <a href="/waters">Back to local waters</a> |
    <a href="/">Dashboard</a>
  </p>
</body>
</html>
""",
        water_name=water.get("name") or "",
        water_type=water.get("type") or "",
        water_city=water.get("city") or "",
        water_county=water.get("county") or "",
        species_html=species or "No species listed.",
        access_html=access or "No access data listed.",
        habitat_html=habitat or "No habitat data listed.",
        meta_html="".join(meta_tags) or "No extra flags.",
        water_lat=water.get("lat"),
        water_lon=water.get("lon"),
        notes=water.get("notes") or "",
        raw=raw,
        app_version=_current_app_version(),
    )


def register_local_waters_routes_v40(app):
    @app.route("/waters")
    def local_waters_page_v40():
        return _render_waters_page()

    @app.route("/api/waters")
    def local_waters_api_v40():
        zip_code = request.args.get("zip", "").strip()
        species = request.args.get("species", "").strip()
        q = request.args.get("q", "").strip()

        try:
            radius = float(request.args.get("radius", "35"))
        except Exception:
            radius = 35.0

        try:
            limit = int(request.args.get("limit", "20"))
        except Exception:
            limit = 20

        radius = max(1.0, min(radius, 250.0))
        limit = max(1, min(limit, 100))

        return jsonify(_filter_rank_waters(
            zip_code=zip_code,
            radius=radius,
            species=species,
            q=q,
            limit=limit,
        ))

    @app.route("/api/waters/all")
    def local_waters_all_api_v40():
        catalog = load_water_catalog()
        raw_waters = catalog["records"]
        waters = []
        for water in raw_waters:
            item = dict(water)
            item["distance_miles"] = None
            item["local_score"] = _score_water(water)
            item["source"] = "local-waters"
            waters.append(item)

        waters.sort(key=lambda x: (x.get("county", ""), x.get("name", "")))

        return jsonify({
            "ok": True,
            "version": _current_app_version(),
            "source": "local-starter-and-custom-waters",
            "count": len(waters),
            "waters": waters,
            "database": {
                "path": catalog.get("source_path"),
                "custom_path": catalog.get("custom_source_path"),
                "total_waters": len(waters),
                "base_waters": catalog.get("base_count", 0),
                "custom_waters": catalog.get("custom_count", 0),
            },
        })

    @app.route("/api/water/<water_id>")
    def local_water_detail_api_v40(water_id: str):
        for water in load_water_records():
            if water.get("id") == water_id:
                return jsonify({
                    "ok": True,
                    "version": _current_app_version(),
                    "water": water,
                })

        return jsonify({
            "ok": False,
            "error": "Local water not found",
            "id": water_id,
        }), 404

    @app.route("/water/<water_id>")
    def local_water_detail_page_v40(water_id: str):
        for water in load_water_records():
            if water.get("id") == water_id:
                return _render_water_detail(water)

        return "<h1>Water not found</h1><p><a href='/waters'>Back to local waters</a></p>", 404

    @app.route("/api/waters/status")
    def local_waters_status_v40():
        catalog = load_water_catalog()
        waters = catalog["records"]
        counties = sorted({str(w.get("county", "")).strip() for w in waters if w.get("county")})
        types = sorted({str(w.get("type", "")).strip() for w in waters if w.get("type")})

        return jsonify({
            "ok": True,
            "version": _current_app_version(),
            "database": {
                "path": catalog.get("source_path"),
                "custom_path": catalog.get("custom_source_path"),
                "exists": (BASE_DIR / str(catalog.get("source_path") or "")).exists(),
                "total_waters": len(waters),
                "counties": counties,
                "types": types,
            },
            "routes": [
                "/waters",
                "/api/waters",
                "/api/waters/all",
                "/api/waters/status",
                "/api/water/<id>",
                "/water/<id>",
            ],
        })
