#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/angler-intel"
cd "$APP_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$APP_DIR/backups/v4_5_2_app_health_backup_polish_$STAMP"

echo "=== Angler Intel IL v4.5.2 App Health Backup Polish ==="
echo "Backup: $BACKUP_DIR"

mkdir -p "$BACKUP_DIR"
cp -a app.py templates static data intelligence tools "$BACKUP_DIR/" 2>/dev/null || true

echo
echo "1) Confirming current health..."
python tools/qc_v4_5_sqlite.py
python tools/qc_v4_5_1a_sqlite_diagnostics.py
python tools/qc_v4_5_1b_app_health_sqlite.py

echo
echo "2) Writing full backup tool..."

cat > tools/app_backup.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = APP_ROOT / "backups"
DATA_DIR = APP_ROOT / "data"

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "venv",
    ".venv",
    "env",
    "node_modules",
}

INCLUDE_TOP_LEVEL = [
    "app.py",
    "requirements.txt",
    "templates",
    "static",
    "data",
    "intelligence",
    "tools",
]

BACKUP_INDEX = BACKUP_ROOT / "backup_index.json"


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def should_exclude(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True

    # Avoid recursive backups inside backups/.
    try:
        rel = path.relative_to(APP_ROOT)
        if rel.parts and rel.parts[0] == "backups":
            return True
    except ValueError:
        pass

    if path.name.endswith(".pyc"):
        return True

    return False


def safe_json_status(path: Path) -> dict:
    info = {
        "path": str(path.relative_to(APP_ROOT)),
        "exists": path.exists(),
    }

    if not path.exists():
        return info

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        info["valid_json"] = True
        info["top_level_type"] = type(payload).__name__
        if isinstance(payload, list):
            info["item_count_estimate"] = len(payload)
        elif isinstance(payload, dict):
            info["item_count_estimate"] = len(payload)
        else:
            info["item_count_estimate"] = 1
    except Exception as exc:
        info["valid_json"] = False
        info["error"] = str(exc)

    return info


def sqlite_status(path: Path) -> dict:
    info = {
        "path": str(path.relative_to(APP_ROOT)),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }

    if not path.exists():
        return info

    try:
        conn = sqlite3.connect(path)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        info["integrity_check"] = integrity
        info["valid_sqlite"] = integrity == "ok"
    except Exception as exc:
        info["valid_sqlite"] = False
        info["error"] = str(exc)

    return info


def collect_files() -> list[Path]:
    files: list[Path] = []

    for item in INCLUDE_TOP_LEVEL:
        path = APP_ROOT / item
        if not path.exists():
            continue

        if path.is_file():
            if not should_exclude(path):
                files.append(path)
            continue

        for sub in path.rglob("*"):
            if sub.is_file() and not should_exclude(sub):
                files.append(sub)

    return sorted(set(files))


def load_index() -> list[dict]:
    if not BACKUP_INDEX.exists():
        return []

    try:
        payload = json.loads(BACKUP_INDEX.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
    except Exception:
        pass

    return []


def save_index(items: list[dict]) -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    BACKUP_INDEX.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def create_backup(label: str | None = None) -> dict:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    stamp = now_stamp()
    safe_label = ""
    if label:
        safe_label = "_" + "".join(c if c.isalnum() or c in "-_" else "_" for c in label).strip("_")

    archive = BACKUP_ROOT / f"angler_intel_backup_{stamp}{safe_label}.zip"
    manifest_name = "backup_manifest.json"

    files = collect_files()

    manifest = {
        "backup_version": "v4.5.2",
        "created_at": now_utc(),
        "app": "Angler Intel IL",
        "source_root": str(APP_ROOT),
        "archive": str(archive.relative_to(APP_ROOT)),
        "label": label,
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
        "file_count": len(files),
        "json_health": [
            safe_json_status(APP_ROOT / "data" / "favorites.json"),
            safe_json_status(APP_ROOT / "data" / "catches.json"),
            safe_json_status(APP_ROOT / "data" / "saved_reports.json"),
        ],
        "sqlite_health": sqlite_status(APP_ROOT / "data" / "angler_intel.sqlite3"),
        "included_top_level": INCLUDE_TOP_LEVEL,
    }

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            arcname = str(path.relative_to(APP_ROOT))
            zf.write(path, arcname)

        zf.writestr(manifest_name, json.dumps(manifest, indent=2, ensure_ascii=False))

    manifest["archive_size_bytes"] = archive.stat().st_size

    index = load_index()
    index.insert(0, manifest)
    index = index[:25]
    save_index(index)

    latest_manifest = BACKUP_ROOT / "latest_backup_manifest.json"
    latest_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    return manifest


def backup_status() -> dict:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    archives = sorted(
        BACKUP_ROOT.glob("angler_intel_backup_*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    index = load_index()

    latest = None
    if archives:
        latest_path = archives[0]
        latest = {
            "path": str(latest_path.relative_to(APP_ROOT)),
            "size_bytes": latest_path.stat().st_size,
            "modified_at_epoch": latest_path.stat().st_mtime,
        }

    return {
        "backup_version": "v4.5.2",
        "backup_root": str(BACKUP_ROOT.relative_to(APP_ROOT)),
        "archive_count": len(archives),
        "latest": latest,
        "index_count": len(index),
        "recent": index[:5],
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Angler Intel IL backup tool")
    parser.add_argument("--create", action="store_true", help="Create a full backup zip")
    parser.add_argument("--status", action="store_true", help="Show backup status")
    parser.add_argument("--label", default=None, help="Optional backup label")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    if args.create:
        result = create_backup(args.label)
    else:
        result = backup_status()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if args.create:
            print("Backup created")
            print(f"Archive: {result['archive']}")
            print(f"Files: {result['file_count']}")
            print(f"Size: {result.get('archive_size_bytes')} bytes")
            print("JSON remains source of truth.")
        else:
            print("=== Backup Status ===")
            print(f"Backup root: {result['backup_root']}")
            print(f"Archives: {result['archive_count']}")
            if result["latest"]:
                print(f"Latest: {result['latest']['path']}")
                print(f"Latest size: {result['latest']['size_bytes']} bytes")
            else:
                print("Latest: none")
            print("JSON remains source of truth.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY

chmod +x tools/app_backup.py

echo
echo "3) Writing App Health backup helper..."

cat > intelligence/app_health_backup.py <<'PY'
from __future__ import annotations

from typing import Any

try:
    from tools.app_backup import backup_status
except Exception:
    backup_status = None


def get_backup_health_for_app() -> dict[str, Any]:
    """
    Read-only backup status for App Health.

    Creating backups should remain an explicit maintenance action.
    This helper only reports current backup health/status.
    """
    if backup_status is None:
        return {
            "ok": False,
            "available": False,
            "summary": "Backup status unavailable",
            "errors": ["Backup tool could not be imported."],
            "json_source_of_truth": True,
        }

    try:
        status = backup_status()
    except Exception as exc:
        return {
            "ok": False,
            "available": False,
            "summary": "Backup status failed",
            "errors": [str(exc)],
            "json_source_of_truth": True,
        }

    latest = status.get("latest")
    archive_count = int(status.get("archive_count", 0))

    return {
        "ok": archive_count > 0,
        "available": True,
        "summary": "Backups available" if archive_count > 0 else "No full backups created yet",
        "archive_count": archive_count,
        "latest": latest,
        "recent": status.get("recent", []),
        "backup_root": status.get("backup_root"),
        "json_source_of_truth": True,
        "sqlite_role": status.get("sqlite_role", "mirror/read-only foundation"),
    }
PY

echo
echo "4) Creating a fresh full backup with new tool..."
python tools/app_backup.py --create --label v4_5_2_pre_ui

echo
echo "5) Creating App Health backup status partial..."

cat > templates/_backup_health_card.html <<'HTML'
<section class="card backup-health-card" id="backup-health-card">
  <h2>Backups</h2>
  <p class="muted">
    App Health is the maintenance hub. Backups protect JSON, SQLite mirror data, templates, static files, intelligence helpers, and tools.
  </p>

  {% if backup_health %}
    <div class="health-grid">
      <div>
        <strong>Status</strong><br>
        {% if backup_health.ok %}
          <span class="status-good">Backups available</span>
        {% else %}
          <span class="status-warn">No full backup yet</span>
        {% endif %}
      </div>

      <div>
        <strong>Backup count</strong><br>
        <span>{{ backup_health.archive_count }}</span>
      </div>

      <div>
        <strong>Backup folder</strong><br>
        <span>{{ backup_health.backup_root or "backups" }}</span>
      </div>

      <div>
        <strong>Source of truth</strong><br>
        <span>JSON</span>
      </div>
    </div>

    {% if backup_health.latest %}
      <p class="muted">
        Latest backup:
        <code>{{ backup_health.latest.path }}</code>
      </p>
    {% endif %}

    {% if backup_health.recent %}
      <details class="health-details">
        <summary>Recent backup manifests</summary>
        <ul>
          {% for item in backup_health.recent %}
            <li>
              {{ item.created_at }} —
              {{ item.archive }} —
              {{ item.file_count }} files
            </li>
          {% endfor %}
        </ul>
      </details>
    {% endif %}
  {% else %}
    <p class="status-warn">Backup health data unavailable.</p>
  {% endif %}
</section>
HTML

echo
echo "6) Patching app.py with backup health context..."

python - <<'PY'
from pathlib import Path
import re

path = Path("app.py")
text = path.read_text()

import_block = "from intelligence.app_health_backup import get_backup_health_for_app\n"

if import_block not in text:
    lines = text.splitlines()
    insert_at = 0

    for i, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            insert_at = i + 1

    lines.insert(insert_at, import_block.rstrip())
    text = "\n".join(lines) + "\n"

if "def app_health_backup_status():" not in text:
    text += '''

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
'''

pattern = re.compile(
    r"render_template\(([^)]*(?:health|backup|app_health)[^)]*)\)",
    flags=re.IGNORECASE | re.DOTALL,
)

def repl(match):
    call_inside = match.group(1)
    full = match.group(0)

    additions = []

    if "backup_health" not in full:
        additions.append("backup_health=app_health_backup_status()")

    if "sqlite_health" not in full and "app_health_sqlite_status" in text:
        additions.append("sqlite_health=app_health_sqlite_status()")

    if not additions:
        return full

    sep = "," if not call_inside.rstrip().endswith(",") else ""
    new_inside = call_inside + sep + "\n        " + ",\n        ".join(additions)

    return f"render_template({new_inside})"

new_text = pattern.sub(repl, text)

path.write_text(new_text)
print("Patched app.py backup health helper/context where detectable.")
PY

echo
echo "7) Inserting backup partial into App Health template if detectable..."

APP_HEALTH_TEMPLATE=""
for f in templates/*.html; do
  if grep -qi "App Health\|backup\|health" "$f"; then
    APP_HEALTH_TEMPLATE="$f"
    break
  fi
done

if [ -n "$APP_HEALTH_TEMPLATE" ]; then
  python - <<PY
from pathlib import Path

path = Path("$APP_HEALTH_TEMPLATE")
text = path.read_text()

include = '{% include "_backup_health_card.html" %}'

if include not in text:
    # Prefer placing backup card near SQLite card if present.
    sqlite_include = '{% include "_sqlite_health_card.html" %}'
    if sqlite_include in text:
        text = text.replace(sqlite_include, include + "\\n" + sqlite_include, 1)
    else:
        markers = ["</main>", "</section>", "</body>"]
        inserted = False

        for marker in markers:
            idx = text.lower().rfind(marker)
            if idx != -1:
                text = text[:idx] + "\\n" + include + "\\n" + text[idx:]
                inserted = True
                break

        if not inserted:
            text += "\\n" + include + "\\n"

    path.write_text(text)
    print(f"Inserted backup health partial into {path}")
else:
    print(f"Backup health partial already present in {path}")
PY
else
  echo "No obvious App Health template found. Partial created but not inserted."
fi

echo
echo "8) Adding backup card CSS if missing..."

cat >> static/css/style.css <<'CSS'

/* v4.5.2 Backup card in App Health */
.backup-health-card {
  margin-top: 1rem;
}

.backup-health-card code {
  word-break: break-word;
}
CSS

echo
echo "9) Writing QC for v4.5.2..."

cat > tools/qc_v4_5_2_backup_polish.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

errors = []

paths = [
    APP_ROOT / "tools" / "app_backup.py",
    APP_ROOT / "intelligence" / "app_health_backup.py",
    APP_ROOT / "app.py",
]

for path in paths:
    try:
        ast.parse(path.read_text())
    except SyntaxError as exc:
        errors.append(f"{path.relative_to(APP_ROOT)} syntax error: {exc}")

partial = APP_ROOT / "templates" / "_backup_health_card.html"
if not partial.exists():
    errors.append("Missing templates/_backup_health_card.html")

app_text = (APP_ROOT / "app.py").read_text()
if "get_backup_health_for_app" not in app_text:
    errors.append("app.py does not import/use get_backup_health_for_app")

if "app_health_backup_status" not in app_text:
    errors.append("app.py missing app_health_backup_status helper")

if partial.exists() and "Admin" in partial.read_text():
    errors.append("Backup health card should not mention Admin")

from tools.app_backup import backup_status
from intelligence.app_health_backup import get_backup_health_for_app

status = backup_status()
health = get_backup_health_for_app()

if not isinstance(status, dict):
    errors.append("backup_status did not return a dict")

if not isinstance(health, dict):
    errors.append("get_backup_health_for_app did not return a dict")

if health.get("json_source_of_truth") is not True:
    errors.append("Backup health does not preserve JSON source-of-truth marker")

if int(status.get("archive_count", 0)) < 1:
    errors.append("No backup archives found after v4.5.2 setup")

index = APP_ROOT / "backups" / "backup_index.json"
if not index.exists():
    errors.append("Missing backups/backup_index.json")
else:
    try:
        payload = json.loads(index.read_text())
        if not isinstance(payload, list):
            errors.append("backup_index.json is not a list")
    except Exception as exc:
        errors.append(f"backup_index.json invalid JSON: {exc}")

if errors:
    print("QC FAILED: v4.5.2 Backup Polish")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.5.2 Backup Polish")
print("App Health remains maintenance hub.")
print("JSON remains source of truth.")
PY

chmod +x tools/qc_v4_5_2_backup_polish.py

echo
echo "10) Writing version marker..."

cat > data/version_v4_5_2_app_health_backup_polish.json <<JSON
{
  "version": "v4.5.2-app-health-backup-polish",
  "previous": "v4.5.1b-app-health-sqlite-status",
  "json_source_of_truth": true,
  "sqlite_role": "mirror/read-only foundation",
  "admin_expanded": false,
  "admin_menu_restored": false,
  "app_health_maintenance_hub": true,
  "backup_tool_added": true,
  "installed_at": "$(date -Iseconds)"
}
JSON

echo
echo "11) Running QC..."
python tools/qc_v4_5_sqlite.py
python tools/qc_v4_5_1a_sqlite_diagnostics.py
python tools/qc_v4_5_1b_app_health_sqlite.py
python tools/qc_v4_5_2_backup_polish.py

echo
echo "12) Restarting service..."
sudo systemctl restart angler-intel
sleep 2
sudo systemctl status angler-intel --no-pager -l | head -40

echo
echo "13) Backup status..."
python tools/app_backup.py --status

echo
echo "14) Git status..."
git status --short || true

echo
echo "=== v4.5.2 complete ==="
echo
echo "Commit with:"
echo "git add app.py intelligence/app_health_backup.py templates/_backup_health_card.html static/css/style.css tools/app_backup.py tools/qc_v4_5_2_backup_polish.py data/version_v4_5_2_app_health_backup_polish.json upgrade_v4_5_2_app_health_backup_polish.sh"
echo "git commit -m 'Add v4.5.2 App Health backup polish'"
echo "git push"
