#!/usr/bin/env python3
"""Route and source-contract QC for the V8 application shell."""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    from app import app

    routes = ["/", "/map", "/waters", "/reports", "/rigs", "/recommendations", "/species", "/data-tools", "/app-health"]
    with app.test_client() as client:
        for route in routes:
            response = client.get(route)
            assert response.status_code == 200, (route, response.status_code)
            body = response.get_data(as_text=True)
            assert 'class="ai-nav"' in body
            if route != "/app-health":
                assert body.count('aria-label="Angler Intel primary navigation"') == 1
                assert '<nav class="ai-main-tabs"' not in body
    for template in ("index.html", "map.html", "waters.html", "reports.html", "tackle_locker.html", "recommendations.html", "water.html"):
        body = (ROOT / "templates" / template).read_text()
        assert '{% include "_nav.html" %}' in body, template
        assert "Current release:" not in body, f"routine release line remains in {template}"
    assert "<style>" not in (ROOT / "templates/waters.html").read_text()
    assert "<style>" not in (ROOT / "templates/reports.html").read_text()
    assert "id=\"primaryTargetSpecies\"" in (ROOT / "templates/index.html").read_text()
    dashboard = (ROOT / "templates/index.html").read_text()
    for required in ("tripPlan", "smartIntelligence", "adaptivePattern", "offeringIntelligence", "lureCards"):
        assert required in dashboard
    css = (ROOT / "static/css/style.css").read_text()
    for token in ("--ai-bg", "--ai-surface", ".ai-nav", ".ai-nav-mobile", "@media (max-width: 700px)"):
        assert token in css
    assert "Admin" not in dashboard
    assert not re.search(r"<select[^>]+multiple", dashboard, re.I)
    nav = (ROOT / "templates/_nav.html").read_text()
    for label in ("Today", "Map", "Waters", "Trips", "Gear", "More", "Smart Picks", "Species Guide", "Data Tools", "App Health"):
        assert label in nav
    assert "application_shell.js" in nav
    for template in ("index.html", "map.html", "waters.html", "reports.html", "tackle_locker.html", "recommendations.html"):
        assert "global_nav_v433.js" not in (ROOT / "templates" / template).read_text(), template
    for module in ("angler_species_rigs_v43.py", "angler_cleanup_v431.py", "angler_health_v39.py", "angler_exports_v37.py"):
        source = (ROOT / module).read_text()
        assert "render_template(\"_nav.html\")" in source, module
        assert '<nav class="ai-nav"' not in source, f"duplicated nav in {module}"
        assert "global_nav_v433.js" not in source, f"legacy injector in {module}"
    assert ast.parse((ROOT / "app.py").read_text())
    print("PASS: V8.0 application shell QC (9 routes)")


if __name__ == "__main__":
    run()
