"""
demo.py (UPDATED for the real RAASTA AI dataset)
----------------------------------------------------
Run this with: python demo.py
Builds the graph from the REAL data/ folder (routes.csv, route_stops.csv,
stops.csv, fares.csv) and prints ranked route alternatives for a few
realistic name-based queries -- the way a chatbot would actually call this.
"""

import json
from graph import TransportGraph
from ranking import get_ranked_routes_by_name


def main():
    graph = TransportGraph().build(
        stops_csv_path="data/stops.csv",
        routes_csv_path="data/routes.csv",
        route_stops_csv_path="data/route_stops.csv",
        fares_csv_path="data/fares.csv",
    )
    print(f"Graph built: {len(graph.stops)} stops, "
          f"{sum(len(v) for v in graph.adjacency.values())} directed edges\n")

    test_trips = [
        ("Bhatti Chowk", "Thokar Niaz Baig"),
        ("Kalma Chowk", "Model Town"),
        ("Railway Station", "Green Town"),
    ]

    for start_name, end_name in test_trips:
        print("=" * 70)
        print(f"TRIP: {start_name} -> {end_name}")
        print("=" * 70)

        results = get_ranked_routes_by_name(graph, start_name, end_name)

        if isinstance(results, dict) and "error" in results:
            print(f"  ERROR: {results['error']}")
            continue
        if not results:
            print("  No suitable public transportation route was found for this journey.")
            continue

        for item in results:
            print(f"\n--- {item['label']} ---")
            print(json.dumps(item["route"], indent=2))
        print()


if __name__ == "__main__":
    main()
