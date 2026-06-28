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
