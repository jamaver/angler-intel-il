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

def overall_score(temp_f, wind_mph, pressure_inhg, cloud):
    s = 50

    if 60 <= temp_f <= 80:
        s += 20
    elif temp_f < 40 or temp_f > 92:
        s -= 20

    if 5 <= wind_mph <= 15:
        s += 12
    elif wind_mph > 22:
        s -= 18

    if pressure_inhg < 29.90:
        s += 12
    elif pressure_inhg > 30.25:
        s -= 10

    if 40 <= cloud <= 85:
        s += 6

    return clamp(s)

def time_blocks(base_score, temp_f, wind_mph):
    morning = base_score + 8
    midday = base_score - 12
    evening = base_score + 12

    if temp_f > 84:
        midday -= 15
        evening += 5

    if wind_mph > 20:
        midday -= 10

    return [
        {"label": "Morning", "time": "5 AM - 10 AM", "score": clamp(morning)},
        {"label": "Midday", "time": "10 AM - 4 PM", "score": clamp(midday)},
        {"label": "Evening", "time": "4 PM - 9 PM", "score": clamp(evening)},
    ]

def hourly_bite_forecast(hourly, f_temp, mph, inhg):
    results = []

    times = hourly.get("time", [])[:24]
    temps = hourly.get("temperature_2m", [])[:24]
    winds = hourly.get("wind_speed_10m", [])[:24]
    pressures = hourly.get("pressure_msl", [])[:24]
    clouds = hourly.get("cloud_cover", [])[:24]

    for i, t in enumerate(times):
        hour = int(t.split("T")[1].split(":")[0])

        temp = f_temp(temps[i])
        wind = mph(winds[i])
        pressure = inhg(pressures[i])
        cloud = clouds[i]

        s = overall_score(temp, wind, pressure, cloud)

        if 5 <= hour <= 9:
            s += 10
        elif 10 <= hour <= 15:
            s -= 12
        elif 16 <= hour <= 21:
            s += 14

        if temp > 85 and 11 <= hour <= 16:
            s -= 12

        if wind > 22:
            s -= 10

        results.append({
            "time": t,
            "hour": hour,
            "score": clamp(s),
            "rating": rating(clamp(s))
        })

    return results
