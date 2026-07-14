#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
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


for rel in ("app.py", "angler_reports_v38.py", "templates/snapshot.html", "static/css/style.css"):
    require(rel)

for rel in ("app.py", "angler_reports_v38.py"):
    try:
        ast.parse(read(rel))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

snapshot_text = read("templates/snapshot.html")
if "selected_forecast_date" not in snapshot_text:
    errors.append("snapshot.html should render selected forecast date controls")
if "forecast-day-selected" not in snapshot_text:
    errors.append("snapshot.html should highlight the selected forecast day")
if "Trip date:" not in snapshot_text:
    errors.append("snapshot.html should surface the trip date in the header")

reports_page = read("angler_reports_v38.py")
if "forecastDateInput" not in reports_page or "loadForecastDates()" not in reports_page:
    errors.append("Saved reports page should expose a forecast date selector")

from app import app as flask_app

client = flask_app.test_client()
intel_res = client.get("/api/intel?zip=60543")
if intel_res.status_code != 200:
    errors.append(f"/api/intel failed with HTTP {intel_res.status_code}")
    print("QC FAILED: smart trip forecast date")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

intel = intel_res.get_json(silent=True) or {}
forecast = intel.get("forecast") if isinstance(intel, dict) else []
if not forecast:
    errors.append("No forecast data available for forecast-date QC")
    print("QC FAILED: smart trip forecast date")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

selected = forecast[1] if len(forecast) > 1 else forecast[0]
selected_date = selected.get("date")
selected_label = selected_date
if selected_date:
    try:
        selected_label = datetime.strptime(str(selected_date), "%Y-%m-%d").strftime("%A, %B %d, %Y")
    except Exception:
        selected_label = selected.get("pretty_date") or selected_date
if not selected_date:
    errors.append("Forecast rows do not include a selectable date")

reports_list_res = client.get("/reports")
if reports_list_res.status_code != 200:
    errors.append(f"/reports failed with HTTP {reports_list_res.status_code}")
else:
    reports_html = reports_list_res.get_data(as_text=True)
    if "forecastDateInput" not in reports_html or "loadForecastDates()" not in reports_html:
        errors.append("Saved reports page should expose a forecast date selector")

create_res = client.post(
    f"/api/reports/create?zip=60543&title=QC%20Forecast%20Date&selected_forecast_date={selected_date}",
)
if create_res.status_code != 200:
    errors.append(f"/api/reports/create with selected_forecast_date failed with HTTP {create_res.status_code}")
else:
    created = create_res.get_json(silent=True) or {}
    report = created.get("report") if isinstance(created, dict) else {}
    if report.get("selected_forecast_date") != selected_date:
        errors.append("Created report did not persist the selected forecast date")
    if not report.get("selected_forecast_label"):
        errors.append("Created report did not persist the selected forecast label")
    if report.get("forecast_day_index") in (None, ""):
        errors.append("Created report did not persist the forecast day index")

    view_url = report.get("view_url")
    if not view_url:
        errors.append("Created report missing view_url")
    else:
        view_res = client.get(view_url)
        if view_res.status_code != 200:
            errors.append(f"{view_url} failed with HTTP {view_res.status_code}")
        else:
            html = view_res.get_data(as_text=True)
            prefix = html.split("Raw saved JSON - debugging", 1)[0]
            for needle in ("Trip date:", selected_label, "forecast-day-selected", "selected_forecast_date"):
                if needle not in html:
                    errors.append(f"Forecast-date report missing {needle}")
            for needle in ("lure_asset", "fish_image", "lure_image", "fallback_used", "species_score", "{\"date\":", "{'date':"):
                if needle in prefix:
                    errors.append(f"Main report still exposes {needle}")
            if "Trip Conditions" not in html or "Forecast date" not in html:
                errors.append("Report conditions should reflect the selected forecast day")

    html_file = report.get("html_file")
    if not html_file:
        errors.append("Created report missing html_file")
    else:
        html_path = Path("reports") / str(html_file)
        if not html_path.exists():
            errors.append(f"Saved HTML artifact missing: {html_file}")
        else:
            html = html_path.read_text(encoding="utf-8")
            prefix = html.split("Raw saved JSON - debugging", 1)[0]
            for needle in ("Trip date:", selected_label, "forecast-day-selected", "selected_forecast_date"):
                if needle not in html:
                    errors.append(f"Saved HTML artifact missing {needle}")
            for needle in ("lure_asset", "fish_image", "lure_image", "fallback_used", "species_score", "{\"date\":", "{'date':"):
                if needle in prefix:
                    errors.append(f"Saved HTML artifact still exposes {needle}")

old_payload = {
    "title": "QC Old Forecast Report",
    "zip": "60543",
    "saved_at": "2026-07-13T10:00:00",
    "intel": intel,
}
old_res = client.post("/api/reports/save", json=old_payload)
if old_res.status_code != 200:
    errors.append(f"/api/reports/save for old-style report failed with HTTP {old_res.status_code}")
else:
    saved = old_res.get_json(silent=True) or {}
    report = saved.get("report") if isinstance(saved, dict) else {}
    view_url = report.get("view_url")
    if not view_url:
        errors.append("Old-style report missing view_url")
    else:
        old_view = client.get(view_url)
        if old_view.status_code != 200:
            errors.append(f"Old-style report view failed with HTTP {old_view.status_code}")
        else:
            html = old_view.get_data(as_text=True)
            if "Trip date:" not in html:
                errors.append("Old-style report should still show a trip date fallback")
            if "forecast-day-selected" not in html:
                errors.append("Old-style report should still highlight a forecast day")

if "/admin" in snapshot_text or "/admin" in read("templates/index.html"):
    errors.append("Admin must not return to normal navigation")

if errors:
    print("QC FAILED: smart trip forecast date")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: smart trip forecast date")
