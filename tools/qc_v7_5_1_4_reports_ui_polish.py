#!/usr/bin/env python3
"""Focused static and route-contract QC for the V7.5.1.4 Saved Reports polish."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(text: str, needle: str, message: str, errors: list[str]) -> None:
    if needle not in text:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    reports = (ROOT / "templates" / "reports.html").read_text(encoding="utf-8")
    routes = (ROOT / "angler_reports_v38.py").read_text(encoding="utf-8")
    completion = (ROOT / "angler_trip_completion_v75.py").read_text(encoding="utf-8")
    drive = (ROOT / "integrations" / "google_drive.py").read_text(encoding="utf-8")
    for path in (ROOT / "angler_reports_v38.py", ROOT / "angler_trip_completion_v75.py", ROOT / "integrations" / "google_drive.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{path.name} syntax error: {exc}")
    for needle, message in (
        ("completionTripDate", "completion dialog is missing actual trip date"),
        ("completionStartedAt", "completion dialog is missing start time"),
        ("completionEndedAt", "completion dialog is missing end time"),
        ("completionWaterbodyOther", "completion dialog is missing other-water fallback"),
        ("completionSpeciesOther", "completion dialog is missing other-species fallback"),
        ("completionGearRod", "completion dialog is missing owned-gear selectors"),
        ("reportStatusBadges", "report cards are missing compact status badges"),
        ("data-drive-report", "report cards are missing Drive export action"),
        ("aria-live", "reports feedback is missing live-region support"),
        ("Remove from Saved Reports", "report removal wording is not soft-delete consistent"),
        ("archived SQLite history is retained", "bulk removal confirmation lacks retention explanation"),
        ("selectedOrOther", "completion submit does not preserve Other values"),
    ):
        require(reports, needle, message, errors)
    if ">Delete<" in reports or "Permanently delete all" in reports:
        errors.append("visible destructive wording remains in Saved Reports")
    require(routes, "_report_runtime_status", "report list does not expose runtime status", errors)
    require(routes, "report_export_status", "report list does not expose Drive state", errors)
    require(completion, "This legacy report has no stored Best Bet to link.", "legacy adherence wording missing", errors)
    require(completion, "authority markers need attention", "authority-aware adherence wording missing", errors)
    require(drive, "def report_export_status", "Drive status lookup missing", errors)
    if "Admin" in reports:
        errors.append("Saved Reports restored an Admin navigation reference")
    if errors:
        print("FAIL: " + "; ".join(errors))
        return 1
    print("PASS: V7.5.1.4 reports UI polish QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
