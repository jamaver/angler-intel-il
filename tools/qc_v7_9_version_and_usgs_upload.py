#!/usr/bin/env python3
"""QC release labeling and maintenance-only USGS key upload behavior."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import app  # noqa: E402


def run():
    client = app.test_client()
    expected = "v7.9.0-environmental-evidence"
    for route in ("/", "/map", "/waters", "/reports", "/recommendations", "/rigs", "/app-health"):
        response = client.get(route)
        assert response.status_code == 200, f"{route} returned {response.status_code}"
        assert expected in response.get_data(as_text=True), f"{route} does not show current release"
    invalid = client.post("/api/app-health/usgs-key", json={"api_key": "invalid"})
    assert invalid.status_code == 400
    body = invalid.get_data(as_text=True)
    assert "AI_USGS_API_KEY" not in body and "c2tGm" not in body
    source = (ROOT / "app.py").read_text()
    assert "os.replace" in source and "USGS_ENV_FILE" in source
    assert "SQLite" not in body
    print("PASS: V7.9 version and USGS upload QC")


if __name__ == "__main__":
    run()
