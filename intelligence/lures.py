from __future__ import annotations

from intelligence.lure_assets import resolve_lure_asset

LURE_DB = {
    "topwater": {
        "name": "Topwater frog or popper",
        "type": "topwater_popper",
        "color": "bone",
        "speed": "Slow to medium",
        "size": "2-3 in",
        "colors": ["Black", "Bone", "Green", "White"],
        "why": "Best around surface weeds, shade, and low-light feeding windows.",
    },
    "spinnerbait": {
        "name": "White/chartreuse spinnerbait",
        "type": "spinnerbait",
        "color": "chartreuse_white",
        "speed": "Medium speed",
        "size": "3/8 oz",
        "colors": ["White", "Chartreuse", "Gold", "Bluegill"],
        "why": "Great search bait when wind, clouds, or stained water help fish feed shallow.",
    },
    "texas_rig": {
        "name": "Texas rig worm or jig",
        "type": "soft_plastic_worm",
        "color": "green_pumpkin",
        "speed": "Slow speed",
        "size": "4-7 in",
        "colors": ["Green pumpkin", "Black/blue", "Junebug", "Watermelon"],
        "why": "Best when fish slow down around cover, docks, weeds, or bottom structure.",
    },
    "crappie_jig": {
        "name": "Small tube jig",
        "type": "jig",
        "color": "white_shad",
        "speed": "Slow speed",
        "size": "1/32-1/16 oz",
        "colors": ["White", "Chartreuse", "Pink", "Glow"],
        "why": "Good around brush, docks, laydowns, and suspended panfish.",
    },
    "minnow_float": {
        "name": "Minnow under slip float",
        "type": "swimbait",
        "color": "shad",
        "speed": "Dead slow",
        "size": "1-2 in",
        "colors": ["Natural", "Silver", "White"],
        "why": "Keeps bait in the strike zone when crappie are suspended or neutral.",
    },
    "micro_jig": {
        "name": "Micro jig",
        "type": "jig",
        "color": "green_pumpkin",
        "speed": "Slow speed",
        "size": "1/64-1/32 oz",
        "colors": ["Red", "Natural", "Black", "Chartreuse"],
        "why": "Ideal for bluegill and panfish when they are feeding near weeds or shallow cover.",
    },
    "catfish_bait": {
        "name": "Cut bait / stink bait",
        "type": "generic",
        "color": "generic",
        "speed": "Still bait",
        "size": "Hook size 2/0-5/0",
        "colors": ["Natural"],
        "why": "Best near bottom, current seams, deep holes, and evening feeding routes.",
    },
    "walleye_jig": {
        "name": "Jig and minnow",
        "type": "jig",
        "color": "brown_orange_craw",
        "speed": "Slow lift/drop",
        "size": "1/8-1/4 oz",
        "colors": ["Gold", "Silver", "Firetiger", "White"],
        "why": "Good for walleye and sauger near current, rocks, and low-light edges.",
    },
    "spoon": {
        "name": "Small spoon / inline spinner",
        "type": "spoon",
        "color": "silver",
        "speed": "Medium speed",
        "size": "1/8-1/4 oz",
        "colors": ["Silver", "Gold", "Orange", "Rainbow"],
        "why": "Good for trout, pike, and aggressive fish in cooler water.",
    },
    "default": {
        "name": "Soft plastic",
        "type": "soft_plastic_worm",
        "color": "green_pumpkin",
        "speed": "Slow speed",
        "size": "3-5 in",
        "colors": ["Green pumpkin", "Natural", "Black", "White"],
        "why": "Reliable general-purpose option when fish activity is uncertain.",
    },
}


def _with_asset(entry: dict[str, object]) -> dict[str, object]:
    asset = resolve_lure_asset(
        recommendation_text=entry.get("name"),
        lure_type=entry.get("type"),
        color=entry.get("color"),
    )
    return {
        **entry,
        "image": asset["path"],
        "lure_asset": asset,
    }


def lure_plan(species_name):
    if "Bass" in species_name and "White" not in species_name:
        return {
            "morning": _with_asset(LURE_DB["topwater"]),
            "midday": _with_asset(LURE_DB["texas_rig"]),
            "evening": _with_asset(LURE_DB["spinnerbait"]),
        }

    if "Crappie" in species_name:
        return {
            "morning": _with_asset(LURE_DB["crappie_jig"]),
            "midday": _with_asset(LURE_DB["minnow_float"]),
            "evening": _with_asset(LURE_DB["crappie_jig"]),
        }

    if "Bluegill" in species_name:
        return {
            "morning": _with_asset(LURE_DB["micro_jig"]),
            "midday": _with_asset(LURE_DB["micro_jig"]),
            "evening": _with_asset(LURE_DB["topwater"]),
        }

    if "Catfish" in species_name:
        return {
            "morning": _with_asset(LURE_DB["catfish_bait"]),
            "midday": _with_asset(LURE_DB["catfish_bait"]),
            "evening": _with_asset(LURE_DB["catfish_bait"]),
        }

    if "Walleye" in species_name or "Sauger" in species_name:
        return {
            "morning": _with_asset(LURE_DB["walleye_jig"]),
            "midday": _with_asset(LURE_DB["walleye_jig"]),
            "evening": _with_asset(LURE_DB["spinnerbait"]),
        }

    if "Trout" in species_name:
        return {
            "morning": _with_asset(LURE_DB["spoon"]),
            "midday": _with_asset(LURE_DB["catfish_bait"]),
            "evening": _with_asset(LURE_DB["spoon"]),
        }

    if "Pike" in species_name or "Muskie" in species_name:
        return {
            "morning": _with_asset(LURE_DB["spinnerbait"]),
            "midday": _with_asset(LURE_DB["spoon"]),
            "evening": _with_asset(LURE_DB["topwater"]),
        }

    return {
        "morning": _with_asset(LURE_DB["default"]),
        "midday": _with_asset(LURE_DB["default"]),
        "evening": _with_asset(LURE_DB["spinnerbait"]),
    }


def choose_lure(species_name):
    plan = lure_plan(species_name)
    return {
        "morning": plan["morning"]["name"],
        "midday": plan["midday"]["name"],
        "evening": plan["evening"]["name"],
        "cards": plan,
    }

