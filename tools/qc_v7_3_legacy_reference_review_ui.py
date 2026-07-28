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
    client = app.test_client()
    response = client.get("/app-health/legacy-references")
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Historical Reference Review" in text
    assert "Record reviewed decision" in text
    assert "JSON catch unchanged" in text
    assert "/admin" not in text.lower()
    print("PASS: V7.3 legacy reference review UI QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
