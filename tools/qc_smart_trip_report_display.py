#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
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


def strip_debug_section(html: str) -> str:
    marker = "Raw saved JSON - debugging"
    if marker not in html:
        return html
    return html.split(marker, 1)[0]


def pick_report_id() -> str | None:
    index_path = APP_ROOT / "data" / "reports_index.json"
    if index_path.exists():
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                preferred = next(
                    (
                        item.get("id")
                        for item in payload
                        if isinstance(item, dict) and item.get("id") == "20260712-202630-trip-report-zip-60543-7f9e27"
                    ),
                    None,
                )
                if preferred:
                    return str(preferred)
                for item in payload:
                    if isinstance(item, dict) and item.get("id"):
                        return str(item["id"])
        except Exception:
            pass
    reports_dir = APP_ROOT / "reports"
    if reports_dir.exists():
        for path in sorted(reports_dir.glob("*.json")):
            if path.stem:
                return path.stem
    return None


for rel in ("app.py", "angler_reports_v38.py", "templates/snapshot.html", "templates/index.html", "static/css/style.css"):
    require(rel)

for rel in ("app.py", "angler_reports_v38.py"):
    path = APP_ROOT / rel
    if path.exists():
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

snapshot_text = read("templates/snapshot.html") if (APP_ROOT / "templates/snapshot.html").exists() else ""
if "<details class=\"report-card report-debug-json\">" not in snapshot_text:
    errors.append("Trip report should keep a collapsed raw JSON debug section")
if "Raw saved JSON - debugging" not in snapshot_text:
    errors.append("Trip report debug section should be clearly labeled")

if not re.search(r"\.report-species-grid\s*\{[^}]*grid-template-columns:\s*1fr;", snapshot_text, re.S):
    errors.append("Trip report species ranking should use a single-column grid")
if not re.search(r"\.report-lure-grid\s*\{[^}]*grid-template-columns:\s*1fr;", snapshot_text, re.S):
    errors.append("Trip report lure recommendations should use a single-column grid")

from app import app as flask_app

client = flask_app.test_client()
report_id = pick_report_id()
if not report_id:
    errors.append("Could not find an existing trip report to inspect")
else:
    view_res = client.get(f"/api/reports/view/{report_id}")
    if view_res.status_code != 200:
        errors.append(f"/api/reports/view/{report_id} failed with HTTP {view_res.status_code}")
    else:
        html = view_res.get_data(as_text=True)
        prefix = strip_debug_section(html)
        for needle in ("lure_asset", "fish_image", "lure_image", "fallback_used", "filename", "species_score", "best_hour", "{\"date\":", "{'date':", "{\"fish_image\"", "{\"color\""):
            if needle in prefix:
                errors.append(f"Main report view still exposes {needle}")
        for needle in ("Best Bet Today", "Trip Conditions", "Species Ranking", "Recommended Lures", "7-Day Fishing Outlook"):
            if needle not in html:
                errors.append(f"Missing report section: {needle}")
        for needle in ("Species:", "Best Time:", "Lure:", "Why:"):
            if needle not in html:
                errors.append(f"Missing friendly best-bet label: {needle}")
        if "report-debug-json" not in html or "<details" not in html:
            errors.append("Trip report should keep the raw JSON in a collapsed details block")
        if 'src="/static/fish/largemouth_bass.png"' not in html and "species-icon" not in html:
            errors.append("Trip report should render fish artwork via image src")
        if 'src="/static/lures/spinnerbait/chartreuse_white.png"' not in html and "lure-art" not in html:
            errors.append("Trip report should render lure artwork via image src")
        if "report-outlook-table" not in html or "<table" not in html:
            errors.append("Trip report should render the 7-day outlook as a table")
        if "Raw saved JSON - debugging" not in html:
            errors.append("Trip report should include the raw JSON debug label")

if client.get("/").status_code != 200:
    errors.append("Dashboard failed to load")

if "/admin" in snapshot_text or "/admin" in read("templates/index.html"):
    errors.append("Admin must not return to normal navigation")

if errors:
    print("QC FAILED: smart trip report display")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: smart trip report display")
