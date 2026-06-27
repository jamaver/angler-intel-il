import pgeocode

nomi = pgeocode.Nominatim("us")

def get_coords(zip_code):
    loc = nomi.query_postal_code(zip_code)
    if loc is None or str(loc.latitude) == "nan":
        return None
    return {
        "zip": zip_code,
        "city": str(loc.place_name),
        "state": str(loc.state_name),
        "lat": float(loc.latitude),
        "lon": float(loc.longitude)
    }
