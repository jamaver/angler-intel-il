from __future__ import annotations

import html
import json
import uuid
from pathlib import Path
from typing import Any

from flask import jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from gear.catalog_providers import available_providers, fetch_product, search_gear_catalog
from gear.settings import load_settings
from gear.inventory import (
    category_label,
    category_sections,
    find_duplicate_items,
    fallback_image_for,
    inventory_summary,
    delete_item,
    list_items,
    provider_icon_for,
    set_status,
    toggle_favorite,
    upsert_item,
)
from intelligence.gear_intelligence import (
    build_trip_packing_list,
    recommend_owned_setup,
    summarize_gear_maintenance,
    summarize_gear_usage,
)
from intelligence.target_profile import load_target_profile, resolve_target_species


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
GEAR_UPLOAD_DIR = DATA_DIR / "gear_uploads"
SPECIES_PATH = DATA_DIR / "species_profiles_v43.json"
RIGS_PATH = DATA_DIR / "lure_rig_setups_v43.json"
ALLOWED_GEAR_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)
    except Exception:
        return default


def _species() -> list[dict[str, Any]]:
    data = _read_json(SPECIES_PATH, [])
    return data if isinstance(data, list) else []


def _rigs() -> list[dict[str, Any]]:
    data = _read_json(RIGS_PATH, [])
    return data if isinstance(data, list) else []


def _match_text(value: str, query: str) -> bool:
    return query.lower() in value.lower()


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _filter_species(q: str = "", group: str = "") -> list[dict[str, Any]]:
    q = q.strip().lower()
    group = group.strip().lower()
    results = []

    for item in _species():
        blob = " ".join([
            str(item.get("id", "")),
            str(item.get("name", "")),
            str(item.get("group", "")),
            " ".join(map(str, item.get("best_lures", []))),
            " ".join(map(str, item.get("habitat", []))),
            str(item.get("quick_pattern", "")),
        ]).lower()

        if q and q not in blob:
            continue

        if group and group != str(item.get("group", "")).lower():
            continue

        results.append(item)

    return results


def _filter_rigs(q: str = "", species: str = "", lure: str = "") -> list[dict[str, Any]]:
    q = q.strip().lower()
    species = species.strip().lower()
    lure = lure.strip().lower()
    results = []

    for item in _rigs():
        blob = " ".join([
            str(item.get("id", "")),
            str(item.get("name", "")),
            " ".join(map(str, item.get("best_for", []))),
            str(item.get("rod", "")),
            str(item.get("line", "")),
            str(item.get("terminal", "")),
            str(item.get("setup", "")),
            str(item.get("when", "")),
            " ".join(map(str, item.get("tips", []))),
        ]).lower()

        if q and q not in blob:
            continue

        if lure and lure not in str(item.get("id", "")).lower() and lure not in str(item.get("name", "")).lower():
            continue

        if species:
            best_for = " ".join(map(str, item.get("best_for", []))).lower()
            if species not in best_for and species not in blob:
                continue

        results.append(item)

    return results


def _enrich_gear_item(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    enriched["fallback_image"] = fallback_image_for(enriched.get("category"), enriched.get("subtype"))
    enriched["display_image"] = enriched.get("image_url") or enriched.get("image") or enriched["fallback_image"]
    enriched["provider_icon"] = enriched.get("provider_icon") or provider_icon_for(enriched.get("provider"), enriched.get("source"))
    enriched["duplicate_matches"] = enriched.get("duplicate_matches") if isinstance(enriched.get("duplicate_matches"), list) else []
    return enriched


def _is_generic_import(product: dict[str, Any]) -> bool:
    blob = " ".join([
        str(product.get("brand", "")),
        str(product.get("model", "")),
        str(product.get("display_name", "")),
        str(product.get("description", "")),
        str(product.get("import_summary", "")),
        str(product.get("product_summary", "")),
    ]).lower()
    generic_markers = (
        "site maintenance",
        "maintenance",
        "page not found",
        "not found",
        "temporarily unavailable",
        "access denied",
        "coming soon",
        "home page",
    )
    if any(marker in blob for marker in generic_markers):
        return True
    if not str(product.get("brand", "")).strip() and not str(product.get("model", "")).strip():
        return True
    if not str(product.get("product_summary", "")).strip() and not str(product.get("import_summary", "")).strip():
        return True
    return False


def _merge_query_match(base: dict[str, Any], match: dict[str, Any], force: bool = False) -> dict[str, Any]:
    merged = dict(base or {})
    if not isinstance(match, dict):
        return merged
    field_sources = merged.get("field_sources") if isinstance(merged.get("field_sources"), dict) else {}
    for key in (
        "provider",
        "provider_product_id",
        "source_name",
        "source_url",
        "category",
        "brand",
        "model",
        "display_name",
        "image_url",
        "image_source",
        "identifiers",
        "specifications",
        "price",
        "availability",
        "confidence",
        "raw_provider_data_cached",
        "provider_icon",
        "length_ft",
        "length_label",
        "power",
        "action",
        "pieces",
        "lure_weight_min_oz",
        "lure_weight_max_oz",
        "line_rating_min_lb",
        "line_rating_max_lb",
        "reel_type",
        "gear_ratio",
        "max_drag_lb",
        "line_capacity",
        "weight_oz",
        "handedness",
        "line_type",
        "strength_lb",
        "diameter_equivalent",
        "color",
        "length_yd",
        "lure_type",
        "hook_size",
        "depth_min_ft",
        "depth_max_ft",
        "quantity",
        "subtype",
        "size",
        "technique_tags",
        "species_tags",
    ):
        value = match.get(key)
        if force and key in {"provider", "provider_product_id", "source_name", "source_url", "category", "brand", "model", "display_name", "image_url", "image_source", "identifiers", "specifications", "price", "availability", "confidence", "raw_provider_data_cached", "provider_icon"}:
            if value not in (None, "", [], {}):
                merged[key] = value
                if key in {"brand", "model", "display_name", "image_url", "source_name", "source_url", "provider", "provider_product_id", "category"}:
                    field_sources[key] = "query_match"
            continue
        if key not in merged or merged.get(key) in (None, "", [], {}):
            if value not in (None, "", [], {}):
                merged[key] = value
                if key in {"brand", "model", "display_name", "image_url", "source_name", "source_url", "provider", "provider_product_id", "category"}:
                    field_sources[key] = "query_match"
    if field_sources:
        merged["field_sources"] = field_sources
    merged["query_match_applied"] = True
    merged["query_match_source"] = match.get("source_name") or match.get("provider") or ""
    merged["query_match_label"] = match.get("display_name") or "Suggested match"
    merged["query_match"] = {
        "provider": match.get("provider"),
        "source_name": match.get("source_name"),
        "source_url": match.get("source_url"),
        "display_name": match.get("display_name"),
        "confidence": match.get("confidence"),
    }
    return merged


def _best_query_matches(query: str, category: str = "", limit: int = 3) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    results = search_gear_catalog(query, category=category, scope="both", limit=max(1, min(limit, 5)))
    matches: list[dict[str, Any]] = []
    for group in (results.get("local", {}).get("owned", []), results.get("local", {}).get("cached", []), results.get("online", {}).get("matches", [])):
        if isinstance(group, list):
            for item in group:
                if isinstance(item, dict):
                    matches.append(item)
    return matches[:limit]


def _locker_context() -> dict[str, Any]:
    items = [_enrich_gear_item(item) for item in list_items()]
    trip_context = _trip_context()
    recommendation = recommend_owned_setup(
        trip_context["target_species"],
        expected_fish_weight=trip_context["expected_fish_weight"],
        lure_type=trip_context["lure_type"],
        lure_weight_oz=trip_context["lure_weight_oz"],
        technique=trip_context["technique"],
        habitat=trip_context["habitat"],
        cover=trip_context["cover"],
        conditions=trip_context["conditions"],
        owned_gear=items,
    )
    categories = []
    for section in category_sections(items):
        categories.append({
            "key": section["key"],
            "label": category_label(section["key"]),
            "count": section["count"],
            "items": [ _enrich_gear_item(item) for item in section["items"] ],
        })

    return {
        "summary": inventory_summary(items),
        "categories": categories,
        "items": items,
        "recent_items": [_enrich_gear_item(item) for item in items[:4]],
        "reference_rigs": _rigs(),
        "settings": load_settings(),
        "providers": available_providers(),
        "trip_context": trip_context,
        "recommendation": recommendation,
        "packing_list": build_trip_packing_list(recommendation),
        "usage": summarize_gear_usage(items),
        "maintenance": summarize_gear_maintenance(items),
    }


def _trip_context() -> dict[str, Any]:
    profile = load_target_profile()
    trip_species, trip_species_source = resolve_target_species("", profile)
    return {
        "target_species": trip_species,
        "target_species_source": trip_species_source,
        "expected_fish_weight": request.args.get("expected_fish_weight", ""),
        "lure_type": request.args.get("lure_type", ""),
        "lure_weight_oz": request.args.get("lure_weight_oz", ""),
        "technique": request.args.get("technique", ""),
        "habitat": request.args.get("habitat", ""),
        "cover": request.args.get("cover", ""),
        "conditions": {
            "temperature": request.args.get("temperature", ""),
            "wind_mph": request.args.get("wind_mph", ""),
            "cloud_cover": request.args.get("cloud_cover", ""),
            "clarity": request.args.get("clarity", ""),
            "time_of_day": request.args.get("time_of_day", ""),
            "season": request.args.get("season", ""),
        },
    }


def _nav(active: str) -> str:
    links = [
        ("/", "Dashboard"),
        ("/waters", "Local Waters"),
        ("/species", "Species"),
        ("/rigs", "My Tackle Locker"),
        ("/reports", "Saved Reports"),
        ("/data-tools", "Data Tools"),
        ("/app-health", "App Health"),
    ]

    out = ['<nav class="ai-main-tabs" aria-label="Angler Intel navigation">']
    for href, label in links:
        cls = "ai-main-tab active" if href == active else "ai-main-tab"
        out.append(f'  <a class="{cls}" href="{href}">{label}</a>')
    out.append("</nav>")
    return "\n".join(out)


def _page_shell(title: str, active: str, body: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{_esc(title)} - Angler Intel</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/css/style.css">
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 2rem;
      max-width: 1100px;
      line-height: 1.45;
      background: #0b1710;
      color: #f4fff6;
    }}
    .card {{
      border: 1px solid rgba(166, 232, 182, 0.35);
      border-radius: 12px;
      padding: 1rem;
      margin: 1rem 0;
      background: #f8fff9;
      color: #102417;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(270px, 1fr));
      gap: 1rem;
    }}
    .tag {{
      display: inline-block;
      padding: 0.15rem 0.4rem;
      margin: 0.12rem;
      border-radius: 999px;
      background: #e9f8ee;
      border: 1px solid #b9ddc5;
      font-size: 0.85rem;
    }}
    input, button, select {{
      font-size: 1rem;
      padding: 0.5rem;
      margin: 0.2rem 0;
      border-radius: 8px;
      border: 1px solid #5fa66f;
    }}
    button {{
      background: #e9f8ee;
      color: #102417;
      font-weight: 800;
      cursor: pointer;
    }}
    a {{
      color: #1f8f45;
      font-weight: 800;
    }}
    .muted {{
      color: #5b6b60;
    }}
    pre {{
      background: #102417;
      color: #f4fff6;
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      white-space: pre-wrap;
    }}
    @media (max-width: 640px) {{
      body {{ margin: 1rem; }}
    }}
  </style>
</head>
<body>
  {_nav(active)}
  {body}
  <script src="/static/js/species_controls_v431.js"></script>
  <script src="/static/js/global_nav_v433.js"></script>
  <script src="/static/js/ui_polish_v442.js"></script>
</body>
</html>
"""


def _render_species_page() -> str:
    cards = []
    for item in _species():
        lures = "".join(f"<span class='tag'>{_esc(x)}</span>" for x in item.get("best_lures", []))
        habitat = "".join(f"<span class='tag'>{_esc(x)}</span>" for x in item.get("habitat", []))
        cards.append(f"""
        <article class="card">
          <h2>{_esc(item.get("name"))}</h2>
          <p class="muted">{_esc(item.get("group"))}</p>
          <p>{_esc(item.get("quick_pattern"))}</p>
          <h3>Good lures</h3>
          <p>{lures}</p>
          <h3>Habitat</h3>
          <p>{habitat}</p>
          <p><a href="/rigs?species={_esc(item.get("name"))}">View rig setups for this species</a></p>
        </article>
        """)

    body = f"""
    <h1>Species Guide</h1>
    <p>v4.3 adds expanded fish profiles for Illinois-focused recommendations.</p>
    <div class="card">
      <label>Search species or habitat<br><input id="speciesSearch" placeholder="trout, pike, walleye, weeds, current"></label>
      <button onclick="filterCards()">Filter</button>
    </div>
    <div id="speciesCards" class="grid">
      {''.join(cards)}
    </div>
    <script>
    function filterCards() {{
      const q = document.getElementById("speciesSearch").value.toLowerCase();
      document.querySelectorAll("#speciesCards article").forEach(card => {{
        card.style.display = card.innerText.toLowerCase().includes(q) ? "" : "none";
      }});
    }}
    </script>
    """
    return _page_shell("Species Guide", "/species", body)


def _render_rigs_page() -> str:
    cards = []
    for item in _rigs():
        best_for = "".join(f"<span class='tag'>{_esc(x)}</span>" for x in item.get("best_for", []))
        tips = "".join(f"<li>{_esc(x)}</li>" for x in item.get("tips", []))
        cards.append(f"""
        <article class="card">
          <h2>{_esc(item.get("name"))}</h2>
          <p>{best_for}</p>
          <p><strong>Rod:</strong> {_esc(item.get("rod"))}</p>
          <p><strong>Line:</strong> {_esc(item.get("line"))}</p>
          <p><strong>Terminal:</strong> {_esc(item.get("terminal"))}</p>
          <p><strong>Setup:</strong> {_esc(item.get("setup"))}</p>
          <p><strong>When:</strong> {_esc(item.get("when"))}</p>
          <h3>Tips</h3>
          <ul>{tips}</ul>
        </article>
        """)

    body = f"""
    <h1>Rig Setup Guide</h1>
    <p>v4.3 adds practical rig setup details for lure and bait types.</p>
    <div class="card">
      <label>Search rig, species, lure, or condition<br><input id="rigSearch" placeholder="trout, pike, spinnerbait, worm, walleye"></label>
      <button onclick="filterCards()">Filter</button>
    </div>
    <div id="rigCards" class="grid">
      {''.join(cards)}
    </div>
    <script>
    function filterCards() {{
      const q = document.getElementById("rigSearch").value.toLowerCase();
      document.querySelectorAll("#rigCards article").forEach(card => {{
        card.style.display = card.innerText.toLowerCase().includes(q) ? "" : "none";
      }});
    }}

    const params = new URLSearchParams(location.search);
    const species = params.get("species");
    const lure = params.get("lure");
    if (species || lure) {{
      document.addEventListener("DOMContentLoaded", () => {{
        const box = document.getElementById("rigSearch");
        box.value = species || lure || "";
        filterCards();
      }});
    }}
    </script>
    """
    return _page_shell("Rig Setup Guide", "/rigs", body)


def register_species_rig_routes_v43(app):
    @app.route("/species")
    def species_page_v43():
        return _render_species_page()

    @app.route("/rigs")
    def rigs_page_v43():
        return render_template("tackle_locker.html", locker=_locker_context())

    @app.route("/tackle-locker")
    def tackle_locker_page_v43():
        return render_template("tackle_locker.html", locker=_locker_context())

    @app.route("/api/species-profiles")
    def species_api_v43():
        q = request.args.get("q", "")
        group = request.args.get("group", "")
        results = _filter_species(q=q, group=group)
        return jsonify({
            "ok": True,
            "version": "v4.3",
            "count": len(results),
            "species": results,
            "database": {
                "path": str(SPECIES_PATH),
                "total_species": len(_species()),
            },
        })

    @app.route("/api/rigs")
    def rigs_api_v43():
        q = request.args.get("q", "")
        species = request.args.get("species", "")
        lure = request.args.get("lure", "")
        results = _filter_rigs(q=q, species=species, lure=lure)
        return jsonify({
            "ok": True,
            "version": "v4.3",
            "count": len(results),
            "rigs": results,
            "database": {
                "path": str(RIGS_PATH),
                "total_rigs": len(_rigs()),
            },
        })

    @app.route("/api/species-rigs/status")
    def species_rigs_status_v43():
        return jsonify({
            "ok": True,
            "version": "v4.3",
            "species_count": len(_species()),
            "rig_count": len(_rigs()),
            "routes": [
                "/species",
                "/rigs",
                "/tackle-locker",
                "/api/species-profiles",
                "/api/rigs",
                "/api/species-rigs/status",
            ],
        })

    @app.route("/api/gear/items", methods=["GET", "POST"])
    def gear_items_api_v610():
        if request.method == "GET":
            items = [_enrich_gear_item(item) for item in list_items()]
            return jsonify({
                "ok": True,
                "version": "v6.13-gear-intelligence-packing-catch-linking",
                "summary": inventory_summary(items),
                "items": items,
                "categories": category_sections(items),
            })

        payload = request.get_json(silent=True) or {}
        item = upsert_item(payload if isinstance(payload, dict) else {})
        return jsonify({
            "ok": True,
            "version": "v6.13-gear-intelligence-packing-catch-linking",
            "item": _enrich_gear_item(item),
            "summary": inventory_summary(),
        })

    @app.route("/api/gear/items/<item_id>/favorite", methods=["POST"])
    def gear_item_favorite_api_v610(item_id: str):
        payload = request.get_json(silent=True) or {}
        favorite = payload.get("favorite")
        item = toggle_favorite(item_id, favorite if favorite is not None else None)
        if not item:
            return jsonify({"ok": False, "error": "Gear item not found"}), 404
        return jsonify({"ok": True, "item": _enrich_gear_item(item), "summary": inventory_summary()})

    @app.route("/api/gear/items/<item_id>/archive", methods=["POST"])
    def gear_item_archive_api_v610(item_id: str):
        item = set_status(item_id, "retired")
        if not item:
            return jsonify({"ok": False, "error": "Gear item not found"}), 404
        return jsonify({"ok": True, "item": _enrich_gear_item(item), "summary": inventory_summary()})

    @app.route("/api/gear/items/<item_id>/retire", methods=["POST"])
    def gear_item_retire_api_v612(item_id: str):
        item = set_status(item_id, "retired")
        if not item:
            return jsonify({"ok": False, "error": "Gear item not found"}), 404
        return jsonify({"ok": True, "item": _enrich_gear_item(item), "summary": inventory_summary()})

    @app.route("/api/gear/items/<item_id>/delete", methods=["POST", "DELETE"])
    def gear_item_delete_api_v612(item_id: str):
        deleted = delete_item(item_id)
        if not deleted:
            return jsonify({"ok": False, "error": "Gear item not found"}), 404
        return jsonify({"ok": True, "deleted": True, "summary": inventory_summary()})

    @app.route("/api/gear/uploads/<path:filename>")
    def gear_uploads_api_v612(filename: str):
        return send_from_directory(GEAR_UPLOAD_DIR, filename)

    @app.route("/api/gear/upload-image", methods=["POST"])
    def gear_upload_image_api_v612():
        upload = request.files.get("image") or request.files.get("file")
        if upload is None or not getattr(upload, "filename", ""):
            return jsonify({"ok": False, "error": "Choose an image file first."}), 400
        original = secure_filename(upload.filename or "")
        suffix = Path(original).suffix.lower()
        if suffix not in ALLOWED_GEAR_IMAGE_EXTENSIONS:
            suffix = ".png"
        GEAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"gear_{uuid.uuid4().hex[:12]}{suffix}"
        file_path = GEAR_UPLOAD_DIR / filename
        upload.save(file_path)
        return jsonify({
            "ok": True,
            "filename": filename,
            "image_url": f"/api/gear/uploads/{filename}",
            "image_source": "local-upload",
        })

    @app.route("/api/gear/search")
    def gear_search_api_v611():
        query = request.args.get("q", "")
        category = request.args.get("category", "")
        scope = request.args.get("scope", "both")
        results = search_gear_catalog(query, category=category, scope=scope)
        return jsonify(results)

    @app.route("/api/gear/catalog/search")
    def gear_catalog_search_api_v610():
        query = request.args.get("q", "")
        category = request.args.get("category", "")
        results = search_gear_catalog(query, category=category, scope="local")
        return jsonify({
            "ok": True,
            "version": "v6.13-gear-intelligence-packing-catch-linking",
            "count": len(results.get("local", {}).get("owned", [])) + len(results.get("local", {}).get("cached", [])),
            "products": results.get("local", {}).get("cached", []),
            "local": results.get("local", {}),
            "messages": results.get("messages", []),
        })

    @app.route("/api/gear/import/url", methods=["POST"])
    def gear_import_url_api_v611():
        payload = request.get_json(silent=True) or {}
        url = payload.get("url", "")
        category = payload.get("category", "misc")
        query_hint = str(payload.get("query", "") or "").strip()
        import_result = fetch_product(url=url, category=category, allow_remote_images=bool(load_settings().get("allow_remote_images", False)))
        if not import_result:
            return jsonify({"ok": False, "error": "Unable to import the product URL."}), 400
        product = import_result if isinstance(import_result, dict) else {}
        query_matches = _best_query_matches(query_hint, category=category, limit=3) if query_hint else []
        if query_matches and _is_generic_import(product):
            product = _merge_query_match(product, query_matches[0], force=True)
            product["query_matches"] = query_matches
            product["query_hint"] = query_hint
        duplicates = find_duplicate_items(product) if isinstance(product, dict) else []
        return jsonify({
            "ok": True,
            "version": "v6.13-gear-intelligence-packing-catch-linking",
            "product": product,
            "duplicate_matches": duplicates if isinstance(duplicates, list) else [],
            "query_matches": query_matches,
        })

    @app.route("/api/gear/settings", methods=["GET", "POST"])
    def gear_settings_api_v611():
        if request.method == "GET":
            return jsonify({"ok": True, "settings": load_settings(), "providers": available_providers()})
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            payload = {}
        from gear.settings import save_settings
        settings = save_settings(payload)
        return jsonify({"ok": True, "settings": settings, "providers": available_providers()})

    @app.route("/api/gear/recommendation")
    def gear_recommendation_api_v613():
        items = [_enrich_gear_item(item) for item in list_items()]
        profile = load_target_profile()
        trip_species = str(request.args.get("species", "")).strip()
        if not trip_species:
            trip_species = resolve_target_species("", profile)[0]
        recommendation = recommend_owned_setup(
            trip_species,
            expected_fish_weight=request.args.get("expected_fish_weight", ""),
            lure_type=request.args.get("lure_type", ""),
            lure_weight_oz=request.args.get("lure_weight_oz", ""),
            technique=request.args.get("technique", ""),
            habitat=request.args.get("habitat", ""),
            cover=request.args.get("cover", ""),
            conditions={
                "temperature": request.args.get("temperature", ""),
                "wind_mph": request.args.get("wind_mph", ""),
                "cloud_cover": request.args.get("cloud_cover", ""),
                "clarity": request.args.get("clarity", ""),
                "time_of_day": request.args.get("time_of_day", ""),
                "season": request.args.get("season", ""),
            },
            owned_gear=items,
        )
        return jsonify({
            "ok": True,
            "version": "v6.13-gear-intelligence-packing-catch-linking",
            "recommendation": recommendation,
            "packing_list": build_trip_packing_list(recommendation),
            "usage": summarize_gear_usage(items),
            "maintenance": summarize_gear_maintenance(items),
            "trip_context": {
                "target_species": trip_species,
                "target_species_source": resolve_target_species("", profile)[1],
            },
        })
