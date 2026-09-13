"""
route_engine.py (UPDATED for the real RAASTA AI dataset)
-----------------------------------------------------------
Finds the best public-transport route between two points.

WHAT CHANGED FROM THE ORIGINAL VERSION:
1. Added find_route_by_name() -- a new entry point that takes stop NAMES
   (e.g. "Kalma Chowk", "Model Town") instead of raw GPS coordinates. This
   is what Member 3's chatbot / RAG layer should actually call, since a
   user's question gives you place names, not coordinates. The original
   find_route(lat, lon, ...) still exists and works exactly as before, for
   cases where you do have raw coordinates (e.g. live GPS location).
2. RouteResult now also tracks total_fare_pkr -- the estimated total cost
   of the trip (sum of one fare per bus boarded), needed for the new
   "Cheapest" ranking option in ranking.py.
3. Added a tie-breaking counter to the Dijkstra priority queue. Without
   it, on an exact cost tie between the very first state (which has no
   "last route" yet) and a later state, heapq would try to compare None
   to a route_id string and crash with a TypeError. This is a rare edge
   case but a real one worth closing off.

Everything else (the core Dijkstra + transfer penalty logic) is UNCHANGED.
"""

import heapq
import itertools

# Assumed average walking speed, used to convert distance -> minutes.
WALKING_SPEED_KMH = 4.5


def walking_minutes(distance_km):
    return round((distance_km / WALKING_SPEED_KMH) * 60, 1)


class RouteResult:
    """
    Structured output for one complete journey (start -> end).
    This is the schema Members 3 and 4 should build against.
    """
    def __init__(self):
        self.total_time_min = 0.0
        self.total_walking_min = 0.0
        self.total_fare_pkr = 0.0
        self.transfers = 0
        self.steps = []  # list of dicts, each a human-readable step
        self.path_stops = []  # stop coordinates used by the bus portion of the trip
        self.start_stop = None
        self.end_stop = None

    def to_dict(self):
        return {
            "total_time_min": round(self.total_time_min, 1),
            "total_walking_min": round(self.total_walking_min, 1),
            "total_fare_pkr": round(self.total_fare_pkr, 1),
            "transfers": self.transfers,
            "steps": self.steps,
            "path_stops": self.path_stops,
            "start_stop": self.start_stop,
            "end_stop": self.end_stop,
        }


def _dijkstra_with_transfer_penalty(graph, start_stop_id, end_stop_id, transfer_penalty_min):
    """
    Core shortest-path search.

    State = (current_stop_id, route_id_used_to_arrive_here)
    We track the route used to arrive at a stop because switching routes
    costs extra time (the transfer penalty). Two different states can
    represent "being at the same stop" but with different future costs.

    Returns: (total_cost_min, path) where path is a list of
             (stop_id, route_id_taken_to_reach_it) tuples, or (None, None)
             if no route exists.
    """
    # A tie-breaking counter avoids ever comparing `last_route` or `path`
    # values directly when two entries have the exact same cost -- without
    # it, heapq falls through to comparing the next tuple element, which
    # can be None (for the very first state) vs. a route_id string, and
    # Python raises a TypeError trying to compare those.
    counter = itertools.count()

    # priority queue entries: (cost_so_far, tiebreaker, stop_id, last_route_id, path_so_far)
    start_state = (0.0, next(counter), start_stop_id, None, [(start_stop_id, None)])
    pq = [start_state]
    best_cost = {}  # (stop_id, last_route_id) -> lowest cost seen

    while pq:
        cost, _, stop_id, last_route, path = heapq.heappop(pq)

        if stop_id == end_stop_id:
            return cost, path

        state_key = (stop_id, last_route)
        if state_key in best_cost and best_cost[state_key] <= cost:
            continue
        best_cost[state_key] = cost

        for edge in graph.adjacency.get(stop_id, []):
            extra = 0.0
            if last_route is not None and edge.route_id != last_route:
                extra = transfer_penalty_min  # switching buses costs time
            new_cost = cost + edge.travel_time_min + extra
            new_path = path + [(edge.to_stop_id, edge.route_id)]
            heapq.heappush(pq, (new_cost, next(counter), edge.to_stop_id, edge.route_id, new_path))

    return None, None


def _build_result(graph, path, walk_to_start, walk_from_end):
    """Shared logic: turns a raw Dijkstra path into a RouteResult with
    plain-language steps, timing, transfer count, and fare total."""
    result = RouteResult()
    result.total_walking_min = walk_to_start + walk_from_end

    start_stop = graph.stops[path[0][0]]
    end_stop = graph.stops[path[-1][0]]
    result.start_stop = {"id": start_stop.stop_id, "name": start_stop.name, "lat": start_stop.lat, "lon": start_stop.lon}
    result.end_stop = {"id": end_stop.stop_id, "name": end_stop.name, "lat": end_stop.lat, "lon": end_stop.lon}
    result.path_stops = [
        {"id": sid, "name": graph.stops[sid].name, "lat": graph.stops[sid].lat, "lon": graph.stops[sid].lon, "route_id": rid}
        for sid, rid in path
        if graph.stops[sid].lat is not None and graph.stops[sid].lon is not None
    ]
    result.steps.append({
        "type": "walk",
        "instruction": f"Walk to {start_stop.name} (~{walk_to_start} min).",
    })

    current_route = None
    board_stop_name = None
    ride_time = 0.0
    prev_stop_id = path[0][0]

    for stop_id, route_id in path[1:]:
        edge = next(e for e in graph.adjacency[prev_stop_id] if e.to_stop_id == stop_id and e.route_id == route_id)

        if route_id != current_route:
            if current_route is not None:
                result.steps.append({
                    "type": "ride",
                    "instruction": (
                        f"Get off at {graph.stops[prev_stop_id].name} "
                        f"(~{round(ride_time,1)} min on this bus)."
                    ),
                })
                result.transfers += 1
            board_stop_name = graph.stops[prev_stop_id].name
            result.steps.append({
                "type": "board",
                "instruction": f"Board {edge.route_name} at {board_stop_name}.",
            })
            result.total_fare_pkr += edge.fare_pkr  # one fare charged per boarding
            current_route = route_id
            ride_time = 0.0

        ride_time += edge.travel_time_min
        result.total_time_min += edge.travel_time_min
        prev_stop_id = stop_id

    result.steps.append({
        "type": "ride",
        "instruction": f"Get off at {graph.stops[prev_stop_id].name} (~{round(ride_time,1)} min on this bus).",
    })

    result.steps.append({
        "type": "walk",
        "instruction": f"Walk to your destination (~{walk_from_end} min).",
    })

    result.total_time_min += result.total_walking_min
    return result


def find_route(graph, start_lat, start_lon, end_lat, end_lon, transfer_penalty_min=10, start_stop_id=None, end_stop_id=None):
    """Find the best route between two coordinates using nearby *usable* stops.

    The old prototype always picked the geometrically closest stop first. That
    could fail when the closest stop was disconnected from the destination even
    though another stop a few hundred metres away had a valid service. We now
    test several nearby stops on both ends and choose the best reachable
    combination using bus time + transfer penalty + walking time.
    """
    # If the location resolver identified an exact dataset stop, preserve that
    # exact stop rather than re-selecting by coordinates. This matters when
    # multiple named stops share the same/similar coordinates (e.g. Shahdara).
    if start_stop_id and start_stop_id in graph.stops:
        start_candidates = [(0.0, graph.stops[start_stop_id])]
    else:
        start_candidates = graph.nearest_stops(start_lat, start_lon, top_n=5)

    if end_stop_id and end_stop_id in graph.stops:
        end_candidates = [(0.0, graph.stops[end_stop_id])]
    else:
        end_candidates = graph.nearest_stops(end_lat, end_lon, top_n=5)

    if not start_candidates or not end_candidates:
        return None

    best = None
    for start_dist_km, start_stop in start_candidates:
        for end_dist_km, end_stop in end_candidates:
            if start_stop.stop_id == end_stop.stop_id:
                continue
            cost, path = _dijkstra_with_transfer_penalty(
                graph, start_stop.stop_id, end_stop.stop_id, transfer_penalty_min
            )
            if path is None:
                continue
            walk_to_start = walking_minutes(start_dist_km)
            walk_from_end = walking_minutes(end_dist_km)
            score = cost + walk_to_start + walk_from_end
            if best is None or score < best[0]:
                best = (score, path, walk_to_start, walk_from_end)

    if best is None:
        return None

    _, path, walk_to_start, walk_from_end = best
    return _build_result(graph, path, walk_to_start, walk_from_end)


def find_route_by_name(graph, start_name, end_name, transfer_penalty_min=10):
    """
    Entry point for when you have stop NAMES instead of coordinates -- this
    is what a chatbot/RAG layer should call, since a user's question gives
    you place names (e.g. "Kalma Chowk", "Model Town"), not GPS points.

    Returns a RouteResult, or a dict with an "error" key explaining what
    went wrong (unknown start stop, unknown end stop, or no route exists)
    so the caller can show a helpful message instead of just None.
    """
    start_stop = graph.find_stop_by_name(start_name)
    end_stop = graph.find_stop_by_name(end_name)

    if start_stop is None:
        return {"error": f"Could not find a stop matching '{start_name}'."}
    if end_stop is None:
        return {"error": f"Could not find a stop matching '{end_name}'."}
    if start_stop.stop_id == end_stop.stop_id:
        return {"error": "Start and destination appear to be the same stop."}

    cost, path = _dijkstra_with_transfer_penalty(
        graph, start_stop.stop_id, end_stop.stop_id, transfer_penalty_min
    )
    if path is None:
        return {"error": f"No route found between {start_stop.name} and {end_stop.name}."}

    # No walking needed to reach the start/end stop -- the user named the
    # stop directly, they're not starting from an arbitrary GPS point.
    return _build_result(graph, path, walk_to_start=0.0, walk_from_end=0.0)
