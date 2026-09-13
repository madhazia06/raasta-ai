"""
RAASTA AI - maps/geocoding.py

Fills in the empty latitude/longitude columns in data/stops.csv by looking
up each stop name against OpenStreetMap's free Nominatim geocoding service.

No API key needed, no extra pip installs needed (uses only Python's built-in
urllib) -- deliberately kept dependency-free since this only needs to run
once (or occasionally, when new stops are added).

IMPORTANT -- Nominatim's usage policy requires:
  1. Maximum 1 request per second (this script sleeps 1.1s between calls)
  2. A real User-Agent header identifying your app (set below)
Breaking these rules can get your IP temporarily blocked by the free service.
214 stops will take about 4 minutes to run -- that's expected, not a bug.

Usage:
    python3 geocoding.py
    -> reads ../data/stops.csv
    -> writes ../data/stops_geocoded.csv (a NEW file, doesn't overwrite
       your original -- review it, then rename it to stops.csv yourself)

Safe to re-run: if you already have a partially-geocoded stops_geocoded.csv,
re-running will skip any stop that already has coordinates, so an
interrupted run can just be resumed by running the script again.
"""
import csv
import json
import os
import time
import urllib.parse
import urllib.request

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
INPUT_PATH = os.path.join(DATA_DIR, "stops.csv")
OUTPUT_PATH = os.path.join(DATA_DIR, "stops_geocoded.csv")

CITY_SUFFIX = ", Lahore, Pakistan"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "RAASTA-AI-Hackathon-Project/1.0 (student hackathon project)"
DELAY_SECONDS = 1.1  # Nominatim policy: max 1 request/sec, add a small buffer


def geocode_one(place_name):
    """
    Look up one place name and return (lat, lon) as strings, or (None, None)
    if nothing was found or the request failed.
    """
    query = place_name + CITY_SUFFIX
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "limit": 1,
    })
    url = f"{NOMINATIM_URL}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"  ERROR looking up '{place_name}': {e}")
        return None, None

    if not data:
        return None, None

    return data[0]["lat"], data[0]["lon"]


def load_existing_output():
    """If stops_geocoded.csv already exists from a previous run, load it so
    we can skip stops that are already done."""
    if not os.path.exists(OUTPUT_PATH):
        return {}
    with open(OUTPUT_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return {r["stop_id"]: r for r in rows}


def run():
    with open(INPUT_PATH, encoding="utf-8-sig") as f:
        stops = list(csv.DictReader(f))
        fieldnames = list(stops[0].keys())

    existing = load_existing_output()

    not_found = []
    newly_geocoded = 0
    already_done = 0

    for stop in stops:
        sid = stop["stop_id"]

        # Resume support: skip if we already have coordinates from a prior run
        if sid in existing and existing[sid].get("latitude"):
            stop["latitude"] = existing[sid]["latitude"]
            stop["longitude"] = existing[sid]["longitude"]
            already_done += 1
            continue

        print(f"Geocoding [{sid}] {stop['stop_name']} ...")
        lat, lon = geocode_one(stop["stop_name"])

        if lat is None:
            print(f"  NOT FOUND: {stop['stop_name']}")
            not_found.append(stop["stop_name"])
        else:
            stop["latitude"] = lat
            stop["longitude"] = lon
            newly_geocoded += 1

        # Write progress after EVERY stop, not just at the end -- so if the
        # script crashes or you Ctrl+C it partway through, nothing is lost
        # and re-running picks up where it left off.
        with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(stops)

        time.sleep(DELAY_SECONDS)

    print("\n" + "=" * 60)
    print(f"Done. Already had coordinates: {already_done}")
    print(f"Newly geocoded this run: {newly_geocoded}")
    print(f"Not found: {len(not_found)}")
    if not_found:
        print("\nThese stops need a MANUAL lookup (couldn't be auto-found):")
        for name in not_found:
            print(f"  - {name}")
        print(
            "\nTip: search these manually on https://www.openstreetmap.org "
            "or Google Maps, then edit their row directly in "
            "stops_geocoded.csv."
        )
    print(f"\nOutput written to: {OUTPUT_PATH}")
    print(
        "Review it, then rename/replace data/stops.csv with this file "
        "once you're satisfied with the results."
    )


if __name__ == "__main__":
    run()
