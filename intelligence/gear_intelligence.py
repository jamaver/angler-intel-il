from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from gear.inventory import gear_item_label


def _text(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value or "").split()).strip()
    return text or fallback


def _as_float(value: Any, fallback: float | None = None) -> float | None:
    try:
        return float(str(value).strip())
    except Exception:
        return fallback


def _as_int(value: Any, fallback: int | None = None) -> int | None:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return fallback


def _compact(value: Any) -> str:
    return _text(value, "").lower().replace("-", "_").replace(" ", "_")


def _split_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_compact(item) for item in value if _compact(item)]
    return [_compact(part) for part in str(value or "").replace("\n", ",").split(",") if _compact(part)]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


SPECIES_ALIASES = {
    "bass": "largemouth_bass",
    "largemouth": "largemouth_bass",
    "largemouth_bass": "largemouth_bass",
    "smallmouth": "smallmouth_bass",
    "smallmouth_bass": "smallmouth_bass",
    "crappie": "crappie",
    "bluegill": "bluegill",
    "panfish": "bluegill",
    "catfish": "channel_catfish",
    "channel_catfish": "channel_catfish",
    "trout": "rainbow_trout",
    "rainbow_trout": "rainbow_trout",
    "walleye": "walleye",
    "sauger": "sauger",
    "white_bass": "white_bass",
    "white bass": "white_bass",
    "pike": "northern_pike",
    "northern_pike": "northern_pike",
    "musky": "northern_pike",
    "muskie": "northern_pike",
}


LURE_ALIASES = {
    "spinnerbait": "spinnerbait",
    "jig": "jig",
    "crankbait": "crankbait",
    "crank": "crankbait",
    "swimbait": "swimbait",
    "topwater": "topwater_popper",
    "popper": "topwater_popper",
    "frog": "frog",
    "spoon": "spoon",
    "spinner": "inline_spinner",
    "inline_spinner": "inline_spinner",
    "drop_shot": "drop_shot",
    "dropshot": "drop_shot",
    "worm": "soft_plastic_worm",
    "soft_plastic": "soft_plastic_worm",
}


def normalize_species_name(value: Any) -> str:
    text = _compact(value)
    return SPECIES_ALIASES.get(text, text.replace(" ", "_"))


def normalize_lure_type(value: Any) -> str:
    text = _compact(value)
    return LURE_ALIASES.get(text, text.replace(" ", "_"))


def _gear_label(item: dict[str, Any] | None) -> str:
    if not isinstance(item, dict):
        return ""
    return gear_item_label(item)


def _gear_category(item: dict[str, Any]) -> str:
    return _compact(item.get("category")) or "misc"


def _owned_items(owned_gear: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    items = [item for item in (owned_gear or []) if isinstance(item, dict)]
    owned = [item for item in items if _compact(item.get("status")) == "owned"]
    wishlist = [item for item in items if _compact(item.get("status")) == "wishlist"]
    return owned or wishlist or items


def _bucket_items(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        buckets[_gear_category(item)].append(item)
    for key in buckets:
        buckets[key].sort(key=lambda item: (
            bool(item.get("favorite")),
            _as_int(item.get("trips_used"), 0) or 0,
            _as_int(item.get("catches_logged"), 0) or 0,
            _text(item.get("updated_at"), _text(item.get("created_at"), "")),
        ), reverse=True)
    return buckets


def _condition_blob(conditions: dict[str, Any] | None) -> str:
    data = conditions if isinstance(conditions, dict) else {}
    return " ".join(_text(value) for value in data.values() if _text(value))


def _target_fish_context(target_species: str, expected_fish_weight: Any = None) -> dict[str, Any]:
    species = normalize_species_name(target_species)
    weight = _as_float(expected_fish_weight, None)
    return {"species": species, "expected_weight": weight}


def _species_weight_band(species: str) -> tuple[float | None, float | None]:
    species = normalize_species_name(species)
    return {
        "bluegill": (0.25, 1.0),
        "crappie": (0.5, 2.0),
        "walleye": (1.0, 5.0),
        "sauger": (1.0, 4.0),
        "rainbow_trout": (0.5, 4.0),
        "channel_catfish": (2.0, 20.0),
        "northern_pike": (2.0, 15.0),
        "white_bass": (1.0, 4.0),
        "smallmouth_bass": (1.0, 6.0),
        "largemouth_bass": (1.0, 8.0),
    }.get(species, (None, None))


def _score_band(value: float | None, low: float | None, high: float | None, *, tolerance: float = 0.25) -> tuple[int, str | None]:
    if value is None or (low is None and high is None):
        return 0, None
    if low is not None and high is not None and low <= value <= high:
        return 22, "Fits the expected size band."
    if low is not None and value < low:
        distance = low - value
        if distance <= max(low * tolerance, 0.5):
            return 10, "A little light for the expected fish size."
        return -8, "May run light for the expected fish size."
    if high is not None and value > high:
        distance = value - high
        if distance <= max(high * tolerance, 0.5):
            return 10, "A little heavy for the expected fish size."
        return -8, "May run heavy for the expected fish size."
    return 0, None


def _normalize_conditions(conditions: dict[str, Any] | None) -> dict[str, Any]:
    data = conditions if isinstance(conditions, dict) else {}
    return {
        "temperature": _as_float(data.get("temperature") or data.get("temp"), None),
        "wind_mph": _as_float(data.get("wind_mph") or data.get("wind"), None),
        "cloud_cover": _as_float(data.get("cloud_cover") or data.get("cloud"), None),
        "clarity": _compact(data.get("clarity") or data.get("water_clarity")),
        "time_of_day": _compact(data.get("time_of_day") or data.get("time")),
        "season": _compact(data.get("season")),
        "cover": _compact(data.get("cover")),
        "habitat": _compact(data.get("habitat")),
    }


def _score_rod(item: dict[str, Any], context: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    score = 45
    reasons: list[str] = []
    warnings: list[str] = []
    lure_weight = context.get("lure_weight_oz")
    expected_weight = context.get("expected_weight")
    species = context.get("species")
    technique = context.get("technique")
    habitat = context.get("habitat")
    cover = context.get("cover")

    min_w = _as_float(item.get("lure_weight_min_oz"), None)
    max_w = _as_float(item.get("lure_weight_max_oz"), None)
    if lure_weight is not None:
        if min_w is not None and max_w is not None and min_w <= lure_weight <= max_w:
            score += 22
            reasons.append("Rod lure rating covers the recommended lure weight.")
        elif min_w is not None and max_w is not None:
            if abs(lure_weight - min_w) <= 0.25 or abs(lure_weight - max_w) <= 0.25:
                score += 10
                reasons.append("Rod lure rating is close to the recommended lure weight.")
            else:
                score -= 8
                warnings.append("Rod lure rating may not fit the lure weight cleanly.")
        else:
            warnings.append("Rod lure rating is missing.")
    else:
        warnings.append("No lure weight was provided for this trip.")

    low, high = _species_weight_band(species)
    weight_score, weight_reason = _score_band(expected_weight, low, high)
    score += weight_score
    if weight_reason:
        reasons.append(weight_reason)

    species_tags = set(_split_tags(item.get("species_tags")))
    if species and species in species_tags:
        score += 16
        reasons.append(f"Species tag matches {species.replace('_', ' ')}.")

    techniques = set(_split_tags(item.get("technique_tags")))
    if technique and technique in techniques:
        score += 10
        reasons.append("Technique tag matches the current trip.")
    elif technique and any(token in techniques for token in {technique.replace(" ", "_"), technique.split("_")[0]}):
        score += 6

    power = _compact(item.get("power"))
    if species in {"largemouth_bass", "smallmouth_bass"} and power in {"medium_heavy", "heavy"}:
        score += 6
        reasons.append("Rod power matches bass-oriented cover work.")
    if species in {"bluegill", "crappie", "rainbow_trout", "walleye"} and power in {"light", "medium_light", "medium"}:
        score += 6
        reasons.append("Rod power suits lighter species work.")
    if cover in {"heavy_cover", "weeds", "vegetation"} and power in {"medium_heavy", "heavy"}:
        score += 5
    elif cover in {"open_water", "clear", "open"} and power in {"medium_light", "medium"}:
        score += 4

    action = _compact(item.get("action"))
    if technique in {"spinnerbait", "crankbait", "swimbait"} and action in {"fast", "moderate_fast"}:
        score += 5
    if technique in {"drop_shot", "finesse", "worm"} and action in {"fast", "extra_fast", "moderate_fast"}:
        score += 4
    if habitat in {"river", "creek", "current"} and _as_float(item.get("length_ft"), 0) and _as_float(item.get("length_ft"), 0) >= 6.6:
        score += 3

    if not item.get("lure_weight_min_oz") and not item.get("lure_weight_max_oz"):
        warnings.append("Rod lure rating is not fully specified.")

    return max(0, min(100, score)), reasons, warnings


def _score_reel(item: dict[str, Any], context: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    score = 42
    reasons: list[str] = []
    warnings: list[str] = []
    technique = context.get("technique")
    species = context.get("species")
    lure_type = context.get("lure_type")
    expected_weight = context.get("expected_weight")

    reel_type = _compact(item.get("reel_type"))
    gear_ratio = _as_float(item.get("gear_ratio"), None)
    drag = _as_float(item.get("max_drag_lb"), None)

    if species in {"rainbow_trout", "crappie", "bluegill", "walleye"} and reel_type == "spinning":
        score += 18
        reasons.append("Spinning reel fits lighter presentations.")
    if species in {"largemouth_bass", "smallmouth_bass", "northern_pike"} and reel_type in {"baitcasting", "spinning"}:
        score += 10
    if technique in {"spinnerbait", "jig", "chatterbait"} and reel_type == "baitcasting":
        score += 15
        reasons.append("Baitcasting reel suits power presentations.")
    if technique in {"drop_shot", "finesse", "trout", "crappie"} and reel_type == "spinning":
        score += 15
        reasons.append("Spinning reel suits finesse work.")

    if gear_ratio is not None:
        if lure_type in {"spinnerbait", "swimbait", "crankbait"} and gear_ratio >= 6.4:
            score += 8
        elif lure_type in {"frog", "topwater_popper"} and gear_ratio >= 7.1:
            score += 8
        elif lure_type in {"drop_shot", "soft_plastic_worm"} and gear_ratio <= 7.0:
            score += 6
        elif lure_type in {"spoon", "inline_spinner"} and 5.0 <= gear_ratio <= 7.0:
            score += 5
    else:
        warnings.append("Reel gear ratio is missing.")

    if drag is not None:
        if expected_weight is not None and drag >= max(4.0, expected_weight * 2):
            score += 6
        elif expected_weight is not None and drag < max(3.0, expected_weight * 1.5):
            score -= 6
            warnings.append("Reel drag may be light for the expected fish size.")
    else:
        warnings.append("Reel drag specification is missing.")

    if species in {"northern_pike", "channel_catfish"} and reel_type == "spinning" and drag and drag >= 8:
        score += 4
    if species in {"largemouth_bass", "smallmouth_bass"} and reel_type == "baitcasting":
        score += 3

    return max(0, min(100, score)), reasons, warnings


def _score_line(item: dict[str, Any], context: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    score = 40
    reasons: list[str] = []
    warnings: list[str] = []
    species = context.get("species")
    cover = context.get("cover")
    clarity = context.get("clarity")
    technique = context.get("technique")
    strength = _as_int(item.get("strength_lb"), None)
    line_type = _compact(item.get("line_type"))

    if line_type == "braid":
        score += 12
        reasons.append("Braid is versatile around cover and heavier presentations.")
    elif line_type in {"fluorocarbon", "fluoro"}:
        score += 12
        reasons.append("Fluorocarbon helps with stealth and sensitivity.")
    elif line_type in {"mono", "monofilament"}:
        score += 8
        reasons.append("Monofilament is forgiving for general-purpose use.")

    if species in {"largemouth_bass", "northern_pike", "channel_catfish"} and line_type == "braid":
        score += 16
        reasons.append("Braid fits stronger fish and cover work.")
    if species in {"rainbow_trout", "walleye", "crappie"} and line_type in {"fluorocarbon", "fluoro", "mono", "monofilament"}:
        score += 10

    if cover in {"heavy_cover", "weeds", "vegetation"} and strength and strength >= 20:
        score += 12
        reasons.append("Line strength supports cover fishing.")
    elif cover in {"open_water", "clear", "open"} and strength and strength <= 12:
        score += 8

    if clarity in {"clear", "stained"} and line_type in {"fluorocarbon", "fluoro"}:
        score += 5
    if technique in {"frog", "spinnerbait"} and line_type == "braid":
        score += 4
    if technique in {"drop_shot", "finesse"} and line_type in {"fluorocarbon", "fluoro"}:
        score += 4

    if strength is None:
        warnings.append("Line strength is missing.")

    return max(0, min(100, score)), reasons, warnings


def _score_lure(item: dict[str, Any], context: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    score = 45
    reasons: list[str] = []
    warnings: list[str] = []
    species = context.get("species")
    lure_type = context.get("lure_type")
    lure_weight = context.get("lure_weight_oz")
    technique = context.get("technique")
    clarity = context.get("clarity")
    time_of_day = context.get("time_of_day")
    cover = context.get("cover")

    item_lure_type = normalize_lure_type(item.get("lure_type") or item.get("subtype") or item.get("category"))
    item_color = _compact(item.get("color"))
    weight = _as_float(item.get("weight_oz"), None)
    species_tags = set(_split_tags(item.get("species_tags")))
    technique_tags = set(_split_tags(item.get("technique_tags")))

    if lure_type and lure_type == item_lure_type:
        score += 24
        reasons.append("Lure type matches the trip recommendation.")
    elif lure_type and item_lure_type in {"spinnerbait", "crankbait", "swimbait", "jig"} and lure_type in {"spinnerbait", "crankbait", "swimbait", "jig"}:
        score += 10

    if species and species in species_tags:
        score += 16
        reasons.append(f"Species tag matches {species.replace('_', ' ')}.")

    if technique and technique in technique_tags:
        score += 14
        reasons.append("Technique tag matches the trip.")
    elif technique and any(token in technique_tags for token in {technique.replace(" ", "_"), technique.split("_")[0]}):
        score += 7

    if lure_weight is not None and weight is not None:
        if abs(lure_weight - weight) <= 0.125:
            score += 16
            reasons.append("Lure weight matches the recommendation closely.")
        elif abs(lure_weight - weight) <= 0.25:
            score += 8

    if clarity in {"clear", "bright"} and item_color in {"shad", "natural_shad", "pearl_white", "white_silver"}:
        score += 8
    if clarity in {"stained", "dirty"} and item_color in {"chartreuse_white", "chartreuse_black_back", "firetiger", "white_chartreuse"}:
        score += 10
    if time_of_day in {"night", "low_light"} and item_color in {"black", "black_night", "bone"}:
        score += 8
    if cover in {"grass", "vegetation", "heavy_cover"} and item_lure_type in {"spinnerbait", "frog", "jig"}:
        score += 7

    if weight is None:
        warnings.append("Lure weight is missing.")
    if not species_tags:
        warnings.append("Species tags are missing for this lure.")

    return max(0, min(100, score)), reasons, warnings


def _score_terminal(item: dict[str, Any], context: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    score = 35
    reasons: list[str] = []
    warnings: list[str] = []
    lure_type = context.get("lure_type")
    technique = context.get("technique")
    species = context.get("species")
    subtype = _compact(item.get("subtype"))
    size = _text(item.get("size"), "")
    hook_size = _text(item.get("hook_size"), "")

    if subtype in {"hook", "jig_head"} and lure_type in {"jig", "soft_plastic_worm", "swimbait", "frog"}:
        score += 20
        reasons.append("Terminal tackle fits the lure style.")
    if subtype in {"leader"} and species in {"northern_pike", "trout", "walleye"}:
        score += 18
        reasons.append("Leader fits the target species.")
    if subtype in {"weight"} and technique in {"texas_rig", "carolina_rig", "drop_shot"}:
        score += 15
    if subtype in {"snap", "swivel"} and lure_type in {"spoon", "inline_spinner", "crankbait"}:
        score += 12

    if size or hook_size:
        reasons.append("Terminal tackle size is specified.")
    else:
        warnings.append("Terminal tackle size is missing.")

    return max(0, min(100, score)), reasons, warnings


def _choose_category(items: list[dict[str, Any]], score_fn, context: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str], list[str]]:
    scored: list[dict[str, Any]] = []
    for item in items:
        score, reasons, warnings = score_fn(item, context)
        scored.append({
            "item": item,
            "score": score,
            "reasons": reasons,
            "warnings": warnings,
        })
    scored.sort(key=lambda entry: (entry["score"], _text(entry["item"].get("updated_at"), _text(entry["item"].get("created_at"), ""))), reverse=True)
    best = scored[0] if scored else None
    return (
        best,
        scored[1:4],
        best["reasons"][:] if best else [],
        best["warnings"][:] if best else [],
    )


def _shape_item(item: dict[str, Any], *, score: int | None = None, notes: list[str] | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
    category = _gear_category(item)
    specs_used: list[str] = []
    if category == "rod":
        pairs = [
            ("Length", item.get("length_label") or item.get("length_ft")),
            ("Power", item.get("power")),
            ("Action", item.get("action")),
            ("Lure weight", f"{item.get('lure_weight_min_oz')} - {item.get('lure_weight_max_oz')}" if item.get("lure_weight_min_oz") is not None or item.get("lure_weight_max_oz") is not None else ""),
            ("Line rating", f"{item.get('line_rating_min_lb')} - {item.get('line_rating_max_lb')}" if item.get("line_rating_min_lb") is not None or item.get("line_rating_max_lb") is not None else ""),
        ]
    elif category == "reel":
        pairs = [
            ("Type", item.get("reel_type")),
            ("Gear ratio", f"{item.get('gear_ratio')}:1" if item.get("gear_ratio") not in (None, "") else ""),
            ("Drag", f"{item.get('max_drag_lb')} lb" if item.get("max_drag_lb") not in (None, "") else ""),
            ("Capacity", item.get("line_capacity")),
        ]
    elif category == "line":
        pairs = [
            ("Type", item.get("line_type")),
            ("Strength", f"{item.get('strength_lb')} lb" if item.get("strength_lb") not in (None, "") else ""),
            ("Color", item.get("color")),
            ("Length", f"{item.get('length_yd')} yd" if item.get("length_yd") not in (None, "") else ""),
        ]
    elif category == "lure":
        pairs = [
            ("Type", item.get("lure_type")),
            ("Color", item.get("color")),
            ("Weight", f"{item.get('weight_oz')} oz" if item.get("weight_oz") not in (None, "") else ""),
            ("Hook size", item.get("hook_size")),
        ]
    elif category == "terminal":
        pairs = [
            ("Subtype", item.get("subtype")),
            ("Size", item.get("size")),
            ("Hook size", item.get("hook_size")),
            ("Quantity", item.get("quantity")),
        ]
    else:
        pairs = []

    for label, value in pairs:
        text = _text(value, "")
        if text:
            specs_used.append(f"{label}: {text}")

    return {
        "id": item.get("id"),
        "category": item.get("category"),
        "label": _gear_label(item),
        "brand": item.get("brand", ""),
        "model": item.get("model", ""),
        "display_name": item.get("display_name") or _gear_label(item),
        "image": item.get("image") or item.get("image_url") or item.get("fallback_image", ""),
        "provider_icon": item.get("provider_icon", ""),
        "source_name": item.get("source_name", ""),
        "status": item.get("status", ""),
        "favorite": bool(item.get("favorite")),
        "notes": item.get("notes", ""),
        "score": score,
        "reasons": notes or [],
        "warnings": warnings or [],
        "specifications_used": specs_used,
        "specifications": item.get("specifications", {}),
        "quantity": item.get("quantity"),
    }


def recommend_owned_setup(
    target_species: str,
    expected_fish_weight: Any = None,
    lure_type: str | None = None,
    lure_weight_oz: Any = None,
    technique: str | None = None,
    habitat: str | None = None,
    cover: str | None = None,
    conditions: dict[str, Any] | None = None,
    owned_gear: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    items = _owned_items(owned_gear)
    buckets = _bucket_items(items)
    species = normalize_species_name(target_species)
    context = {
        "species": species,
        "expected_weight": _as_float(expected_fish_weight, None),
        "lure_type": normalize_lure_type(lure_type),
        "lure_weight_oz": _as_float(lure_weight_oz, None),
        "technique": normalize_lure_type(technique) if technique else "",
        "habitat": _compact(habitat),
        "cover": _compact(cover),
        "clarity": _normalize_conditions(conditions).get("clarity", ""),
        "time_of_day": _normalize_conditions(conditions).get("time_of_day", ""),
        "conditions": _normalize_conditions(conditions),
    }
    rod_choice, rod_alts, rod_reasons, rod_warnings = _choose_category(buckets.get("rod", []), _score_rod, context)
    reel_choice, reel_alts, reel_reasons, reel_warnings = _choose_category(buckets.get("reel", []), _score_reel, context)
    line_choice, line_alts, line_reasons, line_warnings = _choose_category(buckets.get("line", []), _score_line, context)
    lure_choice, lure_alts, lure_reasons, lure_warnings = _choose_category(buckets.get("lure", []), _score_lure, context)
    terminal_choice, terminal_alts, terminal_reasons, terminal_warnings = _choose_category(buckets.get("terminal", []), _score_terminal, context)

    scored_choices = [entry for entry in (rod_choice, reel_choice, line_choice, lure_choice, terminal_choice) if entry]
    if scored_choices:
        score = round(sum(entry["score"] for entry in scored_choices) / len(scored_choices))
    else:
        score = 0

    if lure_choice:
        if lure_choice["item"].get("weight_oz") and context["lure_weight_oz"] is None:
            context["lure_weight_oz"] = _as_float(lure_choice["item"].get("weight_oz"), None)
        if lure_choice["item"].get("lure_type") and not context["lure_type"]:
            context["lure_type"] = normalize_lure_type(lure_choice["item"].get("lure_type"))

    warnings = []
    warnings.extend(rod_warnings)
    warnings.extend(reel_warnings)
    warnings.extend(line_warnings)
    warnings.extend(lure_warnings)
    warnings.extend(terminal_warnings)
    if not rod_choice:
        warnings.append("No owned rod matched this trip yet.")
    if not reel_choice:
        warnings.append("No owned reel matched this trip yet.")
    if not line_choice:
        warnings.append("No owned line matched this trip yet.")
    if not lure_choice:
        warnings.append("No owned lure matched this trip yet.")
    if not terminal_choice:
        warnings.append("No owned terminal tackle matched this trip yet.")

    reasons = []
    for group in (rod_reasons, reel_reasons, line_reasons, lure_reasons, terminal_reasons):
        reasons.extend(group[:2])

    if species in {"largemouth_bass", "smallmouth_bass"}:
        reasons.append("Bass-oriented gear favors casting and cover control.")
    elif species in {"rainbow_trout", "crappie", "bluegill", "walleye"}:
        reasons.append("Lighter presentations and cleaner line usually help here.")
    elif species in {"channel_catfish", "northern_pike"}:
        reasons.append("Stronger line and hardware help manage harder pulls and teeth.")

    confidence = "high" if score >= 85 else "medium" if score >= 65 else "low"
    missing_information = []
    for warning in warnings:
        warning_text = _text(warning, "")
        if warning_text and ("missing" in warning_text.lower() or "not fully specified" in warning_text.lower()):
            missing_information.append(warning_text)
    confidence_notes = [
        "The locker has a strong owned-gear match for this trip." if score >= 85 else
        "The locker has a usable match, but one or more specs are partial." if score >= 65 else
        "The locker does not yet have a tight match for this trip.",
    ]
    if warnings:
        confidence_notes.append("Missing fields reduce confidence more than favorite status increases it.")

    best_lure_label = _gear_label(lure_choice["item"]) if lure_choice else ""
    selected_lure = lure_choice["item"] if lure_choice else {}
    selected_rod = rod_choice["item"] if rod_choice else {}
    selected_reel = reel_choice["item"] if reel_choice else {}
    selected_line = line_choice["item"] if line_choice else {}
    selected_terminal = terminal_choice["item"] if terminal_choice else {}

    setup_name = " / ".join(part for part in [
        _gear_label(selected_rod),
        _gear_label(selected_reel),
        _gear_label(selected_line),
        best_lure_label,
    ] if part)

    alternatives = []
    for category, label, options in (
        ("rod", "Rod", rod_alts),
        ("reel", "Reel", reel_alts),
        ("line", "Line", line_alts),
        ("lure", "Lure", lure_alts),
        ("terminal", "Terminal", terminal_alts),
    ):
        if options:
            top = options[0]
            alternatives.append({
                "category": category,
                "label": label,
                "name": _gear_label(top["item"]),
                "score": top["score"],
                "reason": (top["reasons"][0] if top["reasons"] else "Closest alternative"),
            })

    return {
        "target_species": species,
        "expected_fish_weight": context.get("expected_weight"),
        "lure_type": context.get("lure_type"),
        "lure_weight_oz": context.get("lure_weight_oz"),
        "technique": context.get("technique"),
        "habitat": context.get("habitat"),
        "cover": context.get("cover"),
        "conditions": context.get("conditions", {}),
        "score": score,
        "confidence": confidence,
        "headline": f"Use your {setup_name}" if setup_name else "No full owned setup matched yet.",
        "summary": (
            f"{best_lure_label or 'Recommended lure'} leads the plan for {species.replace('_', ' ') if species else 'this trip'}."
            if best_lure_label else "The locker has useful gear, but the match is still broad."
        ),
        "rod": _shape_item(selected_rod, score=rod_choice["score"] if rod_choice else None, notes=rod_reasons, warnings=rod_warnings) if selected_rod else None,
        "reel": _shape_item(selected_reel, score=reel_choice["score"] if reel_choice else None, notes=reel_reasons, warnings=reel_warnings) if selected_reel else None,
        "line": _shape_item(selected_line, score=line_choice["score"] if line_choice else None, notes=line_reasons, warnings=line_warnings) if selected_line else None,
        "lure": _shape_item(selected_lure, score=lure_choice["score"] if lure_choice else None, notes=lure_reasons, warnings=lure_warnings) if selected_lure else None,
        "terminal": _shape_item(selected_terminal, score=terminal_choice["score"] if terminal_choice else None, notes=terminal_reasons, warnings=terminal_warnings) if selected_terminal else None,
        "reasons": reasons[:8],
        "warnings": warnings[:8],
        "missing_information": missing_information[:8],
        "confidence_notes": confidence_notes,
        "alternatives": alternatives[:5],
        "packing_list": build_trip_packing_list(
            {
                "rod": selected_rod,
                "reel": selected_reel,
                "line": selected_line,
                "lure": selected_lure,
                "terminal": selected_terminal,
                "alternatives": alternatives,
            }
        ),
        "top_matches": {
            "rod": [_shape_item(entry["item"], score=entry["score"], notes=entry["reasons"], warnings=entry["warnings"]) for entry in rod_alts[:2]],
            "reel": [_shape_item(entry["item"], score=entry["score"], notes=entry["reasons"], warnings=entry["warnings"]) for entry in reel_alts[:2]],
            "line": [_shape_item(entry["item"], score=entry["score"], notes=entry["reasons"], warnings=entry["warnings"]) for entry in line_alts[:2]],
            "lure": [_shape_item(entry["item"], score=entry["score"], notes=entry["reasons"], warnings=entry["warnings"]) for entry in lure_alts[:3]],
            "terminal": [_shape_item(entry["item"], score=entry["score"], notes=entry["reasons"], warnings=entry["warnings"]) for entry in terminal_alts[:2]],
        },
    }


def build_trip_packing_list(recommendation: dict[str, Any] | None) -> dict[str, Any]:
    rec = recommendation if isinstance(recommendation, dict) else {}
    core = []
    for key in ("rod", "reel", "line", "lure", "terminal"):
        item = rec.get(key)
        if isinstance(item, dict):
            core.append({
                "key": key,
                "label": key.replace("_", " ").title(),
                "name": item.get("display_name") or item.get("label") or "Recommended item",
                "notes": item.get("reasons", [])[:2],
                "packed": False,
            })

    alternatives = []
    for alt in rec.get("alternatives", []) if isinstance(rec.get("alternatives"), list) else []:
        if isinstance(alt, dict):
            alternatives.append({
                "label": alt.get("label", "Alternative"),
                "name": alt.get("name", ""),
                "score": alt.get("score"),
                "reason": alt.get("reason", ""),
                "packed": False,
            })

    extras = [
        {"label": "Net", "name": "Net if you expect bigger fish", "packed": False},
        {"label": "Pliers", "name": "Pliers", "packed": False},
        {"label": "Scale", "name": "Scale", "packed": False},
        {"label": "Measuring board", "name": "Measuring board", "packed": False},
    ]

    return {
        "title": "Gear to Pack",
        "core": core,
        "alternatives": alternatives[:3],
        "extras": extras,
        "summary": "Pack the matched owned gear first, then add backup lures and basic tools.",
    }


def summarize_gear_maintenance(items: list[dict[str, Any]] | None) -> dict[str, Any]:
    gear = [item for item in (items or []) if isinstance(item, dict)]
    due: list[dict[str, Any]] = []
    soon: list[dict[str, Any]] = []
    retired: list[dict[str, Any]] = []
    now = datetime.now()

    for item in gear:
        status = _compact(item.get("status"))
        if status == "retired":
            retired.append({
                "id": item.get("id"),
                "label": _gear_label(item),
                "reason": _text(item.get("retired_reason"), ""),
            })
            continue
        interval = _as_int(item.get("maintenance_interval_days"), 0) or 0
        last_cleaned = _text(item.get("last_cleaned"), "")
        last_used = _text(item.get("last_used"), "")
        if interval <= 0 and not last_cleaned and not last_used:
            continue
        reference = last_cleaned or last_used
        try:
            reference_dt = datetime.fromisoformat(reference.replace("Z", "+00:00")) if reference else None
        except Exception:
            reference_dt = None
        if not reference_dt and interval > 0:
            soon.append({
                "id": item.get("id"),
                "label": _gear_label(item),
                "reason": "Maintenance interval is set, but the last service date is missing.",
            })
            continue
        if reference_dt and interval > 0:
            age_days = (now - reference_dt.replace(tzinfo=None)).days
            if age_days >= interval:
                due.append({
                    "id": item.get("id"),
                    "label": _gear_label(item),
                    "reason": f"Last service was about {age_days} days ago.",
                })
            elif age_days >= max(1, interval - 14):
                soon.append({
                    "id": item.get("id"),
                    "label": _gear_label(item),
                    "reason": f"Service is coming due in about {max(0, interval - age_days)} days.",
                })

    return {
        "due": due[:6],
        "soon": soon[:6],
        "retired": retired[:6],
        "summary": {
            "due": len(due),
            "soon": len(soon),
            "retired": len(retired),
        },
    }


def summarize_gear_usage(items: list[dict[str, Any]] | None) -> dict[str, Any]:
    gear = [item for item in (items or []) if isinstance(item, dict)]
    used = sorted(
        [item for item in gear if _text(item.get("last_used"), "")],
        key=lambda item: _text(item.get("last_used"), _text(item.get("updated_at"), "")),
        reverse=True,
    )
    most_used = sorted(
        gear,
        key=lambda item: (
            _as_int(item.get("catches_logged"), 0) or 0,
            _as_int(item.get("trips_used"), 0) or 0,
            _text(item.get("updated_at"), _text(item.get("created_at"), "")),
        ),
        reverse=True,
    )
    return {
        "recently_used": [_shape_item(item, score=None) for item in used[:4]],
        "most_used": [_shape_item(item, score=None) for item in most_used[:4] if (_as_int(item.get("catches_logged"), 0) or 0) > 0 or (_as_int(item.get("trips_used"), 0) or 0) > 0],
        "summary": {
            "recent": len(used),
            "used": len([item for item in gear if (_as_int(item.get("trips_used"), 0) or 0) > 0]),
            "caught": len([item for item in gear if (_as_int(item.get("catches_logged"), 0) or 0) > 0]),
        },
    }
