from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Response, jsonify, render_template, send_file


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = BASE_DIR / "backups" / "user-data"

CORE_JSON_FILES = [
    DATA_DIR / "favorites.json",
    DATA_DIR / "catches.json",
]

FULL_BACKUP_PATHS = [
    DATA_DIR,
    BASE_DIR / "intelligence",
    BASE_DIR / "static" / "lures",
    BASE_DIR / "static" / "fish",
]


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


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


def _json_record_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = None
        for key in ("catches", "favorites", "items", "data", "records"):
            val = data.get(key)
            if isinstance(val, list):
                rows = val
                break
        if rows is None:
            rows = [data]
    else:
        rows = []

    clean_rows: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            clean_rows.append(row)
        else:
            clean_rows.append({"value": row})
    return clean_rows


def _flatten_csv_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def _csv_response(json_path: Path, download_name: str) -> Response:
    data = _read_json(json_path, [])
    rows = _json_record_list(data)

    preferred = [
        "date",
        "time",
        "timestamp",
        "zip",
        "water",
        "waterbody",
        "location",
        "species",
        "length",
        "weight",
        "lure",
        "bait",
        "weather",
        "temperature",
        "wind",
        "notes",
    ]

    headers: list[str] = []
    all_keys = set()
    for row in rows:
        all_keys.update(row.keys())

    for key in preferred:
        if key in all_keys:
            headers.append(key)

    for key in sorted(all_keys):
        if key not in headers:
            headers.append(key)

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=headers or ["empty"])
    writer.writeheader()

    for row in rows:
        writer.writerow({key: _flatten_csv_value(row.get(key)) for key in headers})

    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={download_name}"},
    )


def _add_path_to_zip(zf: zipfile.ZipFile, path: Path, arc_prefix: str = "") -> None:
    if not path.exists():
        return

    if path.is_file():
        arcname = Path(arc_prefix) / path.relative_to(BASE_DIR)
        zf.write(path, arcname.as_posix())
        return

    for child in path.rglob("*"):
        if child.is_file():
            arcname = Path(arc_prefix) / child.relative_to(BASE_DIR)
            zf.write(child, arcname.as_posix())


def _send_zip_buffer(buf: io.BytesIO, download_name: str):
    buf.seek(0)
    try:
        return send_file(
            buf,
            mimetype="application/zip",
            as_attachment=True,
            download_name=download_name,
        )
    except TypeError:
        return send_file(
            buf,
            mimetype="application/zip",
            as_attachment=True,
            attachment_filename=download_name,
        )


def _send_zip_file(path: Path, download_name: str):
    try:
        return send_file(
            path,
            mimetype="application/zip",
            as_attachment=True,
            download_name=download_name,
        )
    except TypeError:
        return send_file(
            path,
            mimetype="application/zip",
            as_attachment=True,
            attachment_filename=download_name,
        )


def _build_zip(include_full_assets: bool) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {
            "app": "Angler Intel IL",
            "export_version": "v3.7",
            "created": datetime.now().isoformat(timespec="seconds"),
            "type": "full-user-backup" if include_full_assets else "core-json-export",
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        for path in CORE_JSON_FILES:
            _add_path_to_zip(zf, path)

        if include_full_assets:
            for path in FULL_BACKUP_PATHS:
                _add_path_to_zip(zf, path)

    buf.seek(0)
    return buf


def _file_info(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "download_url": f"/api/backup/download/{path.name}",
    }


def register_export_routes_v37(app):
    @app.route("/exports")
    def exports_page_v37():
        return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Angler Intel IL - Backup & Export</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 2rem;
      max-width: 900px;
      line-height: 1.45;
    }
    a, button {
      font-size: 1rem;
    }
    button {
      padding: 0.5rem 0.85rem;
      border-radius: 8px;
      border: 1px solid #bbb;
      cursor: pointer;
    }
    .card {
      border: 1px solid #ddd;
      border-radius: 12px;
      padding: 1rem;
      margin: 1rem 0;
    }
    code {
      background: #f5f5f5;
      padding: 0.15rem 0.3rem;
      border-radius: 4px;
    }
    pre {
      background: #f5f5f5;
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      white-space: pre-wrap;
    }
  </style>
  <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
  {render_template("_nav.html")}
  <h1>Angler Intel IL Backup & Export</h1>
  <p>v3.7 adds safe exports for favorites, catches, and local app data.</p>

  <div class="card">
    <h2>Download exports</h2>
    <p><a href="/api/export/user-data.zip">Download core JSON user data</a></p>
    <p><a href="/api/export/full-backup.zip">Download full user backup ZIP</a></p>
    <p><a href="/api/export/catches.csv">Download catches CSV</a></p>
    <p><a href="/api/export/favorites.csv">Download favorites CSV</a></p>
  </div>

  <div class="card">
    <h2>Create backup on the Pi</h2>
    <p>This saves a ZIP under <code>~/angler-intel/backups/user-data/</code>.</p>
    <button onclick="createBackup()">Create local backup</button>
    <pre id="backupResult">No backup created yet.</pre>
  </div>

  <div class="card">
    <h2>Existing local backups</h2>
    <button onclick="loadBackups()">Refresh backup list</button>
    <pre id="backupList">Click refresh.</pre>
  </div>

  <p><a href="/">Back to dashboard</a></p>

<script>
async function createBackup() {
  const box = document.getElementById("backupResult");
  box.textContent = "Creating backup...";
  try {
    const res = await fetch("/api/backup/create", {method: "POST"});
    const data = await res.json();
    box.textContent = JSON.stringify(data, null, 2);
    loadBackups();
  } catch (err) {
    box.textContent = "Backup failed: " + err;
  }
}

async function loadBackups() {
  const box = document.getElementById("backupList");
  box.textContent = "Loading...";
  try {
    const res = await fetch("/api/backup/list");
    const data = await res.json();

    if (!data.backups || data.backups.length === 0) {
      box.textContent = "No local backups found.";
      return;
    }

    box.innerHTML = data.backups.map(b =>
      `${b.modified}  ${b.name}  ${b.bytes} bytes\\n${location.origin}${b.download_url}`
    ).join("\\n\\n");
  } catch (err) {
    box.textContent = "Unable to load backups: " + err;
  }
}
</script>
  <script src="/static/js/ui_polish_v442.js"></script>
</body>
</html>
"""

    @app.route("/api/export/status")
    def export_status_v37():
        catches = _json_record_list(_read_json(DATA_DIR / "catches.json", []))
        favorites = _json_record_list(_read_json(DATA_DIR / "favorites.json", []))
        return jsonify({
            "ok": True,
            "version": "v3.7",
            "features": [
                "core JSON export",
                "full user backup export",
                "catches CSV export",
                "favorites CSV export",
                "local backup creation",
                "local backup listing",
            ],
            "counts": {
                "catches": len(catches),
                "favorites": len(favorites),
            },
            "paths": {
                "data": str(DATA_DIR),
                "backups": str(BACKUP_DIR),
            },
        })

    @app.route("/api/export/user-data.zip")
    @app.route("/api/export/all")
    def export_user_data_zip_v37():
        name = f"angler-intel-user-data-{_now_stamp()}.zip"
        return _send_zip_buffer(_build_zip(include_full_assets=False), name)

    @app.route("/api/export/full-backup.zip")
    def export_full_backup_zip_v37():
        name = f"angler-intel-full-user-backup-{_now_stamp()}.zip"
        return _send_zip_buffer(_build_zip(include_full_assets=True), name)

    @app.route("/api/export/catches.csv")
    def export_catches_csv_v37():
        return _csv_response(DATA_DIR / "catches.json", f"angler-intel-catches-{_now_stamp()}.csv")

    @app.route("/api/export/favorites.csv")
    def export_favorites_csv_v37():
        return _csv_response(DATA_DIR / "favorites.json", f"angler-intel-favorites-{_now_stamp()}.csv")

    @app.route("/api/backup/create", methods=["GET", "POST"])
    def create_local_backup_v37():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        name = f"angler-intel-local-backup-{_now_stamp()}.zip"
        path = BACKUP_DIR / name

        buf = _build_zip(include_full_assets=True)
        path.write_bytes(buf.getvalue())

        return jsonify({
            "ok": True,
            "backup": _file_info(path),
        })

    @app.route("/api/backup/list")
    def list_local_backups_v37():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backups = sorted(
            [p for p in BACKUP_DIR.glob("*.zip") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return jsonify({
            "ok": True,
            "backups": [_file_info(p) for p in backups],
        })

    @app.route("/api/backup/download/<filename>")
    def download_local_backup_v37(filename: str):
        if "/" in filename or "\\" in filename or not filename.endswith(".zip"):
            return jsonify({"ok": False, "error": "Invalid backup filename"}), 400

        path = BACKUP_DIR / filename
        if not path.exists() or not path.is_file():
            return jsonify({"ok": False, "error": "Backup not found"}), 404

        return _send_zip_file(path, filename)
