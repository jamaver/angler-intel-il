#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "Usage: $0 /path/to/angler-intel-backup.zip"
  exit 1
fi

BACKUP_ZIP="$1"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$APP_DIR/venv/bin/python"

if [ ! -x "$PY" ]; then
  PY="python3"
fi

cd "$APP_DIR"

"$PY" "$BACKUP_ZIP" <<'PY'
from pathlib import Path
from datetime import datetime
import shutil
import sys
import tempfile
import zipfile

base = Path.cwd()
zip_path = Path(sys.argv[1]).expanduser().resolve()

if not zip_path.exists():
    raise SystemExit(f"Backup not found: {zip_path}")

allowed_roots = {
    "data",
    "intelligence",
    "static/lures",
    "static/fish",
}

restore_pre_backup = base / "backups" / "pre-restore"
restore_pre_backup.mkdir(parents=True, exist_ok=True)

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
pre = restore_pre_backup / f"pre-restore-{stamp}"
pre.mkdir(parents=True, exist_ok=True)

for rel in allowed_roots:
    src = base / rel
    if src.exists():
        dst = pre / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)

with tempfile.TemporaryDirectory() as tmpdir:
    tmp = Path(tmpdir)

    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename

            if name.startswith("/") or ".." in Path(name).parts:
                raise SystemExit(f"Unsafe path in backup: {name}")

            if name.endswith("/"):
                continue

            parts = Path(name).parts
            root1 = parts[0] if parts else ""
            root2 = "/".join(parts[:2]) if len(parts) >= 2 else root1

            if root1 not in allowed_roots and root2 not in allowed_roots:
                continue

            zf.extract(info, tmp)

    for rel in allowed_roots:
        src = tmp / rel
        if not src.exists():
            continue

        dst = base / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()

        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

print(f"Restore complete from: {zip_path}")
print(f"Pre-restore backup saved at: {pre}")
PY
