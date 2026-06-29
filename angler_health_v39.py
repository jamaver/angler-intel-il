from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import jsonify, render_template

try:
    from intelligence.app_health_backup import get_backup_health_for_app
    from intelligence.app_health_intelligence import get_smart_intelligence_health_for_app
    from intelligence.app_health_sqlite import get_sqlite_health_for_app
    from intelligence.app_health_versions import get_version_health_for_app
except Exception:
    get_backup_health_for_app = None
    get_smart_intelligence_health_for_app = None
    get_sqlite_health_for_app = None
    get_version_health_for_app = None


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
BACKUP_DIR = BASE_DIR / "backups" / "user-data"

IMPORTANT_FILES = [
    "app.py",
    "angler_exports_v37.py",
    "angler_reports_v38.py",
    "angler_health_v39.py",
    "templates/index.html",
    "templates/snapshot.html",
    "static/js/app.js",
    "static/css/style.css",
    "data/favorites.json",
    "data/catches.json",
    "data/reports_index.json",
]

IMPORTANT_DIRS = [
    "data",
    "intelligence",
    "templates",
    "static",
    "static/js",
    "static/css",
    "static/lures",
    "static/fish",
    "reports",
    "backups/user-data",
    "tools",
]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_json(path: Path) -> tuple[bool, Any, str | None]:
    if not path.exists():
        return False, None, "missing"

    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return True, None, "empty"
        return True, json.loads(text), None
    except Exception as exc:
        return True, None, str(exc)


def _json_count(data: Any) -> int:
    if isinstance(data, list):
        return len(data)

    if isinstance(data, dict):
        for key in ("items", "data", "records", "favorites", "catches", "reports"):
            value = data.get(key)
            if isinstance(value, list):
                return len(value)
        return 1 if data else 0

    return 0


def _file_info(rel: str) -> dict[str, Any]:
    path = BASE_DIR / rel
    info: dict[str, Any] = {
        "path": rel,
        "exists": path.exists(),
        "type": None,
        "bytes": None,
        "modified": None,
        "ok": False,
    }

    if not path.exists():
        return info

    try:
        stat = path.stat()
        info["type"] = "dir" if path.is_dir() else "file"
        info["bytes"] = stat.st_size if path.is_file() else None
        info["modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        info["ok"] = True
    except Exception as exc:
        info["error"] = str(exc)

    return info


def _dir_count(path: Path, pattern: str = "*") -> int:
    if not path.exists() or not path.is_dir():
        return 0
    return len([p for p in path.glob(pattern) if p.exists()])


def _json_health() -> dict[str, Any]:
    checks = {}

    json_paths = {
        "favorites": DATA_DIR / "favorites.json",
        "catches": DATA_DIR / "catches.json",
        "reports_index": DATA_DIR / "reports_index.json",
    }

    for name, path in json_paths.items():
        exists, data, error = _read_json(path)
        checks[name] = {
            "path": str(path),
            "exists": exists,
            "valid_json": exists and error in (None, "empty"),
            "empty": error == "empty",
            "error": None if error in (None, "empty", "missing") else error,
            "count": _json_count(data),
        }

    return checks


def _disk_health() -> dict[str, Any]:
    total, used, free = shutil.disk_usage(BASE_DIR)

    def mb(n: int) -> float:
        return round(n / 1024 / 1024, 1)

    return {
        "base_dir": str(BASE_DIR),
        "total_mb": mb(total),
        "used_mb": mb(used),
        "free_mb": mb(free),
        "used_percent": round((used / total) * 100, 1) if total else None,
    }


def _app_file_health() -> dict[str, Any]:
    return {
        "files": [_file_info(rel) for rel in IMPORTANT_FILES],
        "dirs": [_file_info(rel) for rel in IMPORTANT_DIRS],
    }


def _route_health(app) -> dict[str, Any]:
    expected = [
        "/",
        "/health",
        "/api/intel",
        "/exports",
        "/api/export/status",
        "/reports",
        "/api/reports/status",
        "/app-health",
        "/api/app-health",
    ]

    registered_rules = sorted(str(rule.rule) for rule in app.url_map.iter_rules())

    return {
        "expected": [
            {
                "route": route,
                "registered": route in registered_rules,
            }
            for route in expected
        ],
        "registered_count": len(registered_rules),
        "registered_rules": registered_rules,
    }


def _summary_status(json_checks: dict[str, Any], file_checks: dict[str, Any], disk: dict[str, Any]) -> tuple[str, list[str]]:
    issues: list[str] = []

    for name, check in json_checks.items():
        if not check["exists"]:
            if name in ("favorites", "catches"):
                issues.append(f"{name}.json is missing")
        elif not check["valid_json"]:
            issues.append(f"{name}.json is invalid JSON")

    required_files = [
        "app.py",
        "templates/index.html",
        "static/js/app.js",
        "static/css/style.css",
    ]

    files_by_path = {item["path"]: item for item in file_checks["files"]}
    for rel in required_files:
        item = files_by_path.get(rel)
        if not item or not item.get("exists"):
            issues.append(f"{rel} is missing")

    if disk.get("free_mb") is not None and disk["free_mb"] < 500:
        issues.append("Pi storage is below 500 MB free")

    if issues:
        return "warning", issues

    return "ok", []


def build_health_payload(app) -> dict[str, Any]:
    json_checks = _json_health()
    file_checks = _app_file_health()
    disk = _disk_health()
    route_checks = _route_health(app)
    status, issues = _summary_status(json_checks, file_checks, disk)

    backups = sorted(BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True) if BACKUP_DIR.exists() else []
    reports_json = sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if REPORTS_DIR.exists() else []
    reports_html = sorted(REPORTS_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True) if REPORTS_DIR.exists() else []

    payload = {
        "ok": status == "ok",
        "status": status,
        "version": "v3.9",
        "created": _now_iso(),
        "issues": issues,
        "counts": {
            "favorites": json_checks["favorites"]["count"],
            "catches": json_checks["catches"]["count"],
            "reports_index": json_checks["reports_index"]["count"],
            "backup_zips": len(backups),
            "report_json_files": len(reports_json),
            "report_html_files": len(reports_html),
            "lure_assets": _dir_count(BASE_DIR / "static" / "lures"),
            "fish_assets": _dir_count(BASE_DIR / "static" / "fish"),
        },
        "json": json_checks,
        "files": file_checks,
        "disk": disk,
        "routes": route_checks,
        "latest": {
            "backup": backups[0].name if backups else None,
            "report_json": reports_json[0].name if reports_json else None,
            "report_html": reports_html[0].name if reports_html else None,
        },
    }

    if get_sqlite_health_for_app is not None:
        try:
            payload["sqlite_health"] = get_sqlite_health_for_app()
        except Exception as exc:
            payload["sqlite_health"] = {
                "ok": False,
                "available": False,
                "summary": "SQLite status unavailable",
                "json_source_of_truth": True,
                "sqlite_role": "mirror/read-only foundation",
                "errors": [str(exc)],
            }

    if get_backup_health_for_app is not None:
        try:
            payload["backup_health"] = get_backup_health_for_app()
        except Exception as exc:
            payload["backup_health"] = {
                "ok": False,
                "available": False,
                "summary": "Backup status unavailable",
                "errors": [str(exc)],
                "json_source_of_truth": True,
            }

    if get_version_health_for_app is not None:
        try:
            payload["version_health"] = get_version_health_for_app()
        except Exception as exc:
            payload["version_health"] = {
                "ok": False,
                "summary": "Version ledger unavailable",
                "json_source_of_truth": True,
                "sqlite_role": "mirror/read-only foundation",
                "errors": [str(exc)],
            }

    if get_smart_intelligence_health_for_app is not None:
        try:
            payload["intelligence_health"] = get_smart_intelligence_health_for_app()
        except Exception as exc:
            payload["intelligence_health"] = {
                "ok": False,
                "summary": "Smart Intelligence readiness unavailable",
                "json_source_of_truth": True,
                "sqlite_role": "mirror/read-only foundation",
                "errors": [str(exc)],
            }

    return payload


def _html_escape(value: Any) -> str:
    import html
    return html.escape("" if value is None else str(value))


def _status_badge(ok: bool, text: str) -> str:
    cls = "ok" if ok else "bad"
    return f"<span class='badge {cls}'>{_html_escape(text)}</span>"


def _render_health_html(payload: dict[str, Any]) -> str:
    status_ok = payload.get("status") == "ok"
    counts = payload.get("counts", {})
    disk = payload.get("disk", {})
    issues = payload.get("issues", [])

    json_rows = []
    for name, check in payload.get("json", {}).items():
        json_rows.append(f"""
<tr>
  <td>{_html_escape(name)}</td>
  <td>{_status_badge(bool(check.get("exists")), "exists" if check.get("exists") else "missing")}</td>
  <td>{_status_badge(bool(check.get("valid_json")), "valid" if check.get("valid_json") else "invalid")}</td>
  <td>{_html_escape(check.get("count"))}</td>
  <td>{_html_escape(check.get("error") or "")}</td>
</tr>
""")

    file_rows = []
    for item in payload.get("files", {}).get("files", []):
        file_rows.append(f"""
<tr>
  <td>{_html_escape(item.get("path"))}</td>
  <td>{_status_badge(bool(item.get("exists")), "ok" if item.get("exists") else "missing")}</td>
  <td>{_html_escape(item.get("type") or "")}</td>
  <td>{_html_escape(item.get("bytes") or "")}</td>
  <td>{_html_escape(item.get("modified") or "")}</td>
</tr>
""")

    route_rows = []
    for item in payload.get("routes", {}).get("expected", []):
        route_rows.append(f"""
<tr>
  <td>{_html_escape(item.get("route"))}</td>
  <td>{_status_badge(bool(item.get("registered")), "registered" if item.get("registered") else "missing")}</td>
</tr>
""")

    issue_html = "<p class='muted'>No issues detected.</p>"
    if issues:
        issue_html = "<ul>" + "".join(f"<li>{_html_escape(x)}</li>" for x in issues) + "</ul>"

    raw_json = json.dumps(payload, indent=2, ensure_ascii=False)
    sqlite_card = render_template(
        "_sqlite_health_card.html",
        sqlite_health=payload.get("sqlite_health"),
    )
    backup_card = render_template(
        "_backup_health_card.html",
        backup_health=payload.get("backup_health"),
    )
    version_card = render_template(
        "_version_health_card.html",
        version_health=payload.get("version_health"),
    )
    intelligence_card = render_template(
        "_smart_intelligence_health_card.html",
        intelligence_health=payload.get("intelligence_health"),
    )

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Angler Intel - App Health</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 2rem;
      max-width: 1100px;
      line-height: 1.45;
      color: #172018;
    }}
    .card {{
      border: 1px solid #ddd;
      border-radius: 12px;
      padding: 1rem;
      margin: 1rem 0;
      background: #fff;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
    }}
    .metric {{
      border: 1px solid #eee;
      border-radius: 10px;
      padding: 0.85rem;
      background: #fafafa;
    }}
    .metric strong {{
      font-size: 1.5rem;
      display: block;
    }}
    .badge {{
      display: inline-block;
      padding: 0.18rem 0.45rem;
      border-radius: 999px;
      font-size: 0.85rem;
      border: 1px solid #bbb;
    }}
    .ok {{
      background: #e9f8ee;
      border-color: #7bc894;
      color: #145c2b;
    }}
    .bad {{
      background: #fff1f1;
      border-color: #d78a8a;
      color: #7a1e1e;
    }}
    .muted {{
      color: #666;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 0.5rem;
    }}
    th, td {{
      text-align: left;
      border-bottom: 1px solid #eee;
      padding: 0.45rem;
      vertical-align: top;
    }}
    pre {{
      background: #f5f5f5;
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      white-space: pre-wrap;
    }}
    a {{
      color: #0b5d2a;
    }}
  </style>
  <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
  <nav class="ai-main-tabs" aria-label="Angler Intel navigation">
  <a class="ai-main-tab" href="/">Dashboard</a>
  <a class="ai-main-tab" href="/waters">Local Waters</a>
  <a class="ai-main-tab" href="/reports">Saved Reports</a>
  <a class="ai-main-tab active" href="/app-health">App Health</a>
</nav>
  <h1>Angler Intel App Health</h1>
  <p>v3.9 diagnostics and cleanup readiness check.</p>

  <div class="card">
    <h2>Status: {_status_badge(status_ok, payload.get("status", "unknown"))}</h2>
    <p class="muted">Generated: {_html_escape(payload.get("created"))}</p>
    {issue_html}
  </div>

  <div class="card">
    <h2>Quick Counts</h2>
    <div class="grid">
      <div class="metric"><strong>{_html_escape(counts.get("favorites"))}</strong>Favorites</div>
      <div class="metric"><strong>{_html_escape(counts.get("catches"))}</strong>Catches</div>
      <div class="metric"><strong>{_html_escape(counts.get("reports_index"))}</strong>Indexed reports</div>
      <div class="metric"><strong>{_html_escape(counts.get("backup_zips"))}</strong>Backup ZIPs</div>
      <div class="metric"><strong>{_html_escape(counts.get("report_html_files"))}</strong>HTML reports</div>
      <div class="metric"><strong>{_html_escape(counts.get("lure_assets"))}</strong>Lure assets</div>
      <div class="metric"><strong>{_html_escape(counts.get("fish_assets"))}</strong>Fish assets</div>
    </div>
  </div>

  <div class="card">
    <h2>Disk</h2>
    <p><strong>Base:</strong> {_html_escape(disk.get("base_dir"))}</p>
    <p><strong>Used:</strong> {_html_escape(disk.get("used_mb"))} MB / {_html_escape(disk.get("total_mb"))} MB ({_html_escape(disk.get("used_percent"))}%)</p>
    <p><strong>Free:</strong> {_html_escape(disk.get("free_mb"))} MB</p>
  </div>

  <div class="card">
    <h2>JSON Data Checks</h2>
    <table>
      <thead><tr><th>Name</th><th>Exists</th><th>JSON</th><th>Count</th><th>Error</th></tr></thead>
      <tbody>{''.join(json_rows)}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Important File Checks</h2>
    <table>
      <thead><tr><th>Path</th><th>Status</th><th>Type</th><th>Bytes</th><th>Modified</th></tr></thead>
      <tbody>{''.join(file_rows)}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Route Checks</h2>
    <table>
      <thead><tr><th>Route</th><th>Status</th></tr></thead>
      <tbody>{''.join(route_rows)}</tbody>
    </table>
  </div>

  {version_card}

  {intelligence_card}

  {backup_card}

  {sqlite_card}

  <details class="card">
    <summary>Raw health JSON</summary>
    <pre>{_html_escape(raw_json)}</pre>
  </details>

  <p>
    <a href="/">Dashboard</a> |
    <a href="/reports">Saved Reports</a>
  </p>
  <script src="/static/js/global_nav_v433.js"></script>
  <script src="/static/js/ui_polish_v442.js"></script>
  <script src="/static/js/app_health_backups_v443.js"></script>
</body>
</html>
"""


def register_health_routes_v39(app):
    @app.route("/app-health")
    def app_health_page_v39():
        payload = build_health_payload(app)
        return _render_health_html(payload)

    @app.route("/api/app-health")
    def app_health_api_v39():
        return jsonify(build_health_payload(app))

    @app.route("/api/app-health/json")
    def app_health_json_v39():
        return jsonify({
            "ok": True,
            "version": "v3.9",
            "json": _json_health(),
        })

    @app.route("/api/app-health/files")
    def app_health_files_v39():
        return jsonify({
            "ok": True,
            "version": "v3.9",
            "files": _app_file_health(),
            "disk": _disk_health(),
        })

    @app.route("/api/app-health/routes")
    def app_health_routes_v39():
        return jsonify({
            "ok": True,
            "version": "v3.9",
            "routes": _route_health(app),
        })
