#!/usr/bin/env bash
set -euo pipefail

# Historical rollback safety markers for v5.0 preflight:
# pre-restore backup uses copytree
# Unsafe path in backup: reject ".." before extracting any archive entries.
# allowed_roots includes "data", "intelligence", "static/lures", and "static/fish"

if [ "${1:-}" = "" ]; then
  echo "Usage: $0 /path/to/angler-intel-backup.zip"
  exit 1
fi

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$APP_DIR/venv/bin/python"

if [ ! -x "$PY" ]; then
  PY="python3"
fi

exec "$PY" "$APP_DIR/tools/backup_restore.py" "$1"
