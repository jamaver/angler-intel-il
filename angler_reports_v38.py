from __future__ import annotations

import html
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from flask import jsonify, request, send_file


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


def _render_item_list(value: Any, empty: str = "No data saved for this section.") -> str:
    if not value:
        return f"<p class='muted'>{html.escape(empty)}</p>"

    if isinstance(value, dict):
        items = []
        for k, v in value.items():
            items.append(f"<li><strong>{html.escape(str(k))}:</strong> {html.escape(_short_text(v, 400))}</li>")
        return "<ul>" + "\n".join(items) + "</ul>"

    if isinstance(value, list):
        items = []
        for entry in value[:12]:
            if isinstance(entry, dict):
                label = (
                    entry.get("name")
                    or entry.get("species")
                    or entry.get("title")
                    or entry.get("water")
                    or entry.get("waterbody")
                    or entry.get("day")
                    or entry.get("date")
                    or "Item"
                )
                detail = _short_text(entry, 360)
                items.append(f"<li><strong>{html.escape(str(label))}</strong><br>{html.escape(detail)}</li>")
            else:
                items.append(f"<li>{html.escape(_short_text(entry, 360))}</li>")
        return "<ul>" + "\n".join(items) + "</ul>"

    return f"<p>{html.escape(_short_text(value, 500))}</p>"


def _render_report_html(report_meta: dict[str, Any], payload: dict[str, Any]) -> str:
    summary = _extract_summary(payload)

    title = report_meta.get("title") or "Saved Fishing Report"
    created = report_meta.get("created") or ""
    zip_code = report_meta.get("zip") or summary.get("zip") or ""

    best_bet = summary.get("best_bet")
    weather = summary.get("weather")
    species = summary.get("species")
    lures = summary.get("lures")
    waters = summary.get("waters")
    forecast = summary.get("forecast")

    raw_json = json.dumps(payload, indent=2, ensure_ascii=False)

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)} - Angler Intel IL</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 2rem;
      max-width: 1000px;
      line-height: 1.45;
      color: #172018;
    }}
    .top {{
      border-bottom: 1px solid #ddd;
      margin-bottom: 1.5rem;
      padding-bottom: 1rem;
    }}
    .card {{
      border: 1px solid #ddd;
      border-radius: 12px;
      padding: 1rem;
      margin: 1rem 0;
      background: #fff;
    }}
    .muted {{
      color: #666;
    }}
    code, pre {{
      background: #f5f5f5;
      border-radius: 8px;
    }}
    code {{
      padding: 0.15rem 0.3rem;
    }}
    pre {{
      padding: 1rem;
      overflow-x: auto;
      white-space: pre-wrap;
    }}
    a {{
      color: #0b5d2a;
    }}
    li {{
      margin: 0.4rem 0;
    }}
    @media print {{
      body {{ margin: 0.5in; }}
      .no-print {{ display: none; }}
      .card {{ break-inside: avoid; }}
    }}
  </style>
  <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
  <nav class="ai-main-tabs" aria-label="Angler Intel navigation">
  <a class="ai-main-tab" href="/">Dashboard</a>
  <a class="ai-main-tab" href="/waters">Local Waters</a>
  <a class="ai-main-tab active" href="/reports">Saved Reports</a>
  <a class="ai-main-tab" href="/app-health">App Health</a>
  <a class="ai-main-tab" href="/admin">Admin</a>
  <a class="ai-main-tab" href="/exports">Export</a>
</nav>
  <div class="top">
    <h1>{html.escape(title)}</h1>
    <p class="muted">Saved by Angler Intel IL v3.8</p>
    <p><strong>Created:</strong> {html.escape(created)}</p>
    <p><strong>ZIP:</strong> {html.escape(str(zip_code or "N/A"))}</p>
    <p class="no-print">
      <a href="/reports">Back to saved reports</a> |
      <a href="/">Dashboard</a> |
      <button onclick="window.print()">Print / Save PDF</button>
    </p>
  </div>

  <div class="card">
    <h2>Best Bet Today</h2>
    {_render_item_list(best_bet, "No Best Bet data saved.")}
  </div>

  <div class="card">
    <h2>Trip Conditions</h2>
    {_render_item_list(weather, "No weather data saved.")}
  </div>

  <div class="card">
    <h2>Species Ranking</h2>
    {_render_item_list(species, "No species ranking saved.")}
  </div>

  <div class="card">
    <h2>Recommended Lures</h2>
    {_render_item_list(lures, "No lure data saved.")}
  </div>

  <div class="card">
    <h2>Nearby Waters</h2>
    {_render_item_list(waters, "No nearby waters saved.")}
  </div>

  <div class="card">
    <h2>7-Day Fishing Outlook</h2>
    {_render_item_list(forecast, "No forecast data saved.")}
  </div>

  <details class="card">
    <summary>Raw saved JSON</summary>
    <pre>{html.escape(raw_json)}</pre>
  </details>
</body>
</html>
"""


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
  <title>Angler Intel IL - Saved Reports</title>
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
    <a class="ai-main-tab" href="/admin">Admin</a>
    <a class="ai-main-tab" href="/exports">Export</a>
  </nav>

  <h1 class="page-title">Saved Offline Reports</h1>
  <p>v3.8 saves local fishing reports on this Pi using your current Angler Intel data.</p>

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
    <a href="/exports">Backup & Export</a>
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

        query = urlencode({"zip": zip_code})

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

        html_file = match.get("html_file")
        if not html_file:
            return jsonify({"ok": False, "error": "Report HTML not found"}), 404

        path = _safe_report_file(html_file)
        if path is None:
            return jsonify({"ok": False, "error": "Report HTML not found"}), 404

        return path.read_text(encoding="utf-8")

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
