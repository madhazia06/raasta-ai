"""
graph.py (FIXED for the real RAASTA AI dataset)
------------------------------------------------
Builds the transportation graph used by the route engine.

WHAT CHANGED FROM THE ORIGINAL VERSION:
1. Reads the REAL column names: stops.csv uses 'latitude'/'longitude'
   (not 'lat'/'lon'), and the stop sequence lives in route_stops.csv
   (not a merged 'routes.csv' with a 'sequence' column).
2. No per-hop travel time exists in the real data -- only each route's
   TOTAL distance_km and stop count. We estimate each hop's time by
   dividing the route's total distance evenly across its stops and
   applying an assumed average city-bus speed (see AVG_BUS_SPEED_KMH
   below). This is a reasonable approximation for a hackathon, not a
   real-time traffic model -- documented clearly so nobody mistakes it
   for precise data.
3. Edges are now BIDIRECTIONAL by default. The real route_stops.csv only
   lists one direction per route (e.g. "R.A. Bazar -> Chungi Amar Sidhu"),
   but real bus services run both ways -- a rider can travel the route in
   reverse just as easily. Without this, Dijkstra would wrongly report
   "no route found" for any trip needing the reverse direction.
4. Each Edge now also carries `bus_type` and `fare_pkr`, needed for the
   new "Cheapest" ranking option in ranking.py.
5. Added find_stop_by_name() for name-based lookup (e.g. "Kalma Chowk"),
   since a chatbot/RAG layer will extract stop NAMES from user queries,
   not GPS coordinates.

This keeps the exact same Stop / Edge / TransportGraph interface that
route_engine.py and ranking.py already expect -- only the loading logic
changed, so the rest of the pipeline needs no changes.
"""

import csv
import math
from collections import defaultdict

# Assumed average city-bus speed (accounts for stops, traffic, signals).
# Used only to ESTIMATE per-hop travel time from a route's total distance,
# since the real dataset doesn't have per-hop timing data.
AVG_BUS_SPEED_KMH = 18.0


class Stop:
    def __init__(self, stop_id, name, lat, lon):
        self.stop_id = stop_id
        self.name = name
        self.lat = float(lat) if lat not in (None, "") else None
        self.lon = float(lon) if lon not in (None, "") else None

    def __repr__(self):
        return f"Stop({self.stop_id}, {self.name})"


class Edge:
    """A direct bus segment from one stop to the next, on a specific route."""
    def __init__(self, to_stop_id, route_id, route_name, travel_time_min, bus_type, fare_pkr):
        self.to_stop_id = to_stop_id
        self.route_id = route_id
        self.route_name = route_name
        self.travel_time_min = float(travel_time_min)
        self.bus_type = bus_type
        self.fare_pkr = fare_pkr  # estimated flat/average fare for boarding this route


class TransportGraph:
    def __init__(self):
        self.stops = {}                      # stop_id -> Stop
        self.adjacency = defaultdict(list)   # stop_id -> list[Edge]
        self.name_index = {}                 # normalized stop name -> stop_id
        self.fares_by_bus_type = {}          # bus_type -> estimated flat fare (PKR)

    # ---------- Loading data ----------

    def load_stops(self, stops_csv_path):
        with open(stops_csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stop = Stop(row["stop_id"], row["stop_name"], row.get("latitude"), row.get("longitude"))
                self.stops[stop.stop_id] = stop
                self.name_index[self._normalize(stop.name)] = stop.stop_id

    def load_fares(self, fares_csv_path):
        """
        Real fares.csv gives a fare RANGE per bus_type (e.g. Speedo: Rs 20-80,
        distance-based) rather than an exact per-route figure. For ranking
        purposes we use the midpoint of the range as an estimated flat fare
        per boarding. This is an approximation, not an exact fare -- good
        enough to RANK routes by relative cost, not to quote an exact price.
        """
        with open(fares_csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                min_fare = float(row["min_fare_pkr"])
                max_fare = float(row["max_fare_pkr"])
                self.fares_by_bus_type[row["bus_type"]] = round((min_fare + max_fare) / 2, 1)

    def load_routes(self, routes_csv_path, route_stops_csv_path):
        """
        Reads routes.csv (for each route's bus_type + total distance_km)
        and route_stops.csv (for the actual stop sequence), then builds
        BIDIRECTIONAL edges between consecutive stops on each route.
        """
        route_meta = {}  # route_id -> {"route_name":, "bus_type":, "distance_km":, "num_stops":}
        with open(routes_csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                route_meta[row["route_id"]] = {
                    "route_name": row["route_name"],
                    "bus_type": row["bus_type"],
                    "distance_km": float(row["distance_km"]) if row.get("distance_km") else None,
                    "num_stops": int(row["num_stops"]) if row.get("num_stops") else None,
                }

        route_rows = defaultdict(list)
        with open(route_stops_csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                route_rows[row["route_id"]].append(row)

        for route_id, rows in route_rows.items():
            rows.sort(key=lambda r: int(r["stop_sequence"]))
            meta = route_meta.get(route_id, {})
            route_name = meta.get("route_name", route_id)
            bus_type = meta.get("bus_type", "Unknown")
            fare = self.fares_by_bus_type.get(bus_type, 0)

            # Estimate per-hop time: total route distance / number of hops,
            # converted to minutes at AVG_BUS_SPEED_KMH. Falls back to a
            # flat 3 minutes/hop if distance data is missing for this route.
            num_hops = max(len(rows) - 1, 1)
            if meta.get("distance_km"):
                per_hop_km = meta["distance_km"] / num_hops
                per_hop_min = round((per_hop_km / AVG_BUS_SPEED_KMH) * 60, 1)
            else:
                per_hop_min = 3.0

            for i in range(len(rows) - 1):
                current_stop = rows[i]["stop_id"]
                next_stop = rows[i + 1]["stop_id"]

                # Forward edge
                self.adjacency[current_stop].append(
                    Edge(next_stop, route_id, route_name, per_hop_min, bus_type, fare)
                )
                # Reverse edge -- real bus routes run both directions even
                # though the source data only lists one sequence order.
                self.adjacency[next_stop].append(
                    Edge(current_stop, route_id, route_name, per_hop_min, bus_type, fare)
                )

    def build(self, stops_csv_path, routes_csv_path, route_stops_csv_path, fares_csv_path=None):
        self.load_stops(stops_csv_path)
        if fares_csv_path:
            self.load_fares(fares_csv_path)
        self.load_routes(routes_csv_path, route_stops_csv_path)
        return self

    # ---------- Helpers ----------

    def haversine_km(self, lat1, lon1, lat2, lon2):
        """Straight-line distance between two GPS points, in kilometers."""
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return 2 * R * math.asin(math.sqrt(a))

    def nearest_stops(self, lat, lon, top_n=3):
        """
        Given a raw GPS point (e.g. user's typed location, geocoded),
        return the top_n closest stops with their walking distance in km.
        """
        distances = []
        for stop_id, stop in self.stops.items():
            if stop.lat is None or stop.lon is None:
                continue
            dist_km = self.haversine_km(lat, lon, stop.lat, stop.lon)
            distances.append((dist_km, stop))
        distances.sort(key=lambda x: x[0])
        return distances[:top_n]

    @staticmethod
    def _normalize(name):
        return " ".join(name.strip().lower().split())

    def find_stop_by_name(self, name):
        """
        Look up a stop by name (e.g. what a chatbot/RAG layer extracts from
        a user's question). Tries, in order:
          1. Exact match (case/whitespace-insensitive)
          2. Substring match (name is contained in a stop's name, or vice versa)
        Returns the matching Stop, or None if nothing reasonable was found.
        If multiple stops match a substring search, returns the shortest
        matching name (usually the more precise match).
        """
        key = self._normalize(name)

        if key in self.name_index:
            return self.stops[self.name_index[key]]

        candidates = []
        for stop_name_norm, stop_id in self.name_index.items():
            if key in stop_name_norm or stop_name_norm in key:
                candidates.append(self.stops[stop_id])

        if not candidates:
            return None
        return min(candidates, key=lambda s: len(s.name))
