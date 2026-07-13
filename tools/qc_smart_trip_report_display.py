#!/usr/bin/env python3
from __future__ import annotations

import ast
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


for rel in ("app.py", "templates/snapshot.html", "templates/index.html", "static/css/style.css"):
    require(rel)

app_path = APP_ROOT / "app.py"
if app_path.exists():
    try:
        ast.parse(app_path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append(f"app.py syntax error: {exc}")

snapshot_text = read("templates/snapshot.html") if (APP_ROOT / "templates/snapshot.html").exists() else ""
if "<details class=\"report-card report-debug-json\">" not in snapshot_text:
    errors.append("Trip report should keep a collapsed raw JSON debug section")
if "Raw saved JSON - debugging" not in snapshot_text:
    errors.append("Trip report debug section should be clearly labeled")

for needle in (
    "report-summary-grid",
    "report-condition-grid",
    "report-species-grid",
    "report-lure-grid",
    "report-outlook-table",
):
    if needle not in snapshot_text:
        errors.append(f"Trip report template should include {needle}")

from app import app as flask_app

client = flask_app.test_client()
response = client.get("/snapshot?zip=60543")
if response.status_code != 200:
    errors.append(f"/snapshot failed with HTTP {response.status_code}")
else:
    html = response.get_data(as_text=True)
    prefix = html.split("Raw saved JSON - debugging", 1)[0]
    for needle in ("lure_asset", "fish_image", "lure_image", "fallback_used", "filename", "species_score"):
        if needle in prefix:
            errors.append(f"Main report view still exposes {needle}")
    if "species-icon" not in html or "lure-art" not in html:
        errors.append("Trip report should render fish and lure artwork")
    if "report-outlook-table" not in html:
        errors.append("Trip report should render the 7-day outlook as a table")
    if "report-debug-json" not in html or "<details" not in html:
        errors.append("Trip report should keep the raw JSON in a collapsed details block")

index = client.get("/")
if index.status_code != 200:
    errors.append(f"Dashboard failed with HTTP {index.status_code}")

if "/admin" in snapshot_text or "/admin" in read("templates/index.html"):
    errors.append("Admin must not return to normal navigation")

if errors:
    print("QC FAILED: smart trip report display")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: smart trip report display")
