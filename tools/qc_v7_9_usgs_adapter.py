#!/usr/bin/env python3
"""Offline QC for the optional modern USGS adapter."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from integrations import usgs_water  # noqa: E402


def run():
    os.environ.pop("AI_USGS_API_KEY", None)
    config = usgs_water.settings()
    assert config["enabled"] and not config["api_key_configured"]
    assert "AI_USGS_API_KEY" not in str(usgs_water.health())
    feature = {"type": "Feature", "geometry": {"coordinates": [-88.2, 41.7]}, "properties": {"monitoring_location_number": "05500000", "monitoring_location_name": "Example River", "parameter_code": "00060", "value": "1420", "unit_of_measure": "ft3/s", "time": "2026-09-02T12:00:00Z"}}
    with patch.object(usgs_water, "_request", return_value={"features": [feature]}):
        stations = usgs_water.discover_stations(41.7, -88.2, radius_miles=15, parameter_code="00060")
    assert stations and stations[0]["connection_quality"] == "direct_nearby"
    assert "waterservices.usgs.gov" not in Path(ROOT / "integrations/usgs_water.py").read_text()
    print("PASS: V7.9 USGS adapter QC")


if __name__ == "__main__":
    run()
