#!/usr/bin/env python3
"""Smoke checks for the App Health legacy-reference review surface."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app


def main() -> int:
    template = ROOT / "templates" / "v7_legacy_reference_review.html"
    assert template.exists() and template.stat().st_size > 0
    template_text = template.read_text(encoding="utf-8")
    # The live database may have no unresolved rows after reviewed decisions
    # were accepted, so verify the operator control in the template itself.
    assert "/app-health/legacy-references/decision" in template_text
    assert "Record reviewed decision" in template_text
    assert "original JSON catch unchanged" in template_text
    client = app.test_client()
    response = client.get("/app-health/legacy-references?page=999")
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Historical Reference Review" in text
    assert "Showing page" in text
    assert "/admin" not in text.lower()
    print("PASS: V7.3 legacy reference review UI QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
