#!/usr/bin/env python3
"""Focused QC for restrained V7.4.4 analytics UI integration."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
    ast.parse(app)
    for needle in ("analyticsEvidence", "analyticsEvidenceBody", "analytics-evidence"):
        assert needle in template, f"dashboard template missing {needle}"
    assert '<details class="analytics-evidence"' in template, "analytics evidence must default collapsed"
    for needle in ("loadAnalyticsEvidence", "/api/analytics/personal", "/api/analytics/catch-water", "/api/analytics/lures", "/api/analytics/gear"):
        assert needle in js, f"dashboard JavaScript missing {needle}"
    for needle in ("analytics-evidence", "analytics-evidence-grid", "analytics-evidence-disclaimer"):
        assert needle in css, f"dashboard CSS missing {needle}"
    assert "Admin" not in template
    print("PASS: V7.4.4 restrained analytics UI QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
