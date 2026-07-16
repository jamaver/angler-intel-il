#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import tempfile
import sys
from pathlib import Path
from io import BytesIO
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _fake_product_html() -> str:
    return """<!doctype html>
<html>
  <head>
    <title>St. Croix Mojo Bass 7'1" MH Fast</title>
    <meta property="og:title" content="St. Croix Mojo Bass 7'1&quot; MH Fast">
    <meta property="og:image" content="https://example.com/mojo-bass.jpg">
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Product",
      "name": "St. Croix Mojo Bass 7'1\\\" MH Fast",
      "brand": {"@type": "Brand", "name": "St. Croix"},
      "model": "Mojo Bass",
      "sku": "MBS71MHF",
      "image": "https://example.com/mojo-bass.jpg",
      "offers": {"@type": "Offer", "price": "149.99", "availability": "https://schema.org/InStock"},
      "additionalProperty": [
        {"@type": "PropertyValue", "name": "Length", "value": "7'1\\\""},
        {"@type": "PropertyValue", "name": "Power", "value": "Medium Heavy"},
        {"@type": "PropertyValue", "name": "Action", "value": "Fast"},
        {"@type": "PropertyValue", "name": "Lure Weight", "value": "3/8-1 oz"},
        {"@type": "PropertyValue", "name": "Line Rating", "value": "12-20 lb"},
        {"@type": "PropertyValue", "name": "Pieces", "value": "1"}
      ]
    }
    </script>
  </head>
  <body></body>
</html>"""


def _fake_amazon_response() -> dict[str, object]:
    return {
        "SearchResult": {
            "Items": [
                {
                    "ASIN": "B00TEST123",
                    "DetailPageURL": "https://www.amazon.com/dp/B00TEST123",
                    "Images": {
                        "Primary": {
                            "Large": {"URL": "https://example.com/amazon-rod.jpg"},
                            "Medium": {"URL": "https://example.com/amazon-rod-med.jpg"},
                        }
                    },
                    "ItemInfo": {
                        "Title": {"DisplayValue": "Amazon Rod"},
                        "ByLineInfo": {"Brand": {"DisplayValue": "Amazon"}},
                        "Features": {"DisplayValues": ["8-foot", "Medium Heavy", "Fast"]},
                    },
                    "OffersV2": {
                        "Listings": [
                            {
                                "Price": {"DisplayAmount": "$99.99"},
                                "Availability": {"Message": {"DisplayValue": "In Stock"}},
                            }
                        ]
                    },
                }
            ]
        }
    }


def _fake_walmart_response() -> dict[str, object]:
    return {
        "items": [
            {
                "itemId": "WM123",
                "name": "Walmart Lure",
                "brand": "Walmart",
                "url": "https://www.walmart.com/ip/WM123",
                "image": {"large": "https://example.com/walmart-lure.jpg"},
                "price": "$7.49",
                "availability": "In stock",
                "upc": "123456789012",
            }
        ]
    }


class _FakeResponse:
    def __init__(self, html: str, url: str = "https://example.com/product") -> None:
        self._html = html.encode("utf-8")
        self.url = url
        self.history = []
        self.encoding = "utf-8"
        self.headers = {"content-type": "text/html; charset=utf-8"}

    def iter_content(self, chunk_size: int = 65536):
        for idx in range(0, len(self._html), chunk_size):
            yield self._html[idx:idx + chunk_size]

    def close(self) -> None:
        return None


def main() -> int:
    errors: list[str] = []

    for rel in ("app.py", "angler_species_rigs_v43.py", "gear/inventory.py", "gear/catalog_providers.py", "gear/product_url_import.py", "gear/settings.py", "templates/tackle_locker.html", "static/js/tackle_locker_v610.js"):
        path = ROOT / rel
        if not path.exists():
            errors.append(f"Missing {rel}")
        elif path.stat().st_size <= 0:
            errors.append(f"Empty {rel}")

    version_marker = ROOT / "data" / "version_v6_12_gear_management_url_assist.json"
    if not version_marker.exists():
        errors.append("Missing version_v6_12_gear_management_url_assist.json")
    else:
        try:
            marker = json.loads(version_marker.read_text(encoding="utf-8"))
            if marker.get("version") != "v6.12-gear-management-url-assist":
                errors.append("Version marker has unexpected version label")
        except Exception as exc:
            errors.append(f"Version marker could not be parsed: {exc}")

    for rel in ("app.py", "angler_species_rigs_v43.py", "gear/inventory.py", "gear/catalog_providers.py", "gear/product_url_import.py", "gear/settings.py"):
        try:
            ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

    for rel in (
        "static/gear/providers/amazon.svg",
        "static/gear/providers/walmart.svg",
        "static/gear/providers/structured.svg",
        "static/gear/providers/local.svg",
        "static/gear/providers/manual.svg",
        "static/gear/providers/cache.svg",
    ):
        path = ROOT / rel
        if not path.exists() or path.stat().st_size <= 0:
            errors.append(f"Missing provider icon {rel}")

    if not (ROOT / "templates" / "tackle_locker.html").read_text(encoding="utf-8").find("gearSearchScope") >= 0:
        errors.append("tackle locker template is missing search scope control")
    template_text = (ROOT / "templates" / "tackle_locker.html").read_text(encoding="utf-8")
    for needle in ("gearSearchScope", "gearProductUrl", "gearImportUrlButton", "gearOnlineLookup", "gearDefaultScope", "My Tackle Locker"):
        if needle not in template_text:
            errors.append(f"tackle locker template missing {needle}")
    for needle in ("gearImportQuery", "gearImageUpload", "gearImagePreview"):
        if needle not in template_text:
            errors.append(f"tackle locker template missing {needle}")
    for needle in ("data-gear-action=\"retire\"", "data-gear-action=\"delete\"", "gear-danger-button"):
        if needle not in template_text:
            errors.append(f"tackle locker template missing {needle}")
    if "/admin" in template_text:
        errors.append("Admin should not be present in tackle locker nav")

    js_text = (ROOT / "static" / "js" / "tackle_locker_v610.js").read_text(encoding="utf-8")
    for needle in ("searchCatalog", "importFromUrl", "saveSettings", "gearSearchScope", "gearImportUrlButton", "providerIconFor", "gear-provider-grid"):
        if needle not in js_text:
            errors.append(f"tackle locker JS missing {needle}")

    style_text = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
    for needle in ("gear-provider-icon", "gear-provider-grid", "gear-provider-card"):
        if needle not in style_text:
            errors.append(f"style.css missing {needle}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        inventory_path = tmp / "gear_inventory.json"
        cache_path = tmp / "gear_catalog_cache.json"
        settings_path = tmp / "gear_settings.json"
        _write_json(inventory_path, {"version": "v6.12-gear-management-url-assist", "updated_at": "2026-07-15T00:00:00", "items": [], "maintenance": [], "catalog_cache": []})
        _write_json(cache_path, {"version": "v6.12-gear-management-url-assist", "updated_at": "2026-07-15T00:00:00", "products": []})
        _write_json(settings_path, {
            "version": "v6.12-gear-management-url-assist",
            "updated_at": "2026-07-15T00:00:00",
            "search_scope_default": "both",
            "online_lookup_enabled": False,
            "enabled_providers": {"structured": True, "manufacturer": False, "walmart": False, "amazon": False},
            "allow_remote_images": True,
            "cache_lookup_results": True,
            "cache_duration_days": 30,
            "prefer_manufacturer_specs": True,
        })
        os.environ["AI_GEAR_INVENTORY_PATH"] = str(inventory_path)
        os.environ["AI_GEAR_CATALOG_CACHE_PATH"] = str(cache_path)
        os.environ["AI_GEAR_SETTINGS_PATH"] = str(settings_path)

        from app import app as flask_app

        client = flask_app.test_client()

        manual_payload = {
            "category": "rod",
            "brand": "St. Croix",
            "model": "Mojo Bass",
            "display_name": "St. Croix Mojo Bass 7'1\" MH Fast",
            "status": "owned",
            "notes": "Manual QC rod",
            "length_ft": 7.08,
            "length_label": "7'1\"",
            "power": "medium_heavy",
            "action": "fast",
            "lure_weight_min_oz": 0.375,
            "lure_weight_max_oz": 1.0,
            "line_rating_min_lb": 12,
            "line_rating_max_lb": 20,
            "technique_tags": "spinnerbait, jig",
            "species_tags": "largemouth_bass, smallmouth_bass",
        }
        created = client.post("/api/gear/items", json=manual_payload)
        if created.status_code != 200:
            errors.append(f"Manual gear create failed: HTTP {created.status_code}")
        else:
            item = (created.get_json(silent=True) or {}).get("item", {})
            if item.get("display_name") != manual_payload["display_name"]:
                errors.append("Manual gear create did not persist display name")

        retire_test = client.post("/api/gear/items", json={
            "category": "lure",
            "brand": "Test",
            "model": "Delete Me",
            "display_name": "Test Delete Me",
            "status": "owned",
        })
        retire_item = (retire_test.get_json(silent=True) or {}).get("item", {})
        if not retire_item.get("id"):
            errors.append("Delete test item was not created")
        else:
            retired = client.post(f"/api/gear/items/{retire_item['id']}/retire")
            if retired.status_code != 200:
                errors.append("Retire route failed")
            deleted = client.post(f"/api/gear/items/{retire_item['id']}/delete")
            if deleted.status_code != 200:
                errors.append("Delete route failed")

        local = client.get("/api/gear/search", query_string={"q": "Mojo Bass", "scope": "local", "category": "rod"})
        if local.status_code != 200:
            errors.append(f"Local search failed: HTTP {local.status_code}")
        else:
            data = local.get_json(silent=True) or {}
            if not data.get("local", {}).get("owned"):
                errors.append("Local search should return owned gear")

        online = client.get("/api/gear/search", query_string={"q": "Mojo Bass", "scope": "online", "category": "rod"})
        if online.status_code != 200:
            errors.append(f"Online search failed: HTTP {online.status_code}")
        else:
            data = online.get_json(silent=True) or {}
            if data.get("online", {}).get("count", -1) != 0:
                errors.append("Online search should be calm when providers are disabled")
            if not any("disabled" in msg.lower() or "unavailable" in msg.lower() for msg in data.get("messages", [])):
                errors.append("Online search should explain when providers are unavailable")

        both = client.get("/api/gear/search", query_string={"q": "Mojo Bass", "scope": "both", "category": "rod"})
        if both.status_code != 200:
            errors.append(f"Both search failed: HTTP {both.status_code}")
        else:
            data = both.get_json(silent=True) or {}
            if not data.get("local", {}).get("owned"):
                errors.append("Both search should return local matches first")

        page = client.get("/rigs")
        if page.status_code != 200:
            errors.append(f"/rigs failed: HTTP {page.status_code}")
        else:
            html = page.get_data(as_text=True)
            for needle in ("gearSearchScope", "gearProductUrl", "gearImportUrlButton", "gearOnlineLookup", "gearDefaultScope", "My Tackle Locker", "Fishing Rig Reference"):
                if needle not in html:
                    errors.append(f"/rigs missing {needle}")
            if "/admin" in html:
                errors.append("Admin should not be in tackle locker nav")

        import gear.product_url_import as product_url_import  # noqa: F401
        with mock.patch("gear.product_url_import.requests.get") as fake_get:
            fake_get.return_value = _FakeResponse(_fake_product_html(), url="https://www.stcroixrods.com/mojo-bass")
            imported = client.post("/api/gear/import/url", json={"url": "https://www.stcroixrods.com/mojo-bass", "category": "rod"})
        if imported.status_code != 200:
            errors.append(f"URL import failed: HTTP {imported.status_code}")
        else:
            data = imported.get_json(silent=True) or {}
            product = data.get("product") if isinstance(data, dict) else {}
            if not isinstance(product, dict) or product.get("brand") != "St. Croix":
                errors.append("URL import did not normalize manufacturer brand")
            if product.get("provider") != "structured":
                errors.append("URL import should normalize as structured provider")
            if not product.get("source_url"):
                errors.append("URL import should retain source URL")
            if not data.get("duplicate_matches"):
                errors.append("URL import should flag duplicate locker matches")
            if not product.get("image_url") and not product.get("image"):
                errors.append("URL import should preserve or fallback image data")
            if not product.get("length_ft") or not product.get("length_label"):
                errors.append("URL import should infer rod length")
            if not product.get("power") or not product.get("action"):
                errors.append("URL import should infer rod power and action")
            if not product.get("lure_weight_min_oz") or not product.get("line_rating_min_lb"):
                errors.append("URL import should infer rod lure and line ratings")
            if not product.get("import_summary"):
                errors.append("URL import should provide a summary for review")

        generic_html = """<!doctype html><html><head><title>Site Maintenance</title></head><body><p>Maintenance</p></body></html>"""
        query_match = {
            "provider": "structured",
            "provider_product_id": "query-match-rod",
            "source_name": "Structured product page",
            "source_url": "https://example.com/query-match",
            "category": "rod",
            "brand": "St. Croix",
            "model": "Legend Tournament Bass",
            "display_name": "St. Croix Legend Tournament Bass 7'1\" MH Fast",
            "image_url": "https://example.com/query-match.jpg",
            "confidence": "high",
            "length_label": "7'1\"",
            "power": "medium_heavy",
            "action": "fast",
        }
        with mock.patch("gear.product_url_import.requests.get") as fake_get, mock.patch("angler_species_rigs_v43.search_gear_catalog") as fake_search:
            fake_get.return_value = _FakeResponse(generic_html, url="https://example.com/maintenance")
            fake_search.return_value = {
                "local": {"owned": [], "cached": []},
                "online": {"matches": [query_match], "count": 1},
                "messages": [],
            }
            imported = client.post("/api/gear/import/url", json={
                "url": "https://example.com/maintenance",
                "category": "rod",
                "query": "7'1 medium heavy fast rod",
            })
        if imported.status_code != 200:
            errors.append(f"Query fallback URL import failed: HTTP {imported.status_code}")
        else:
            data = imported.get_json(silent=True) or {}
            product = data.get("product") if isinstance(data, dict) else {}
            if product.get("brand") != "St. Croix" or "Legend Tournament Bass" not in str(product.get("display_name", "")):
                errors.append("Query fallback should fill brand/model from a suggested match")
            if not data.get("query_matches"):
                errors.append("Query fallback should return suggested matches")
            if not product.get("query_match_applied"):
                errors.append("Query fallback should mark the applied match")

        upload = client.post(
            "/api/gear/upload-image",
            data={"image": (BytesIO(b"fake image bytes"), "rod.png")},
            content_type="multipart/form-data",
        )
        if upload.status_code != 200:
            errors.append(f"Image upload failed: HTTP {upload.status_code}")
        else:
            data = upload.get_json(silent=True) or {}
            if not data.get("image_url", "").startswith("/api/gear/uploads/"):
                errors.append("Image upload should return a local image URL")

        blocked = client.post("/api/gear/import/url", json={"url": "http://127.0.0.1/", "category": "rod"})
        if blocked.status_code == 200:
            errors.append("Private localhost URL should be rejected")

        settings_res = client.get("/api/gear/settings")
        if settings_res.status_code != 200:
            errors.append(f"/api/gear/settings failed: HTTP {settings_res.status_code}")
        else:
            data = settings_res.get_json(silent=True) or {}
            if not data.get("providers"):
                errors.append("Gear settings should expose provider health")

        os.environ["AI_AMAZON_PAAPI_ACCESS_KEY"] = "AKIATEST"
        os.environ["AI_AMAZON_PAAPI_SECRET_KEY"] = "SECRET"
        os.environ["AI_AMAZON_PAAPI_PARTNER_TAG"] = "anglerintel-20"
        from gear.providers.amazon_provider import AmazonCatalogProvider
        amazon = AmazonCatalogProvider()
        with mock.patch("gear.providers.amazon_provider.requests.post") as fake_post:
            fake_post.return_value = mock.Mock(
                status_code=200,
                json=lambda: _fake_amazon_response(),
                raise_for_status=lambda: None,
            )
            amazon_results = amazon.search("bass rod", category="rod", limit=5)
        if not amazon_results or amazon_results[0].get("image_url") != "https://example.com/amazon-rod.jpg":
            errors.append("Amazon provider did not normalize live search results")

        os.environ["AI_WALMART_API_SEARCH_URL"] = "https://example.com/walmart/search"
        from gear.providers.walmart_provider import WalmartCatalogProvider
        walmart = WalmartCatalogProvider()
        with mock.patch("gear.providers.walmart_provider.requests.get") as fake_get:
            fake_get.return_value = mock.Mock(
                status_code=200,
                json=lambda: _fake_walmart_response(),
                raise_for_status=lambda: None,
            )
            walmart_results = walmart.search("spinnerbait", category="lure", limit=5)
        if not walmart_results or walmart_results[0].get("image_url") != "https://example.com/walmart-lure.jpg":
            errors.append("Walmart provider did not normalize live search results")

    if errors:
        print("QC FAILED: gear catalog search")
        for error in errors:
            print(f"- {error}")
        return 1

    print("QC PASSED: gear catalog search")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
