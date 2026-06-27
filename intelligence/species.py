SPECIES = [
    {"name": "Largemouth Bass", "habitat": ["pond", "lake", "reservoir"], "temp": (65, 85)},
    {"name": "Smallmouth Bass", "habitat": ["river", "lake"], "temp": (55, 75)},
    {"name": "Crappie", "habitat": ["pond", "lake", "reservoir"], "temp": (58, 75)},
    {"name": "Bluegill", "habitat": ["pond", "lake"], "temp": (60, 88)},
    {"name": "Channel Catfish", "habitat": ["pond", "lake", "river"], "temp": (70, 92)},
    {"name": "Flathead Catfish", "habitat": ["river", "large_lake"], "temp": (72, 92)},
    {"name": "Walleye", "habitat": ["river", "lake", "reservoir"], "temp": (50, 72)},
    {"name": "White Bass", "habitat": ["river", "lake", "reservoir"], "temp": (55, 78)},
    {"name": "Sauger", "habitat": ["river"], "temp": (45, 70)},
    {"name": "Common Carp", "habitat": ["pond", "lake", "river"], "temp": (55, 88)},
    {"name": "Yellow Perch", "habitat": ["lake"], "temp": (50, 70)},
    {"name": "Northern Pike", "habitat": ["natural_lake", "river"], "temp": (45, 70)},
    {"name": "Muskie", "habitat": ["natural_lake", "river"], "temp": (55, 75)},
    {"name": "Rainbow Trout", "habitat": ["stocked_lake", "cold_stream"], "temp": (45, 62)},
    {"name": "Brown Trout", "habitat": ["cold_stream", "stocked_lake"], "temp": (45, 62)},
]

def clamp(n):
    return max(0, min(100, int(round(n))))

def rating(score):
    if score >= 80:
        return "Excellent"
    if score >= 65:
        return "Good"
    if score >= 45:
        return "Fair"
    return "Slow"

def score_species(species, temp_f, wind_mph, pressure_inhg, area_type):
    low, high = species["temp"]
    s = 50

    if low <= temp_f <= high:
        s += 25
    else:
        s -= 15

    if area_type in species["habitat"]:
        s += 15
    else:
        s -= 30

    if species["name"] in ["Northern Pike", "Muskie"] and area_type in ["pond", "reservoir"]:
        s -= 35

    if "Trout" in species["name"] and temp_f > 65:
        s -= 45

    if 5 <= wind_mph <= 15:
        s += 6

    if pressure_inhg < 29.9:
        s += 8

    return clamp(s)
