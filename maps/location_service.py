"""Key-free location helpers for RAASTA AI.

Place lookup uses OpenStreetMap Nominatim and requires no API key. Walking time
is an estimate from straight-line distance because the final project purposely
does not depend on a routing API. The map itself displays only the start and
end pins, never a made-up path.
"""
import json
import math
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "RAASTA-AI/1.0 (student public-transport project)"
LAHORE_BOUNDS = (31.35, 74.05, 31.72, 74.55)


def _read_json(url, headers=None, timeout=12):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _looks_like_lahore(lat, lon):
    min_lat, min_lon, max_lat, max_lon = LAHORE_BOUNDS
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def geocode_place(place_name):
    """Resolve a typed Lahore place using OpenStreetMap; no key is required."""
    place_name = (place_name or "").strip()
    if not place_name:
        return None
    query = place_name if "lahore" in place_name.lower() else f"{place_name}, Lahore, Pakistan"
    try:
        params = urllib.parse.urlencode({
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "pk",
        })
        data = _read_json(f"{NOMINATIM_URL}?{params}", headers={"User-Agent": USER_AGENT})
        if data:
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            if _looks_like_lahore(lat, lon):
                return {
                    "name": data[0].get("display_name", place_name),
                    "lat": lat,
                    "lon": lon,
                    "provider": "OpenStreetMap",
                }
    except Exception:
        pass
    return None


def haversine_km(lat1, lon1, lat2, lon2):
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def walking_route(origin, destination):
    """Estimate walking distance/time without drawing a route line."""
    distance = haversine_km(origin["lat"], origin["lon"], destination["lat"], destination["lon"])
    walking_km = distance * 1.2
    duration = max(1, round((walking_km / 4.5) * 60)) if walking_km > 0.02 else 0
    return {
        "distance_km": round(walking_km, 2),
        "duration_min": duration,
        "provider": "estimated",
    }
