from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

V7_AUTHORITY = "json"

V7_DOMAINS = (
    "species",
    "waters",
    "manual_waters",
    "target_profile",
    "saved_locations",
    "gear_inventory",
    "gear_settings",
    "gear_catalog_cache",
    "catches",
    "favorites",
    "reports",
    "reports_index",
    "recommendations",
    "forecast",
    "intelligence",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_authority_map() -> dict[str, dict[str, Any]]:
    now = utc_now()
    return {
        domain: {
            "domain": domain,
            "authority": V7_AUTHORITY,
            "note": "JSON remains authoritative in V7.0",
            "updated_at": now,
        }
        for domain in V7_DOMAINS
    }
