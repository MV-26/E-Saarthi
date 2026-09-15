def get_risk_level(safety_score: float):
    if safety_score >= 80:
        return "Low"
    elif safety_score >= 60:
        return "Medium"
    else:
        return "High"


def calculate_safety_score(
    crime_score: float,
    traffic_score: float,
    weather_score: float,
    road_score: float,
    accident_score: float
):
    score = (
        crime_score * 0.30 +
        traffic_score * 0.20 +
        weather_score * 0.15 +
        road_score * 0.20 +
        accident_score * 0.15
    )

    return round(score, 2)


def select_route_options(routes):
    if not routes:
        return {
            "safest": None,
            "balanced": None,
            "fastest": None
        }

    safest = max(routes, key=lambda r: r["safety_score"])

    fastest = min(routes, key=lambda r: r["duration_minutes"])

    min_duration = min(r["duration_minutes"] for r in routes)
    max_duration = max(r["duration_minutes"] for r in routes)

    if max_duration == min_duration:
        balanced = safest
    else:
        for route in routes:
            time_score = (
                (max_duration - route["duration_minutes"])
                / (max_duration - min_duration)
            ) * 100

            route["balanced_score"] = round(
                route["safety_score"] * 0.6
                + time_score * 0.4,
                2
            )

        balanced = max(routes, key=lambda r: r["balanced_score"])

    return {
        "safest": safest["route_id"],
        "balanced": balanced["route_id"],
        "fastest": fastest["route_id"]
    }