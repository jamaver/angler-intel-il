#!/usr/bin/env python3
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

errors: list[str] = []


def read(rel: str) -> str:
    return (APP_ROOT / rel).read_text(encoding="utf-8")


def require(rel: str) -> None:
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
    elif path.stat().st_size <= 0:
        errors.append(f"Empty {rel}")


for rel in (
    "app.py",
    "templates/index.html",
    "templates/water.html",
    "static/js/app.js",
    "static/css/style.css",
):
    require(rel)

path = APP_ROOT / "app.py"
if path.exists():
    try:
        ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append(f"app.py syntax error: {exc}")

js_path = APP_ROOT / "static/js/app.js"
if js_path.exists():
    node = subprocess.run(["node", "--check", str(js_path)], capture_output=True, text=True)
    if node.returncode != 0:
        errors.append(f"static/js/app.js syntax error: {node.stderr.strip() or node.stdout.strip()}")

index_text = read("templates/index.html") if (APP_ROOT / "templates/index.html").exists() else ""
water_text = read("templates/water.html") if (APP_ROOT / "templates/water.html").exists() else ""
js_text = read("static/js/app.js") if (APP_ROOT / "static/js/app.js").exists() else ""
css_text = read("static/css/style.css") if (APP_ROOT / "static/css/style.css").exists() else ""

for needle, message in (
    ("dashboard-primary-grid", "Dashboard should use the new primary grid"),
    ("dashboard-secondary-grid", "Dashboard should use the new secondary grid"),
    ("section-head", "Dashboard should use section headers"),
    ("dashboard-status-card", "Dashboard status card should remain present"),
    ("App Health", "Dashboard should preserve App Health navigation"),
):
    if needle not in index_text:
        errors.append(message)

for needle, message in (
    ("intel-shell", "Smart Intelligence should render inside an intel shell"),
    ("intel-score-card", "Smart Intelligence should expose the score card"),
    ("intel-quad-grid", "Smart Intelligence should expose the four-up grid"),
    ("water-hero-copy", "Water detail hero should use the cleaner copy wrapper"),
    ("section-head", "Water detail should use section headers"),
):
    if needle not in js_text + water_text + css_text:
        errors.append(message)

if "/admin" in index_text or "/admin" in water_text:
    errors.append("Admin must not return to normal navigation")

from app import app as flask_app

client = flask_app.test_client()
for path in ("/", "/map", "/waters", "/reports"):
    response = client.get(path)
    if response.status_code != 200:
        errors.append(f"{path} failed with HTTP {response.status_code}")

if errors:
    print("QC FAILED: ui cleanup preview")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: ui cleanup preview")
