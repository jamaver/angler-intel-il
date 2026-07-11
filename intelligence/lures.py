LURE_DB = {
    "topwater": {
        "name": "Topwater frog or popper",
        "image": "/static/icons/lures/topwater_popper.svg",
        "speed": "Slow to medium",
        "size": "2-3 in",
        "colors": ["Black", "Bone", "Green", "White"],
        "why": "Best around surface weeds, shade, and low-light feeding windows."
    },
    "spinnerbait": {
        "name": "White/chartreuse spinnerbait",
        "image": "/static/icons/lures/spinnerbait.svg",
        "speed": "Medium speed",
        "size": "3/8 oz",
        "colors": ["White", "Chartreuse", "Gold", "Bluegill"],
        "why": "Great search bait when wind, clouds, or stained water help fish feed shallow."
    },
    "texas_rig": {
        "name": "Texas rig worm or jig",
        "image": "/static/icons/lures/soft_plastic_worm.svg",
        "speed": "Slow speed",
        "size": "4-7 in",
        "colors": ["Green pumpkin", "Black/blue", "Junebug", "Watermelon"],
        "why": "Best when fish slow down around cover, docks, weeds, or bottom structure."
    },
    "crappie_jig": {
        "name": "Small tube jig",
        "image": "/static/icons/lures/jig.svg",
        "speed": "Slow speed",
        "size": "1/32-1/16 oz",
        "colors": ["White", "Chartreuse", "Pink", "Glow"],
        "why": "Good around brush, docks, laydowns, and suspended panfish."
    },
    "minnow_float": {
        "name": "Minnow under slip float",
        "image": "/static/icons/lures/bobber_live_bait.svg",
        "speed": "Dead slow",
        "size": "1-2 in",
        "colors": ["Natural", "Silver", "White"],
        "why": "Keeps bait in the strike zone when crappie are suspended or neutral."
    },
    "micro_jig": {
        "name": "Micro jig",
        "image": "/static/icons/lures/jig.svg",
        "speed": "Slow speed",
        "size": "1/64-1/32 oz",
        "colors": ["Red", "Natural", "Black", "Chartreuse"],
        "why": "Ideal for bluegill and panfish when they are feeding near weeds or shallow cover."
    },
    "catfish_bait": {
        "name": "Cut bait / stink bait",
        "image": "/static/icons/lures/bobber_live_bait.svg",
        "speed": "Still bait",
        "size": "Hook size 2/0-5/0",
        "colors": ["Natural"],
        "why": "Best near bottom, current seams, deep holes, and evening feeding routes."
    },
    "walleye_jig": {
        "name": "Jig and minnow",
        "image": "/static/icons/lures/drop_shot.svg",
        "speed": "Slow lift/drop",
        "size": "1/8-1/4 oz",
        "colors": ["Gold", "Silver", "Firetiger", "White"],
        "why": "Good for walleye and sauger near current, rocks, and low-light edges."
    },
    "spoon": {
        "name": "Small spoon / inline spinner",
        "image": "/static/icons/lures/spoon.svg",
        "speed": "Medium speed",
        "size": "1/8-1/4 oz",
        "colors": ["Silver", "Gold", "Orange", "Rainbow"],
        "why": "Good for trout, pike, and aggressive fish in cooler water."
    },
    "default": {
        "name": "Soft plastic",
        "image": "/static/icons/lures/generic_lure.svg",
        "speed": "Slow speed",
        "size": "3-5 in",
        "colors": ["Green pumpkin", "Natural", "Black", "White"],
        "why": "Reliable general-purpose option when fish activity is uncertain."
    }
}

def lure_plan(species_name):
    if "Bass" in species_name and "White" not in species_name:
        return {
            "morning": LURE_DB["topwater"],
            "midday": LURE_DB["texas_rig"],
            "evening": LURE_DB["spinnerbait"]
        }

    if "Crappie" in species_name:
        return {
            "morning": LURE_DB["crappie_jig"],
            "midday": LURE_DB["minnow_float"],
            "evening": LURE_DB["crappie_jig"]
        }

    if "Bluegill" in species_name:
        return {
            "morning": LURE_DB["micro_jig"],
            "midday": LURE_DB["micro_jig"],
            "evening": LURE_DB["topwater"]
        }

    if "Catfish" in species_name:
        return {
            "morning": LURE_DB["catfish_bait"],
            "midday": LURE_DB["catfish_bait"],
            "evening": LURE_DB["catfish_bait"]
        }

    if "Walleye" in species_name or "Sauger" in species_name:
        return {
            "morning": LURE_DB["walleye_jig"],
            "midday": LURE_DB["walleye_jig"],
            "evening": LURE_DB["spinnerbait"]
        }

    if "Trout" in species_name:
        return {
            "morning": LURE_DB["spoon"],
            "midday": LURE_DB["catfish_bait"],
            "evening": LURE_DB["spoon"]
        }

    if "Pike" in species_name or "Muskie" in species_name:
        return {
            "morning": LURE_DB["spinnerbait"],
            "midday": LURE_DB["spoon"],
            "evening": LURE_DB["topwater"]
        }

    return {
        "morning": LURE_DB["default"],
        "midday": LURE_DB["default"],
        "evening": LURE_DB["spinnerbait"]
    }

def choose_lure(species_name):
    plan = lure_plan(species_name)
    return {
        "morning": plan["morning"]["name"],
        "midday": plan["midday"]["name"],
        "evening": plan["evening"]["name"],
        "cards": plan
    }
