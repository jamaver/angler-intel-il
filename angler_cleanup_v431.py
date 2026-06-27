from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import jsonify, request


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SPECIES_PATH = DATA_DIR / "species_profiles_v43.json"
SETTINGS_PATH = DATA_DIR / "species_settings_v431.json"
VERSION_PATH = DATA_DIR / "app_version.json"

COMMON_SPECIES = [
    "largemouth-bass",
    "smallmouth-bass",
    "bluegill",
    "crappie",
    "channel-catfish",
    "walleye",
    "northern-pike",
    "rainbow-trout",
    "brown-trout",
    "yellow-perch",
    "white-bass",
    "common-carp",
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _species() -> list[dict[str, Any]]:
    data = _read_json(SPECIES_PATH, [])
    return data if isinstance(data, list) else []


def _settings() -> dict[str, Any]:
    species_ids = {item.get("id") for item in _species() if isinstance(item, dict)}
    data = _read_json(SETTINGS_PATH, {})

    if not isinstance(data, dict):
        data = {}

    active = data.get("active_species")
    if not isinstance(active, list):
        active = [sid for sid in COMMON_SPECIES if sid in species_ids]

    active = [sid for sid in active if sid in species_ids]

    common = data.get("common_species")
    if not isinstance(common, list):
        common = [sid for sid in COMMON_SPECIES if sid in species_ids]

    optional = data.get("optional_species")
    if not isinstance(optional, list):
        optional = [
            item.get("id")
            for item in _species()
            if isinstance(item, dict)
            and item.get("id") not in common
        ]

    return {
        "version": "v4.3.1",
        "updated": data.get("updated") or _now(),
        "active_species": active,
        "common_species": common,
        "optional_species": optional,
    }


def _save_settings(settings: dict[str, Any]) -> None:
    settings["version"] = "v4.3.1"
    settings["updated"] = _now()
    _write_json(SETTINGS_PATH, settings)


def _species_by_id() -> dict[str, dict[str, Any]]:
    return {
        item["id"]: item
        for item in _species()
        if isinstance(item, dict) and item.get("id")
    }


def _with_enabled_flags(items: list[dict[str, Any]], active: set[str]) -> list[dict[str, Any]]:
    out = []
    for item in items:
        copy = dict(item)
        copy["enabled"] = copy.get("id") in active
        copy["tier"] = "common" if copy.get("id") in COMMON_SPECIES else copy.get("tier", "optional")
        out.append(copy)
    return out


def _validate_data() -> dict[str, Any]:
    try:
        import sys
        tools_dir = BASE_DIR / "tools"
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))
        from validate_data import validate
        return validate()
    except Exception as exc:
        return {
            "ok": False,
            "issues": [f"Unable to run validator: {exc}"],
            "warnings": [],
        }


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _nav() -> str:
    return """<nav class="ai-main-tabs" aria-label="Angler Intel navigation">
  <a class="ai-main-tab" href="/">Dashboard</a>
  <a class="ai-main-tab" href="/waters">Local Waters</a>
  <a class="ai-main-tab" href="/species">Species</a>
  <a class="ai-main-tab" href="/rigs">Rig Setups</a>
  <a class="ai-main-tab" href="/reports">Saved Reports</a>
  <a class="ai-main-tab active" href="/data-tools">Data Tools</a>
  <a class="ai-main-tab" href="/app-health">App Health</a>
  <a class="ai-main-tab" href="/admin">Admin</a>
  <a class="ai-main-tab" href="/exports">Export</a>
</nav>"""


def _data_tools_page() -> str:
    version = _read_json(VERSION_PATH, {})
    validation = _validate_data()

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Angler Intel IL - Data Tools</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/css/style.css">
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 2rem;
      max-width: 1100px;
      line-height: 1.45;
      background: #0b1710;
      color: #f4fff6;
    }}
    .card {{
      border: 1px solid rgba(166, 232, 182, 0.35);
      border-radius: 12px;
      padding: 1rem;
      margin: 1rem 0;
      background: #f8fff9;
      color: #102417;
    }}
    button, select {{
      font-size: 1rem;
      padding: 0.5rem;
      border-radius: 8px;
      border: 1px solid #5fa66f;
      background: #e9f8ee;
      color: #102417;
      font-weight: 800;
      cursor: pointer;
    }}
    pre {{
      background: #102417;
      color: #f4fff6;
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      white-space: pre-wrap;
    }}
    .ok {{ color: #1f8f45; font-weight: 800; }}
    .bad {{ color: #9b1c1c; font-weight: 800; }}
  </style>
</head>
<body>
  {_nav()}

  <h1>Data Tools</h1>
  <p>v4.3.1 cleanup tools for species, rigs, local waters, and future recommendation logic.</p>

  <div class="card">
    <h2>Project Version</h2>
    <pre>{_esc(json.dumps(version, indent=2, ensure_ascii=False))}</pre>
  </div>

  <div class="card">
    <h2>Data Validation</h2>
    <p>Status: <span class="{'ok' if validation.get('ok') else 'bad'}">{'OK' if validation.get('ok') else 'Needs attention'}</span></p>
    <button onclick="runValidation()">Run validation</button>
    <pre id="validationBox">{_esc(json.dumps(validation, indent=2, ensure_ascii=False))}</pre>
  </div>

  <div class="card">
    <h2>Species Controls</h2>
    <p>Common freshwater species are active by default. Optional species can be enabled here or on the Species page.</p>
    <button onclick="loadSpecies()">Refresh species</button>
    <button onclick="resetSpecies()">Reset common defaults</button>
    <div id="speciesBox">Loading...</div>
  </div>

<script>
async function api(url, options = {{}}) {{
  const res = await fetch(url, options);
  const text = await res.text();
  try {{ return JSON.parse(text); }} catch {{ return {{ok: res.ok, text}}; }}
}}

function esc(s) {{
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}}

async function runValidation() {{
  const box = document.getElementById("validationBox");
  box.textContent = "Running...";
  const data = await api("/api/data/validate");
  box.textContent = JSON.stringify(data, null, 2);
}}

async function loadSpecies() {{
  const box = document.getElementById("speciesBox");
  box.textContent = "Loading...";
  const active = await api("/api/species/active");
  const optional = await api("/api/species/optional");

  const activeRows = (active.species || []).map(s => `
    <div>
      <strong>${{esc(s.name)}}</strong>
      <button onclick="disableSpecies('${{esc(s.id)}}')">Disable</button>
    </div>
  `).join("");

  const optionalRows = (optional.species || []).map(s => `
    <div>
      <strong>${{esc(s.name)}}</strong>
      <button onclick="enableSpecies('${{esc(s.id)}}')">Enable</button>
    </div>
  `).join("");

  box.innerHTML = `
    <h3>Active Species</h3>
    ${{activeRows || "<p>No active species.</p>"}}
    <h3>Optional Species</h3>
    ${{optionalRows || "<p>No optional species available.</p>"}}
  `;
}}

async function enableSpecies(id) {{
  await api("/api/species/enable", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify({{id}})
  }});
  loadSpecies();
}}

async function disableSpecies(id) {{
  await api("/api/species/disable", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify({{id}})
  }});
  loadSpecies();
}}

async function resetSpecies() {{
  if (!confirm("Reset active species to common freshwater defaults?")) return;
  await api("/api/species/reset", {{method: "POST"}});
  loadSpecies();
}}

loadSpecies();
</script>
</body>
</html>
"""


def register_cleanup_routes_v431(app):
    @app.route("/api/version")
    def version_api_v431():
        version = _read_json(VERSION_PATH, {})
        return jsonify({
            "ok": True,
            "version": version,
        })

    @app.route("/api/data/validate")
    def validate_api_v431():
        return jsonify(_validate_data())

    @app.route("/data-tools")
    def data_tools_page_v431():
        return _data_tools_page()

    @app.route("/api/species/active")
    def active_species_api_v431():
        settings = _settings()
        by_id = _species_by_id()
        active_ids = settings["active_species"]

        return jsonify({
            "ok": True,
            "version": "v4.3.1",
            "count": len(active_ids),
            "active_species": active_ids,
            "species": [by_id[sid] for sid in active_ids if sid in by_id],
            "settings": settings,
        })

    @app.route("/api/species/optional")
    def optional_species_api_v431():
        settings = _settings()
        by_id = _species_by_id()
        active = set(settings["active_species"])

        optional_ids = [
            sid for sid in settings["optional_species"]
            if sid in by_id and sid not in active
        ]

        return jsonify({
            "ok": True,
            "version": "v4.3.1",
            "count": len(optional_ids),
            "optional_species": optional_ids,
            "species": [by_id[sid] for sid in optional_ids],
            "settings": settings,
        })

    @app.route("/api/species/all")
    def all_species_api_v431():
        settings = _settings()
        active = set(settings["active_species"])
        return jsonify({
            "ok": True,
            "version": "v4.3.1",
            "species": _with_enabled_flags(_species(), active),
            "settings": settings,
        })

    @app.route("/api/species/enable", methods=["POST"])
    def enable_species_api_v431():
        payload = request.get_json(silent=True) or {}
        sid = str(payload.get("id") or request.form.get("id") or request.args.get("id") or "").strip()

        by_id = _species_by_id()
        if sid not in by_id:
            return jsonify({"ok": False, "error": "Unknown species id", "id": sid}), 404

        settings = _settings()
        active = settings["active_species"]

        if sid not in active:
            active.append(sid)

        settings["active_species"] = active
        _save_settings(settings)

        return jsonify({
            "ok": True,
            "enabled": sid,
            "settings": settings,
        })

    @app.route("/api/species/disable", methods=["POST"])
    def disable_species_api_v431():
        payload = request.get_json(silent=True) or {}
        sid = str(payload.get("id") or request.form.get("id") or request.args.get("id") or "").strip()

        settings = _settings()
        settings["active_species"] = [x for x in settings["active_species"] if x != sid]
        _save_settings(settings)

        return jsonify({
            "ok": True,
            "disabled": sid,
            "settings": settings,
        })

    @app.route("/api/species/reset", methods=["POST"])
    def reset_species_api_v431():
        by_id = _species_by_id()
        settings = _settings()
        settings["active_species"] = [sid for sid in COMMON_SPECIES if sid in by_id]
        _save_settings(settings)

        return jsonify({
            "ok": True,
            "message": "Species reset to common freshwater defaults.",
            "settings": settings,
        })
