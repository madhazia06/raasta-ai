"""Location/geocoding helpers for the RAASTA AI Streamlit app.

Primary provider: Google Maps Geocoding + Directions when GOOGLE_MAPS_API_KEY
is configured. Fallback: OpenStreetMap Nominatim for geocoding and straight-line
walking estimates so the prototype still works without a paid API key.
"""

import json
import math
import urllib.parse
import urllib.request

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
GOOGLE_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "RAASTA-AI/1.0 (student public-transport project)"
LAHORE_BOUNDS = (31.35, 74.05, 31.72, 74.55)  # rough guardrail for fallback results


def _read_json(url, headers=None, timeout=12):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _looks_like_lahore(lat, lon):
    min_lat, min_lon, max_lat, max_lon = LAHORE_BOUNDS
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def geocode_place(place_name, google_api_key=None):
    """Resolve a user-entered Lahore place to coordinates.

    Returns a dict: {name, lat, lon, provider}, or None when not found.
    """
    place_name = (place_name or "").strip()
    if not place_name:
        return None

    query = place_name
    if "lahore" not in place_name.lower():
        query += ", Lahore, Pakistan"

    # Prefer Google because it generally understands local landmarks/businesses
    # better than a free geocoder.
    if google_api_key:
        try:
            params = urllib.parse.urlencode({
                "address": query,
                "key": google_api_key,
                "region": "pk",
            })
            data = _read_json(f"{GOOGLE_GEOCODE_URL}?{params}")
            if data.get("status") == "OK" and data.get("results"):
                item = data["results"][0]
                loc = item["geometry"]["location"]
                lat, lon = float(loc["lat"]), float(loc["lng"])
                if _looks_like_lahore(lat, lon):
                    return {
                        "name": item.get("formatted_address", place_name),
                        "lat": lat,
                        "lon": lon,
                        "provider": "Google Maps",
                    }
        except Exception:
            pass

    # Free fallback for development/demo use.
    try:
        params = urllib.parse.urlencode({
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "pk",
        })
        data = _read_json(
            f"{NOMINATIM_URL}?{params}",
            headers={"User-Agent": USER_AGENT},
        )
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


def _decode_polyline(encoded):
    """Decode a Google encoded polyline without adding another dependency."""
    points = []
    index = lat = lng = 0
    while index < len(encoded):
        for coord in ("lat", "lng"):
            result = shift = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if coord == "lat":
                lat += delta
            else:
                lng += delta
        points.append([lng / 1e5, lat / 1e5])
    return points


def walking_route(origin, destination, google_api_key=None):
    """Return walking info between two {lat, lon} points.

    The returned path is [[lon, lat], ...], suitable for PyDeck.
    """
    if google_api_key:
        try:
            params = urllib.parse.urlencode({
                "origin": f"{origin['lat']},{origin['lon']}",
                "destination": f"{destination['lat']},{destination['lon']}",
                "mode": "walking",
                "key": google_api_key,
            })
            data = _read_json(f"{GOOGLE_DIRECTIONS_URL}?{params}")
            if data.get("status") == "OK" and data.get("routes"):
                route = data["routes"][0]
                leg = route["legs"][0]
                return {
                    "distance_km": round(leg["distance"]["value"] / 1000, 2),
                    "duration_min": max(1, round(leg["duration"]["value"] / 60)),
                    "path": _decode_polyline(route["overview_polyline"]["points"]),
                    "provider": "Google Maps",
                }
        except Exception:
            pass

    distance = haversine_km(origin["lat"], origin["lon"], destination["lat"], destination["lon"])
    # Walking paths are normally longer than straight-line distance. 1.2 is a
    # conservative prototype estimate when Directions API is unavailable.
    walking_km = distance * 1.2
    duration = max(1, round((walking_km / 4.5) * 60))
    return {
        "distance_km": round(walking_km, 2),
        "duration_min": duration,
        "path": [[origin["lon"], origin["lat"]], [destination["lon"], destination["lat"]]],
        "provider": "estimated",
    }
