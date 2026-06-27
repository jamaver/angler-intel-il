#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$APP_DIR/venv/bin/python"

if [ ! -x "$PY" ]; then
  PY="python3"
fi

cd "$APP_DIR"

"$PY" <<'PY'
from pathlib import Path
from datetime import datetime
import json
import zipfile

base = Path.cwd()
backup_dir = base / "backups" / "user-data"
backup_dir.mkdir(parents=True, exist_ok=True)

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
out = backup_dir / f"angler-intel-cli-backup-{stamp}.zip"

paths = [
    base / "data",
    base / "intelligence",
    base / "static" / "lures",
    base / "static" / "fish",
]

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("manifest.json", json.dumps({
        "app": "Angler Intel IL",
        "backup_version": "v3.7-cli",
        "created": datetime.now().isoformat(timespec="seconds"),
    }, indent=2))

    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            zf.write(path, path.relative_to(base).as_posix())
        else:
            for child in path.rglob("*"):
                if child.is_file():
                    zf.write(child, child.relative_to(base).as_posix())

print(out)
PY
