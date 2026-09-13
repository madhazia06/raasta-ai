"""
RAASTA AI - maps/geocoding_retry.py

Runs AFTER geocoding.py. Picks up any stop in data/stops_geocoded.csv that
still has no coordinates, and tries harder using two extra tricks:

  1. Bounding box search: restricts the search to Lahore's approximate
     geographic box, instead of relying on the place name containing
     "Lahore" as text. This helps a lot with minor local landmarks that
     exist in the map data but aren't tagged with the city name.
  2. Suffix stripping: local informal names like "IBA Stop" or "Pindi Stop"
     often aren't indexed with generic words like "Stop"/"Morr"/"Bridge"/
     "Interchange" attached -- so it also tries the name with these words
     removed.

Every stop's row gets a new `geocode_method` column recording exactly which
attempt succeeded (or "NOT_FOUND" if nothing worked) -- so you and your
team can see which coordinates are solid exact matches vs. which used a
looser fallback, and decide whether any need a manual double-check.

Usage:
    python3 geocoding_retry.py
    -> reads/updates data/stops_geocoded.csv in place
    -> still won't touch your original data/stops.csv
"""
import csv
import json
import os
import time
import urllib.parse
import urllib.request

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TARGET_PATH = os.path.join(DATA_DIR, "stops_geocoded.csv")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "RAASTA-AI-Hackathon-Project/1.0 (student hackathon project)"
DELAY_SECONDS = 1.1

# Lahore's approximate bounding box: (min_lon, min_lat, max_lon, max_lat)
LAHORE_BBOX = (74.10, 31.30, 74.50, 31.70)

# Generic filler words that often aren't part of a place's actual map name
STRIP_SUFFIXES = ["Stop", "Morr", "Bridge", "Interchange", "Road"]


def strip_generic_suffix(name):
    """Remove a trailing generic word like 'Stop' or 'Morr' if present.
    Returns None if no such suffix was found (nothing to try)."""
    words = name.split()
    if len(words) > 1 and words[-1] in STRIP_SUFFIXES:
        return " ".join(words[:-1])
    return None


def call_nominatim(query, use_bbox=False):
    params = {"q": query, "format": "json", "limit": 1}
    if use_bbox:
        params["viewbox"] = ",".join(str(x) for x in LAHORE_BBOX)
        params["bounded"] = 1
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"    ERROR: {e}")
        return None
    return data[0] if data else None


def try_harder(place_name):
    """
    Try multiple strategies in order, stopping at the first success.
    Returns (lat, lon, method_name) or (None, None, "NOT_FOUND").
    """
    attempts = [
        (f"{place_name}, Lahore, Pakistan", False, "bbox_with_city_name"),
        (place_name, True, "bbox_bounded_search"),
    ]

    stripped = strip_generic_suffix(place_name)
    if stripped:
        attempts.append((stripped, True, "stripped_suffix_bounded"))
        attempts.append((f"{stripped}, Lahore, Pakistan", False, "stripped_suffix_with_city"))

    for query, use_bbox, method in attempts:
        print(f"    trying [{method}]: '{query}'")
        result = call_nominatim(query, use_bbox=use_bbox)
        time.sleep(DELAY_SECONDS)
        if result:
            return result["lat"], result["lon"], method

    return None, None, "NOT_FOUND"


def run():
    with open(TARGET_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    if "geocode_method" not in fieldnames:
        fieldnames.append("geocode_method")

    # Mark existing successful rows as "original_pass" if not already labeled
    for row in rows:
        if row.get("latitude") and not row.get("geocode_method"):
            row["geocode_method"] = "original_pass"

    still_missing = [r for r in rows if not r.get("latitude")]
    print(f"Found {len(still_missing)} stops still missing coordinates. Retrying with extra strategies...\n")

    fixed = 0
    still_not_found = []

    for row in still_missing:
        print(f"Retrying [{row['stop_id']}] {row['stop_name']} ...")
        lat, lon, method = try_harder(row["stop_name"])

        if lat:
            row["latitude"] = lat
            row["longitude"] = lon
            row["geocode_method"] = method
            fixed += 1
            print(f"  FOUND via {method}")
        else:
            row["geocode_method"] = "NOT_FOUND"
            still_not_found.append(row["stop_name"])
            print(f"  still not found")

        # Save progress after every stop (resume-friendly, same as geocoding.py)
        with open(TARGET_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    print("\n" + "=" * 60)
    print(f"Retry complete. Fixed this round: {fixed}")
    print(f"Still not found: {len(still_not_found)}")
    if still_not_found:
        print("\nThese genuinely need a manual lookup (search openstreetmap.org or Google Maps):")
        for name in still_not_found:
            print(f"  - {name}")
    print(f"\nUpdated: {TARGET_PATH}")


if __name__ == "__main__":
    run()
