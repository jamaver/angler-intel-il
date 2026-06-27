import requests

def f_temp(c):
    return c * 9 / 5 + 32

def mph(kmh):
    return kmh * 0.621371

def inhg(hpa):
    return hpa * 0.02953

def get_weather(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,wind_speed_10m,pressure_msl,cloud_cover"
        "&hourly=temperature_2m,wind_speed_10m,pressure_msl,cloud_cover"
        "&daily=temperature_2m_max,temperature_2m_min,wind_speed_10m_max"
        "&forecast_days=7"
        "&timezone=auto"
    )
    r = requests.get(url, timeout=12)
    r.raise_for_status()
    return r.json()
