"""
ranking.py (UPDATED for the real RAASTA AI dataset)
------------------------------------------------------
Generates multiple route alternatives, labeled the way the app's feature
list describes: Fastest, Cheapest, Fewest Bus Changes, Least Walking.

WHAT CHANGED FROM THE ORIGINAL VERSION:
1. Added "Cheapest" -- the original version only had 3 of the app's 4
   promised preferences (it was missing this one entirely, since the
   placeholder data it was built against had no fare information at all).
   Now that graph.py loads real fares.csv data, this is possible.
2. Added get_ranked_routes_by_name() -- same ranking logic, but takes stop
   NAMES instead of raw GPS coordinates, using route_engine.find_route_by_name().
   This is what Member 3's chatbot should call.
3. The original get_ranked_routes(lat/lon version) is UNCHANGED and still
   works exactly as before.

HOW IT WORKS (plain English, same as before):
We run the route search a few times with different transfer-penalty
settings (a low penalty favours speed even with more bus changes; a high
penalty favours fewer bus changes even if slower). We then de-duplicate
the results and label the best of each category.
"""

from route_engine import find_route, find_route_by_name


CANDIDATE_SETTINGS = [
    ("low_penalty", 3),    # favors speed, tolerates transfers
    ("mid_penalty", 10),   # balanced
    ("high_penalty", 30),  # strongly avoids transfers
]


def _dedupe(candidates):
    unique = []
    seen = set()
    for c in candidates:
        key = (round(c.total_time_min, 1), c.transfers, round(c.total_walking_min, 1), round(c.total_fare_pkr, 1))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def _label_candidates(unique):
    """Shared logic: picks the best route per category and labels them,
    skipping duplicates (e.g. if the fastest route is ALSO the cheapest,
    it's only shown once, labeled 'Fastest')."""
    fastest = min(unique, key=lambda r: r.total_time_min)
    cheapest = min(unique, key=lambda r: (r.total_fare_pkr, r.total_time_min))
    fewest_transfers = min(unique, key=lambda r: (r.transfers, r.total_time_min))
    least_walking = min(unique, key=lambda r: (r.total_walking_min, r.total_time_min))

    labeled = []
    added_ids = set()

    for label, route in [
        ("Fastest", fastest),
        ("Cheapest", cheapest),
        ("Fewest Bus Changes", fewest_transfers),
        ("Least Walking", least_walking),
    ]:
        route_id = id(route)
        if route_id not in added_ids:
            labeled.append({"label": label, "route": route.to_dict()})
            added_ids.add(route_id)

    return labeled


def get_ranked_routes(graph, start_lat, start_lon, end_lat, end_lon):
    """
    Coordinate-based version (unchanged interface). Returns a list of
    labeled route alternatives, e.g. [{"label": "Fastest", "route": {...}}].
    Returns an empty list if no route could be found at all.
    """
    candidates = []
    for _, penalty in CANDIDATE_SETTINGS:
        result = find_route(graph, start_lat, start_lon, end_lat, end_lon, transfer_penalty_min=penalty)
        if result is not None:
            candidates.append(result)

    if not candidates:
        return []  # caller should show the "No Route Found" message

    return _label_candidates(_dedupe(candidates))


def get_ranked_routes_by_name(graph, start_name, end_name):
    """
    Name-based version -- this is what Member 3's chatbot should call.
    Returns the same shape as get_ranked_routes(), OR a dict with an
    "error" key if the start/end stop names couldn't be resolved at all.
    """
    candidates = []
    last_error = None

    for _, penalty in CANDIDATE_SETTINGS:
        result = find_route_by_name(graph, start_name, end_name, transfer_penalty_min=penalty)
        if isinstance(result, dict) and "error" in result:
            last_error = result["error"]
            continue
        candidates.append(result)

    if not candidates:
        return {"error": last_error or "No route could be found."}

    return _label_candidates(_dedupe(candidates))
