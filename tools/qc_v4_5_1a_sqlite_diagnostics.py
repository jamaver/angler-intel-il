#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from tools.sqlite_diagnostics import collect_diagnostics


d = collect_diagnostics()

if not d.get("ok"):
    print("QC FAILED: v4.5.1a SQLite diagnostics")
    for err in d.get("errors", []):
        print(f" - {err}")
    raise SystemExit(1)

print("QC PASSED: v4.5.1a SQLite diagnostics")
print(f"Database: {d['database']}")
print(f"Size: {d['database_size_bytes']} bytes")
print("JSON remains source of truth.")
