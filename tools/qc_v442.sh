#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/angler-intel"
cd "$APP_DIR"

PY="$APP_DIR/venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="python3"
fi

echo "========================================"
echo "Angler Intel IL v4.4.2 QC"
echo "========================================"
echo

echo "Git status"
echo "----------------------------------------"
git status --short || true
echo

echo "Sensitive tracked files check"
echo "----------------------------------------"
git ls-files | grep -E 'admin_token|favorites.json|catches.json|reports_index.json|backups/|reports/|venv|__pycache__|\.pyc' || echo "OK: no private/generated files tracked"
echo

echo "Python compile"
echo "----------------------------------------"
"$PY" -m py_compile \
  app.py \
  angler_exports_v37.py \
  angler_reports_v38.py \
  angler_health_v39.py \
  angler_admin_v310.py \
  angler_waters_v40.py \
  angler_species_rigs_v43.py \
  angler_cleanup_v431.py \
  angler_recommendations_v44.py
echo "OK: Python compiles"
echo

echo "JSON validation"
echo "----------------------------------------"
for f in \
  data/illinois_waters.json \
  data/species_profiles_v43.json \
  data/lure_rig_setups_v43.json \
  data/species_settings_v431.json \
  data/recommendation_rules_v44.json \
  data/app_version.json
do
  echo "Checking $f"
  "$PY" -m json.tool "$f" >/dev/null
done
echo "OK: JSON files valid"
echo

echo "Data validator"
echo "----------------------------------------"
if [ -x tools/validate_data.py ]; then
  "$PY" tools/validate_data.py || true
else
  echo "WARNING: tools/validate_data.py missing"
fi
echo

echo "Route checks"
echo "----------------------------------------"
for route in / /recommendations /waters /species /rigs /reports /data-tools /app-health /admin /exports; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' "http://localhost:5000$route" || true)"
  printf "%-18s -> HTTP %s\n" "$route" "$code"
done
echo

echo "API checks"
echo "----------------------------------------"
APIS=(
  "/health"
  "/api/version"
  "/api/data/validate"
  "/api/recommendations/status"
  "/api/recommendations?zip=60543&radius=35&limit=3&species=bass"
  "/api/recommendations?zip=60543&radius=50&limit=3&species=trout"
  "/api/recommendations?zip=60543&radius=50&limit=3&species=pike"
  "/api/waters?zip=60543&radius=35&limit=3"
  "/api/species/active"
  "/api/species/optional"
  "/api/rigs?species=trout"
)

for api in "${APIS[@]}"; do
  echo "Checking $api"
  body="$(curl -sS "http://localhost:5000$api" || true)"
  if echo "$body" | "$PY" -m json.tool >/dev/null 2>&1; then
    echo "  OK valid JSON"
  else
    echo "  WARNING invalid JSON or empty response"
    echo "$body" | head -5
  fi
done
echo

echo "UI script checks"
echo "----------------------------------------"
for route in / /recommendations /waters /species /rigs /reports /data-tools /app-health /admin /exports; do
  page="$(curl -sS "http://localhost:5000$route" || true)"

  if echo "$page" | grep -q "global_nav_v433.js"; then
    nav="nav OK"
  else
    nav="nav MISSING"
  fi

  if echo "$page" | grep -q "ui_polish_v442.js"; then
    polish="polish OK"
  else
    polish="polish MISSING"
  fi

  printf "%-18s -> %s, %s\n" "$route" "$nav" "$polish"
done
echo

echo "Service logs"
echo "----------------------------------------"
journalctl -u angler-intel -n 30 --no-pager || true
echo

echo "========================================"
echo "v4.4.2 QC complete"
echo "========================================"
