from __future__ import annotations

import json
import secrets
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import jsonify, request


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TOKEN_PATH = DATA_DIR / "admin_token.txt"

BACKUP_DIRS = {
    "user-data": BASE_DIR / "backups" / "user-data",
    "releases": BASE_DIR / "backups" / "releases",
}

REPORTS_DIR = BASE_DIR / "reports"
REPORTS_INDEX = DATA_DIR / "reports_index.json"
SERVICE_NAME = "angler-intel"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_token() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if TOKEN_PATH.exists():
        token = TOKEN_PATH.read_text(encoding="utf-8").strip()
        if token:
            return token

    token = secrets.token_urlsafe(24)
    TOKEN_PATH.write_text(token + "\n", encoding="utf-8")
    try:
        TOKEN_PATH.chmod(0o600)
    except Exception:
        pass
    return token


def _provided_token() -> str:
    return (
        request.headers.get("X-Admin-Token")
        or request.args.get("token")
        or request.form.get("token")
        or ""
    ).strip()


def _authorized() -> bool:
    return bool(_provided_token()) and secrets.compare_digest(_provided_token(), _ensure_token())


def _require_auth():
    if not _authorized():
        return jsonify({
            "ok": False,
            "error": "Unauthorized. Provide the admin token using X-Admin-Token.",
            "token_file": str(TOKEN_PATH),
        }), 401
    return None


def _safe_name(filename: str, allowed_suffixes: tuple[str, ...]) -> bool:
    if not filename:
        return False
    if "/" in filename or "\\" in filename or ".." in filename:
        return False
    return filename.endswith(allowed_suffixes)


def _file_info(path: Path, kind: str) -> dict[str, Any]:
    stat = path.stat()
    return {
        "kind": kind,
        "name": path.name,
        "path": str(path),
        "bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def _list_backups() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for kind, folder in BACKUP_DIRS.items():
        if not folder.exists():
            continue

        for path in folder.glob("*"):
            if path.is_file() and path.suffix in (".zip", ".tgz", ".gz"):
                items.append(_file_info(path, kind))

    return sorted(items, key=lambda x: x.get("modified", ""), reverse=True)


def _list_reports() -> list[dict[str, Any]]:
    if not REPORTS_DIR.exists():
        return []

    items = []
    for path in REPORTS_DIR.glob("*"):
        if path.is_file() and path.suffix in (".html", ".json"):
            items.append(_file_info(path, "report"))

    return sorted(items, key=lambda x: x.get("modified", ""), reverse=True)


def _run(cmd: list[str], timeout: int = 10) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-6000:],
            "stderr": proc.stderr[-6000:],
            "cmd": cmd,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "cmd": cmd,
        }


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


def _remove_report_from_index(filename: str) -> None:
    data = _read_json(REPORTS_INDEX, [])

    if isinstance(data, dict) and isinstance(data.get("reports"), list):
        reports = data["reports"]
        wrapper = True
    elif isinstance(data, list):
        reports = data
        wrapper = False
    else:
        return

    filtered = []
    for item in reports:
        if not isinstance(item, dict):
            filtered.append(item)
            continue

        if item.get("json_file") == filename or item.get("html_file") == filename:
            continue

        filtered.append(item)

    if wrapper:
        data["reports"] = filtered
        _write_json(REPORTS_INDEX, data)
    else:
        _write_json(REPORTS_INDEX, filtered)


def _render_admin_page() -> str:
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Angler Intel IL - Admin</title>
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
      max-width: 520px;
    }
    button {
      border-radius: 8px;
      border: 1px solid #bbb;
      cursor: pointer;
    }
    button.danger {
      border-color: #b55;
      background: #fff1f1;
    }
    pre {
      background: #f5f5f5;
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      white-space: pre-wrap;
    }
    .muted { color: #666; }
    .row {
      border-top: 1px solid #eee;
      padding: 0.6rem 0;
    }
    a { color: #0b5d2a; }
  </style>
  <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
  <nav class="ai-main-tabs" aria-label="Angler Intel navigation">
  <a class="ai-main-tab" href="/">Dashboard</a>
  <a class="ai-main-tab" href="/waters">Local Waters</a>
  <a class="ai-main-tab" href="/reports">Saved Reports</a>
  <a class="ai-main-tab" href="/app-health">App Health</a>
  <a class="ai-main-tab active" href="/admin">Admin</a>
  <a class="ai-main-tab" href="/exports">Export</a>
</nav>
  <h1>Angler Intel IL Admin</h1>
  <p class="muted">v3.10 local admin tools. Delete/restart actions require your admin token.</p>

  <div class="card">
    <h2>Admin Token</h2>
    <p>On the Pi, get it with:</p>
    <pre>cat ~/angler-intel/data/admin_token.txt</pre>
    <input id="token" placeholder="Paste admin token here">
    <p class="muted">The token is only used in this browser session.</p>
  </div>

  <div class="card">
    <h2>Service</h2>
    <button onclick="serviceStatus()">Service status</button>
    <button onclick="serviceLogs()">Recent logs</button>
    <button class="danger" onclick="restartService()">Restart angler-intel</button>
    <pre id="serviceBox">No service action yet.</pre>
  </div>

  <div class="card">
    <h2>Backups</h2>
    <button onclick="loadBackups()">Refresh backups</button>
    <label>
      Keep newest user-data backups:
      <input id="keepCount" value="5" style="max-width:90px">
    </label>
    <button class="danger" onclick="pruneBackups()">Prune old user-data backups</button>
    <div id="backupsBox">Loading...</div>
  </div>

  <div class="card">
    <h2>Saved Reports</h2>
    <button onclick="loadReports()">Refresh reports</button>
    <div id="reportsBox">Loading...</div>
  </div>

  <div class="card">
    <h2>Admin Status</h2>
    <button onclick="loadStatus()">Refresh admin status</button>
    <pre id="statusBox">Loading...</pre>
  </div>

  <p>
    <a href="/">Dashboard</a> |
    <a href="/app-health">App Health</a> |
    <a href="/exports">Backup & Export</a> |
    <a href="/reports">Saved Reports</a>
  </p>

<script>
function token() {
  return document.getElementById("token").value.trim();
}

async function api(url, options = {}) {
  options.headers = options.headers || {};
  if (token()) options.headers["X-Admin-Token"] = token();
  const res = await fetch(url, options);
  const text = await res.text();

  try {
    return JSON.parse(text);
  } catch {
    return {ok: res.ok, text};
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

async function loadStatus() {
  const box = document.getElementById("statusBox");
  box.textContent = "Loading...";
  const data = await api("/api/admin/status");
  box.textContent = JSON.stringify(data, null, 2);
}

async function serviceStatus() {
  const box = document.getElementById("serviceBox");
  box.textContent = "Loading service status...";
  const data = await api("/api/admin/service/status");
  box.textContent = JSON.stringify(data, null, 2);
}

async function serviceLogs() {
  const box = document.getElementById("serviceBox");
  box.textContent = "Loading logs...";
  const data = await api("/api/admin/service/logs");
  box.textContent = data.stdout || JSON.stringify(data, null, 2);
}

async function restartService() {
  const box = document.getElementById("serviceBox");

  if (!token()) {
    box.textContent = "Paste your admin token first.";
    return;
  }

  if (!confirm("Restart the angler-intel service now?")) return;

  const data = await api("/api/admin/service/restart", {method: "POST"});
  box.textContent = JSON.stringify(data, null, 2);
}

async function loadBackups() {
  const box = document.getElementById("backupsBox");
  box.textContent = "Loading backups...";
  const data = await api("/api/admin/backups");

  if (!data.backups || data.backups.length === 0) {
    box.innerHTML = "<p class='muted'>No backups found.</p>";
    return;
  }

  box.innerHTML = data.backups.map(b => `
    <div class="row">
      <strong>${esc(b.name)}</strong><br>
      <span class="muted">${esc(b.kind)} · ${esc(b.modified)} · ${esc(b.bytes)} bytes</span><br>
      <button class="danger" onclick="deleteBackup('${esc(b.kind)}','${esc(b.name)}')">Delete</button>
    </div>
  `).join("");
}

async function deleteBackup(kind, name) {
  if (!token()) {
    alert("Paste your admin token first.");
    return;
  }

  if (!confirm("Delete backup " + name + "?")) return;

  const data = await api("/api/admin/backups/delete", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({kind, filename: name})
  });

  alert(JSON.stringify(data, null, 2));
  loadBackups();
  loadStatus();
}

async function pruneBackups() {
  if (!token()) {
    alert("Paste your admin token first.");
    return;
  }

  const keep = Number(document.getElementById("keepCount").value || 5);

  if (!confirm("Delete old user-data backups and keep newest " + keep + "?")) return;

  const data = await api("/api/admin/backups/prune", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({kind: "user-data", keep})
  });

  alert(JSON.stringify(data, null, 2));
  loadBackups();
  loadStatus();
}

async function loadReports() {
  const box = document.getElementById("reportsBox");
  box.textContent = "Loading reports...";
  const data = await api("/api/admin/reports");

  if (!data.reports || data.reports.length === 0) {
    box.innerHTML = "<p class='muted'>No report files found.</p>";
    return;
  }

  box.innerHTML = data.reports.map(r => `
    <div class="row">
      <strong>${esc(r.name)}</strong><br>
      <span class="muted">${esc(r.modified)} · ${esc(r.bytes)} bytes</span><br>
      <button class="danger" onclick="deleteReport('${esc(r.name)}')">Delete</button>
    </div>
  `).join("");
}

async function deleteReport(name) {
  if (!token()) {
    alert("Paste your admin token first.");
    return;
  }

  if (!confirm("Delete report file " + name + "?")) return;

  const data = await api("/api/admin/reports/delete", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({filename: name})
  });

  alert(JSON.stringify(data, null, 2));
  loadReports();
  loadStatus();
}

loadStatus();
loadBackups();
loadReports();
</script>
</body>
</html>
"""


def register_admin_routes_v310(app):
    _ensure_token()

    @app.route("/admin")
    def admin_page_v310():
        return _render_admin_page()

    @app.route("/api/admin/status")
    def admin_status_v310():
        backups = _list_backups()
        reports = _list_reports()
        return jsonify({
            "ok": True,
            "version": "v3.10",
            "created": _now_iso(),
            "token_file": str(TOKEN_PATH),
            "counts": {
                "backups": len(backups),
                "reports": len(reports),
            },
            "paths": {
                "base": str(BASE_DIR),
                "user_data_backups": str(BACKUP_DIRS["user-data"]),
                "release_backups": str(BACKUP_DIRS["releases"]),
                "reports": str(REPORTS_DIR),
            },
            "routes": [
                "/admin",
                "/api/admin/status",
                "/api/admin/backups",
                "/api/admin/backups/delete",
                "/api/admin/backups/prune",
                "/api/admin/reports",
                "/api/admin/reports/delete",
                "/api/admin/service/status",
                "/api/admin/service/logs",
                "/api/admin/service/restart",
            ],
        })

    @app.route("/api/admin/backups")
    def admin_backups_v310():
        return jsonify({
            "ok": True,
            "version": "v3.10",
            "backups": _list_backups(),
        })

    @app.route("/api/admin/backups/delete", methods=["POST"])
    def admin_delete_backup_v310():
        auth = _require_auth()
        if auth:
            return auth

        payload = request.get_json(silent=True) or {}
        kind = str(payload.get("kind") or request.form.get("kind") or "").strip()
        filename = str(payload.get("filename") or request.form.get("filename") or "").strip()

        if kind not in BACKUP_DIRS:
            return jsonify({"ok": False, "error": "Invalid backup kind"}), 400

        if not _safe_name(filename, (".zip", ".tgz", ".gz")):
            return jsonify({"ok": False, "error": "Invalid backup filename"}), 400

        path = BACKUP_DIRS[kind] / filename
        if not path.exists() or not path.is_file():
            return jsonify({"ok": False, "error": "Backup not found"}), 404

        path.unlink()

        return jsonify({
            "ok": True,
            "deleted": filename,
            "kind": kind,
        })

    @app.route("/api/admin/backups/prune", methods=["POST"])
    def admin_prune_backups_v310():
        auth = _require_auth()
        if auth:
            return auth

        payload = request.get_json(silent=True) or {}
        kind = str(payload.get("kind") or "user-data").strip()
        keep = int(payload.get("keep") or 5)

        if kind not in BACKUP_DIRS:
            return jsonify({"ok": False, "error": "Invalid backup kind"}), 400

        if keep < 1:
            return jsonify({"ok": False, "error": "Keep must be at least 1"}), 400

        folder = BACKUP_DIRS[kind]
        files = []
        if folder.exists():
            files = sorted(
                [p for p in folder.glob("*") if p.is_file() and p.suffix in (".zip", ".tgz", ".gz")],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

        deleted = []
        for path in files[keep:]:
            deleted.append(path.name)
            path.unlink()

        return jsonify({
            "ok": True,
            "kind": kind,
            "kept": min(keep, len(files)),
            "deleted": deleted,
        })

    @app.route("/api/admin/reports")
    def admin_reports_v310():
        return jsonify({
            "ok": True,
            "version": "v3.10",
            "reports": _list_reports(),
        })

    @app.route("/api/admin/reports/delete", methods=["POST"])
    def admin_delete_report_v310():
        auth = _require_auth()
        if auth:
            return auth

        payload = request.get_json(silent=True) or {}
        filename = str(payload.get("filename") or request.form.get("filename") or "").strip()

        if not _safe_name(filename, (".html", ".json")):
            return jsonify({"ok": False, "error": "Invalid report filename"}), 400

        path = REPORTS_DIR / filename
        if not path.exists() or not path.is_file():
            return jsonify({"ok": False, "error": "Report not found"}), 404

        path.unlink()
        _remove_report_from_index(filename)

        return jsonify({
            "ok": True,
            "deleted": filename,
        })

    @app.route("/api/admin/service/status")
    def admin_service_status_v310():
        return jsonify(_run(["systemctl", "status", SERVICE_NAME, "--no-pager"], timeout=8))

    @app.route("/api/admin/service/logs")
    def admin_service_logs_v310():
        return jsonify(_run(["journalctl", "-u", SERVICE_NAME, "-n", "100", "--no-pager"], timeout=8))

    @app.route("/api/admin/service/restart", methods=["POST"])
    def admin_service_restart_v310():
        auth = _require_auth()
        if auth:
            return auth

        # Check whether passwordless sudo is available. The web app cannot type a sudo password.
        sudo_check = _run(["sudo", "-n", "true"], timeout=5)
        if not sudo_check.get("ok"):
            return jsonify({
                "ok": False,
                "error": "Passwordless sudo is not available for the Flask service user.",
                "fix": "Use terminal restart: sudo systemctl restart angler-intel",
                "details": sudo_check,
            }), 403

        # Restart asynchronously so the request can return before Flask is killed/restarted.
        cmd = "sleep 1; sudo -n systemctl restart angler-intel"
        try:
            subprocess.Popen(
                ["bash", "-lc", cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return jsonify({
                "ok": True,
                "message": "Restart scheduled. Refresh the dashboard in a few seconds.",
                "service": SERVICE_NAME,
            })
        except Exception as exc:
            return jsonify({
                "ok": False,
                "error": str(exc),
            }), 500
