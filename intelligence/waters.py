import requests
import math

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]

def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return r * c

def classify_water(tags):
    waterway = tags.get("waterway", "")
    water = tags.get("water", "")
    natural = tags.get("natural", "")
    landuse = tags.get("landuse", "")
    leisure = tags.get("leisure", "")

    if waterway in ["river", "stream", "canal", "ditch"]:
        return "river"

    if water in ["reservoir"] or landuse == "reservoir":
        return "reservoir"

    if water in ["pond", "basin"] or natural == "water" and water == "pond":
        return "pond"

    if leisure == "fishing":
        return "fishing_area"

    if natural == "water":
        return "lake"

    return "water"

def center_of_element(e):
    if "center" in e:
        return e["center"].get("lat"), e["center"].get("lon")

    if "lat" in e and "lon" in e:
        return e.get("lat"), e.get("lon")

    return None, None

def build_query(lat, lon, radius_m=25000):
    return f"""
    [out:json][timeout:20];
    (
      node["natural"="water"](around:{radius_m},{lat},{lon});
      way["natural"="water"](around:{radius_m},{lat},{lon});
      relation["natural"="water"](around:{radius_m},{lat},{lon});

      node["water"](around:{radius_m},{lat},{lon});
      way["water"](around:{radius_m},{lat},{lon});
      relation["water"](around:{radius_m},{lat},{lon});

      node["waterway"](around:{radius_m},{lat},{lon});
      way["waterway"](around:{radius_m},{lat},{lon});
      relation["waterway"](around:{radius_m},{lat},{lon});

      node["landuse"="reservoir"](around:{radius_m},{lat},{lon});
      way["landuse"="reservoir"](around:{radius_m},{lat},{lon});
      relation["landuse"="reservoir"](around:{radius_m},{lat},{lon});

      node["leisure"="fishing"](around:{radius_m},{lat},{lon});
      way["leisure"="fishing"](around:{radius_m},{lat},{lon});
      relation["leisure"="fishing"](around:{radius_m},{lat},{lon});
    );
    out center tags 80;
    """

def fetch_overpass(query):
    for url in OVERPASS_URLS:
        try:
            r = requests.post(url, data={"data": query}, timeout=25)
            r.raise_for_status()
            return r.json()
        except Exception:
            continue

    return {"elements": []}

def detect_water(lat, lon):
    query = build_query(lat, lon)
    data = fetch_overpass(query)

    waters = []

    for e in data.get("elements", []):
        tags = e.get("tags", {})
        water_type = classify_water(tags)

        if water_type in ["ditch"]:
            continue

        c_lat, c_lon = center_of_element(e)
        if c_lat is None or c_lon is None:
            continue

        name = tags.get("name")
        if not name:
            name = f"Unnamed {water_type}"

        distance = haversine_miles(lat, lon, c_lat, c_lon)

        waters.append({
            "name": name,
            "type": water_type,
            "distance": round(distance, 1),
            "lat": round(c_lat, 6),
            "lon": round(c_lon, 6)
        })

    seen = set()
    clean = []

    for w in sorted(waters, key=lambda x: x["distance"]):
        key = (w["name"], w["type"], w["lat"], w["lon"])
        if key not in seen:
            seen.add(key)
            clean.append(w)

    return clean[:12]

def infer_area_type(waters):
    types = [w["type"] for w in waters]

    if "river" in types:
        return "river"
    if "reservoir" in types:
        return "reservoir"
    if "lake" in types:
        return "lake"
    if "pond" in types:
        return "pond"
    if "fishing_area" in types:
        return "pond"

    return "pond"
