"""
RAASTA AI - maps/geocoding_fallback_fill.py

Runs LAST, after geocoding.py and geocoding_retry.py. Guarantees every
single stop in stops_geocoded.csv ends up with SOME coordinate -- no blanks
left anywhere -- by estimating position from each stop's neighbors in the
route sequence, instead of leaving it empty or requiring manual lookup.

How the estimate works, per still-missing stop:
  1. Look at every route this stop belongs to (via route_stops.csv).
  2. On each of those routes, find the nearest stop BEFORE it and the
     nearest stop AFTER it that already has real coordinates.
  3. If both neighbors are known: interpolate a point on the straight line
     between them, positioned proportionally (e.g. if the missing stop is
     stop #3 of 5 between two known points, it lands 40% of the way along
     that line).
  4. If only one neighbor is known: just use that neighbor's coordinates
     directly (close enough for a hackathon demo -- consecutive bus stops
     are rarely more than a few hundred meters apart).
  5. If a stop has genuinely no known neighbor anywhere (shouldn't happen
     with this dataset, but handled just in case): falls back to Lahore's
     city center coordinates, clearly flagged so it's obvious this one
     needs a real manual look later.

Every estimated row is clearly labeled in `geocode_method` as one of:
  interpolated_between_neighbors | nearest_neighbor_only | city_center_fallback
...so nobody mistakes an estimate for a real geocoded match later.

Usage:
    python3 geocoding_fallback_fill.py
    -> reads/updates data/stops_geocoded.csv in place (fills ALL blanks)
    -> reads data/route_stops.csv (read-only, just for sequence info)
"""
import csv
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STOPS_PATH = os.path.join(DATA_DIR, "stops_geocoded.csv")
ROUTE_STOPS_PATH = os.path.join(DATA_DIR, "route_stops.csv")

# Lahore city center (Data Darbar area) -- last-resort fallback only
LAHORE_CENTER = ("31.5825", "74.3100")


def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_route_sequences(route_stops_rows):
    """route_id -> ordered list of stop_id"""
    routes = {}
    for row in sorted(route_stops_rows, key=lambda r: (r["route_id"], int(r["stop_sequence"]))):
        routes.setdefault(row["route_id"], []).append(row["stop_id"])
    return routes


def find_neighbors(stop_id, routes_containing, sequences, coords):
    """
    For a given stop, look across every route it's on and find the closest
    known-coordinate neighbor before and after it in sequence.
    Returns (before_coord_or_None, after_coord_or_None, steps_before, steps_after).
    """
    best_before, best_after = None, None
    best_steps_before, best_steps_after = None, None

    for route_id in routes_containing:
        seq = sequences.get(route_id, [])
        if stop_id not in seq:
            continue
        idx = seq.index(stop_id)

        # search backwards for nearest known stop
        for steps, i in enumerate(range(idx - 1, -1, -1), start=1):
            if seq[i] in coords:
                if best_before is None or steps < best_steps_before:
                    best_before = coords[seq[i]]
                    best_steps_before = steps
                break

        # search forwards for nearest known stop
        for steps, i in enumerate(range(idx + 1, len(seq)), start=1):
            if seq[i] in coords:
                if best_after is None or steps < best_steps_after:
                    best_after = coords[seq[i]]
                    best_steps_after = steps
                break

    return best_before, best_after, best_steps_before, best_steps_after


def interpolate(before, after, steps_before, steps_after):
    """Linear interpolation between two (lat, lon) points, weighted by position."""
    total_steps = steps_before + steps_after
    fraction = steps_before / total_steps
    lat = float(before[0]) + fraction * (float(after[0]) - float(before[0]))
    lon = float(before[1]) + fraction * (float(after[1]) - float(before[1]))
    return f"{lat:.6f}", f"{lon:.6f}"


def run():
    stops = load_csv(STOPS_PATH)
    route_stops = load_csv(ROUTE_STOPS_PATH)
    sequences = build_route_sequences(route_stops)

    fieldnames = list(stops[0].keys())
    if "geocode_method" not in fieldnames:
        fieldnames.append("geocode_method")

    # stop_id -> (lat, lon) for every stop that ALREADY has real coordinates
    coords = {s["stop_id"]: (s["latitude"], s["longitude"]) for s in stops if s.get("latitude")}

    # stop_id -> list of route_ids it appears on
    stop_to_routes = {}
    for row in route_stops:
        stop_to_routes.setdefault(row["stop_id"], []).append(row["route_id"])

    filled_interpolated = 0
    filled_single_neighbor = 0
    filled_city_center = 0

    for stop in stops:
        if stop.get("latitude"):
            continue  # already has coordinates, skip

        sid = stop["stop_id"]
        routes_containing = stop_to_routes.get(sid, [])
        before, after, steps_before, steps_after = find_neighbors(
            sid, routes_containing, sequences, coords
        )

        if before and after:
            lat, lon = interpolate(before, after, steps_before, steps_after)
            stop["latitude"], stop["longitude"] = lat, lon
            stop["geocode_method"] = "interpolated_between_neighbors"
            filled_interpolated += 1
        elif before or after:
            lat, lon = before or after
            stop["latitude"], stop["longitude"] = lat, lon
            stop["geocode_method"] = "nearest_neighbor_only"
            filled_single_neighbor += 1
        else:
            stop["latitude"], stop["longitude"] = LAHORE_CENTER
            stop["geocode_method"] = "city_center_fallback"
            filled_city_center += 1

        # so later stops can potentially use THIS stop's new estimate as a neighbor too
        coords[sid] = (stop["latitude"], stop["longitude"])

    with open(STOPS_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(stops)

    print("=" * 60)
    print("Fallback fill complete. Every stop now has coordinates.")
    print(f"  Interpolated between two known neighbors: {filled_interpolated}")
    print(f"  Estimated from a single known neighbor: {filled_single_neighbor}")
    print(f"  Fell back to city-center (needs manual fix): {filled_city_center}")
    print(f"\nUpdated: {STOPS_PATH}")
    print(
        "\nAll rows are labeled in the geocode_method column, so anyone on "
        "your team can filter for exact matches vs. estimates if precision "
        "matters for a specific feature."
    )


if __name__ == "__main__":
    run()
