#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/angler-intel"
cd "$APP_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$APP_DIR/backups/v4_5_1b_app_health_sqlite_status_$STAMP"

echo "=== Angler Intel IL v4.5.1b App Health SQLite Status ==="
echo "Backup: $BACKUP_DIR"

mkdir -p "$BACKUP_DIR"
cp -a app.py templates static data intelligence tools "$BACKUP_DIR/" 2>/dev/null || true

echo
echo "1) Confirming v4.5.1a diagnostics..."
python tools/sqlite_init.py
python tools/qc_v4_5_sqlite.py
python tools/qc_v4_5_1a_sqlite_diagnostics.py

echo
echo "2) Adding read-only App Health helper..."

cat > intelligence/app_health_sqlite.py <<'PY'
from __future__ import annotations

from typing import Any

try:
    from intelligence.sqlite_foundation import initialize_and_mirror
    from tools.sqlite_diagnostics import collect_diagnostics
except Exception:  # defensive import safety for Flask startup
    initialize_and_mirror = None
    collect_diagnostics = None


def get_sqlite_health_for_app() -> dict[str, Any]:
    """
    Read-only SQLite health summary for App Health.

    Important:
    - JSON remains the source of truth.
    - SQLite is still a mirror/foundation layer.
    - This helper should not make Flask depend on SQLite being perfect.
    """
    if collect_diagnostics is None:
        return {
            "ok": False,
            "available": False,
            "summary": "SQLite diagnostics unavailable",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation",
            "errors": ["Diagnostics module could not be imported."],
        }

    try:
        diagnostics = collect_diagnostics()
    except Exception as exc:
        return {
            "ok": False,
            "available": False,
            "summary": "SQLite diagnostics failed",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation",
            "errors": [str(exc)],
        }

    table_counts = diagnostics.get("tables", {})
    sources = diagnostics.get("sources", [])

    return {
        "ok": bool(diagnostics.get("ok")),
        "available": bool(diagnostics.get("database_exists")),
        "summary": "SQLite mirror healthy" if diagnostics.get("ok") else "SQLite mirror needs attention",
        "database": diagnostics.get("database"),
        "database_size_bytes": diagnostics.get("database_size_bytes"),
        "integrity_check": diagnostics.get("integrity_check"),
        "journal_mode": diagnostics.get("journal_mode"),
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
        "table_counts": table_counts,
        "sources": sources,
        "errors": diagnostics.get("errors", []),
        "warnings": diagnostics.get("warnings", []),
        "checked_at": diagnostics.get("checked_at"),
    }
PY

echo
echo "3) Patching app.py with safe App Health SQLite context..."

python - <<'PY'
from pathlib import Path

path = Path("app.py")
text = path.read_text()

import_block = "from intelligence.app_health_sqlite import get_sqlite_health_for_app\n"

if import_block not in text:
    lines = text.splitlines()
    insert_at = 0

    # Put after existing imports.
    for i, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            insert_at = i + 1

    lines.insert(insert_at, import_block.rstrip())
    text = "\n".join(lines) + "\n"

if "def app_health_sqlite_status():" not in text:
    add_block = '''

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
'''
    text += add_block

path.write_text(text)
print("Patched app.py import/helper.")
PY

echo
echo "4) Looking for App Health template..."

APP_HEALTH_TEMPLATE=""
for f in templates/*.html; do
  if grep -qi "App Health\|backup\|health" "$f"; then
    APP_HEALTH_TEMPLATE="$f"
    break
  fi
done

if [ -z "$APP_HEALTH_TEMPLATE" ]; then
  echo "No obvious App Health template found. Creating reusable partial only."
else
  echo "Found likely App Health template: $APP_HEALTH_TEMPLATE"
fi

echo
echo "5) Creating reusable SQLite status partial..."

cat > templates/_sqlite_health_card.html <<'HTML'
<section class="card sqlite-health-card" id="sqlite-health-card">
  <h2>SQLite Foundation</h2>
  <p class="muted">
    SQLite is currently a mirror/read-only foundation. JSON remains the source of truth.
  </p>

  {% if sqlite_health %}
    <div class="health-grid">
      <div>
        <strong>Status</strong><br>
        {% if sqlite_health.ok %}
          <span class="status-good">Healthy</span>
        {% else %}
          <span class="status-warn">Needs attention</span>
        {% endif %}
      </div>

      <div>
        <strong>Database</strong><br>
        <span>{{ sqlite_health.database or "Not available" }}</span>
      </div>

      <div>
        <strong>Integrity</strong><br>
        <span>{{ sqlite_health.integrity_check or "Unknown" }}</span>
      </div>

      <div>
        <strong>Journal</strong><br>
        <span>{{ sqlite_health.journal_mode or "Unknown" }}</span>
      </div>
    </div>

    {% if sqlite_health.table_counts %}
      <details class="health-details">
        <summary>SQLite table counts</summary>
        <ul>
          {% for table, count in sqlite_health.table_counts.items() %}
            <li>{{ table }}: {{ count }}</li>
          {% endfor %}
        </ul>
      </details>
    {% endif %}

    {% if sqlite_health.sources %}
      <details class="health-details">
        <summary>Mirrored JSON sources</summary>
        <ul>
          {% for source in sqlite_health.sources %}
            <li>
              {{ source.logical_name }}:
              {{ source.row_count }} rows,
              source={{ source.source_of_truth }},
              loaded={{ source.last_loaded_at }}
            </li>
          {% endfor %}
        </ul>
      </details>
    {% endif %}

    {% if sqlite_health.warnings %}
      <details class="health-details">
        <summary>SQLite warnings</summary>
        <ul>
          {% for warning in sqlite_health.warnings %}
            <li>{{ warning }}</li>
          {% endfor %}
        </ul>
      </details>
    {% endif %}

    {% if sqlite_health.errors %}
      <details class="health-details">
        <summary>SQLite errors</summary>
        <ul>
          {% for error in sqlite_health.errors %}
            <li>{{ error }}</li>
          {% endfor %}
        </ul>
      </details>
    {% endif %}
  {% else %}
    <p class="status-warn">SQLite health data unavailable.</p>
  {% endif %}
</section>
HTML

echo
echo "6) Adding CSS for the card if not already present..."

cat >> static/css/style.css <<'CSS'

/* v4.5.1b SQLite Foundation card in App Health */
.sqlite-health-card {
  margin-top: 1rem;
}

.sqlite-health-card .muted {
  opacity: 0.78;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
  margin: 0.75rem 0;
}

.health-grid > div {
  padding: 0.75rem;
  border-radius: 0.75rem;
  background: rgba(255, 255, 255, 0.06);
}

.status-good {
  font-weight: 700;
}

.status-warn {
  font-weight: 700;
}

.health-details {
  margin-top: 0.5rem;
}
CSS

echo
echo "7) Attempting safe template insertion..."

if [ -n "$APP_HEALTH_TEMPLATE" ]; then
  python - <<PY
from pathlib import Path

path = Path("$APP_HEALTH_TEMPLATE")
text = path.read_text()

include = '{% include "_sqlite_health_card.html" %}'

if include not in text:
    # Prefer inserting before closing main/container/body if present.
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
    print(f"Inserted SQLite health partial into {path}")
else:
    print(f"SQLite health partial already present in {path}")
PY
else
  echo "Skipped template insertion because App Health template was not identified."
fi

echo
echo "8) Patching App Health route render context if obvious..."

python - <<'PY'
from pathlib import Path
import re

path = Path("app.py")
text = path.read_text()

# Add sqlite_health=app_health_sqlite_status() to render_template calls
# that appear related to health/backup.
pattern = re.compile(
    r"render_template\(([^)]*(?:health|backup|app_health)[^)]*)\)",
    flags=re.IGNORECASE | re.DOTALL,
)

def repl(match):
    call_inside = match.group(1)
    full = match.group(0)

    if "sqlite_health" in full:
        return full

    # Add as final kwarg before closing paren.
    if call_inside.rstrip().endswith(","):
        new_inside = call_inside + "\n        sqlite_health=app_health_sqlite_status(),"
    else:
        new_inside = call_inside + ",\n        sqlite_health=app_health_sqlite_status()"

    return f"render_template({new_inside})"

new_text = pattern.sub(repl, text)

if new_text != text:
    path.write_text(new_text)
    print("Patched likely App Health render_template context.")
else:
    print("No obvious App Health render_template call patched automatically.")
    print("If the card does not show, we will manually wire sqlite_health into the App Health route.")
PY

echo
echo "9) Writing QC for v4.5.1b..."

cat > tools/qc_v4_5_1b_app_health_sqlite.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

errors = []

app_py = APP_ROOT / "app.py"
template_partial = APP_ROOT / "templates" / "_sqlite_health_card.html"
helper = APP_ROOT / "intelligence" / "app_health_sqlite.py"

try:
    ast.parse(app_py.read_text())
except SyntaxError as exc:
    errors.append(f"app.py syntax error: {exc}")

try:
    ast.parse(helper.read_text())
except SyntaxError as exc:
    errors.append(f"app_health_sqlite.py syntax error: {exc}")

if not template_partial.exists():
    errors.append("Missing templates/_sqlite_health_card.html")

app_text = app_py.read_text()
if "get_sqlite_health_for_app" not in app_text:
    errors.append("app.py does not import/use get_sqlite_health_for_app")

if "app_health_sqlite_status" not in app_text:
    errors.append("app.py missing app_health_sqlite_status helper")

if "Admin" in template_partial.read_text():
    errors.append("SQLite health card should not mention Admin")

from intelligence.app_health_sqlite import get_sqlite_health_for_app
from tools.sqlite_diagnostics import collect_diagnostics

d = collect_diagnostics()
h = get_sqlite_health_for_app()

if not isinstance(h, dict):
    errors.append("get_sqlite_health_for_app did not return dict")

if h.get("json_source_of_truth") is not True:
    errors.append("sqlite health does not preserve JSON source-of-truth marker")

if "mirror" not in str(h.get("sqlite_role", "")).lower():
    errors.append("sqlite health role does not say mirror/read-only foundation")

if not d.get("ok"):
    errors.append("Underlying sqlite diagnostics are not passing")

if errors:
    print("QC FAILED: v4.5.1b App Health SQLite Status")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.5.1b App Health SQLite Status")
print("SQLite status helper is read-only and App Health oriented.")
PY

chmod +x tools/qc_v4_5_1b_app_health_sqlite.py

echo
echo "10) Writing version marker..."

cat > data/version_v4_5_1b_app_health_sqlite_status.json <<JSON
{
  "version": "v4.5.1b-app-health-sqlite-status",
  "previous": "v4.5.1a-sqlite-diagnostics",
  "json_source_of_truth": true,
  "sqlite_role": "mirror/read-only foundation",
  "admin_expanded": false,
  "admin_menu_restored": false,
  "app_health_maintenance_hub": true,
  "installed_at": "$(date -Iseconds)"
}
JSON

echo
echo "11) Running QC..."
python tools/qc_v4_5_sqlite.py
python tools/qc_v4_5_1a_sqlite_diagnostics.py
python tools/qc_v4_5_1b_app_health_sqlite.py

echo
echo "12) Restarting service..."
sudo systemctl restart angler-intel
sleep 2
sudo systemctl status angler-intel --no-pager -l | head -40

echo
echo "13) Git status..."
git status --short || true

echo
echo "=== v4.5.1b complete ==="
echo
echo "Open the app and check App Health."
echo
echo "Commit with:"
echo "git add app.py intelligence/app_health_sqlite.py templates/_sqlite_health_card.html static/css/style.css tools/qc_v4_5_1b_app_health_sqlite.py data/version_v4_5_1b_app_health_sqlite_status.json upgrade_v4_5_1b_app_health_sqlite_status.sh"
echo "git commit -m 'Add v4.5.1b App Health SQLite status'"
echo "git push"
