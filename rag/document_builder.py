"""
RAASTA AI - rag/document_builder.py
Member 1: Data + RAG

STEP 2 of the RAG pipeline.

Turns the structured CSVs (routes.csv, route_stops.csv, fares.csv,
operating_hours.csv, service_info.csv, transfers.csv) into plain-language
text "documents" -- one per route, plus a handful of summary documents for
fares/hours/service info. These text chunks are what actually get embedded
in Step 3 (embeddings.py). A vector database can only search text, not raw
spreadsheet rows, so this step is the bridge between your data and RAG.

Usage:
    python3 document_builder.py
    -> reads from ../data/*.csv
    -> writes rag_documents.json (list of {doc_id, route_id, bus_type, text, metadata})

Each document's `text` field is intentionally written the way a person would
actually describe the route out loud -- this matches how a user's query will
be phrased, which is what makes retrieval work well.
"""
import csv
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(os.path.dirname(__file__), "rag_documents.json")


def load_csv(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_route_stop_map(route_stops_rows):
    """route_id -> ordered list of stop names"""
    route_map = {}
    for row in sorted(route_stops_rows, key=lambda r: (r["route_id"], int(r["stop_sequence"]))):
        route_map.setdefault(row["route_id"], []).append(row["stop_name"])
    return route_map


def build_transfer_map(transfer_rows):
    """stop_name -> list of route_ids that pass through it (for cross-referencing in route docs)"""
    stop_to_routes = {}
    for row in transfer_rows:
        stop_to_routes[row["stop_name"]] = row["routes_available"].split("|")
    return stop_to_routes


def route_document(route, stops, fares_by_type, hours_by_type, transfer_lookup):
    """Build one natural-language paragraph describing a single route."""
    bus_type = route["bus_type"]
    route_label = f"{bus_type} Route {route['route_no']}" if bus_type != "Metro" else "the Lahore Metrobus"

    stops_str = ", ".join(stops[1:-1]) if len(stops) > 2 else ""
    if stops_str:
        via_clause = f" via {stops_str}"
    else:
        via_clause = ""

    sentence = (
        f"{route_label} runs from {stops[0]} to {stops[-1]}{via_clause}. "
        f"It is a {bus_type} bus"
    )
    if route.get("vehicle_class"):
        sentence += f" ({route['vehicle_class']})"
    if route.get("distance_km"):
        sentence += f", covering approximately {route['distance_km']} km"
    sentence += f" with {route['num_stops']} stops."

    # Fare info
    fare = fares_by_type.get(bus_type)
    if fare:
        if fare["min_fare_pkr"] == fare["max_fare_pkr"]:
            sentence += f" The fare is a flat Rs {fare['min_fare_pkr']}."
        else:
            sentence += f" The fare ranges from Rs {fare['min_fare_pkr']} to Rs {fare['max_fare_pkr']} depending on distance."

    # Hours info
    hours = hours_by_type.get(bus_type)
    if hours:
        sentence += f" Buses run from {hours['first_bus']} to {hours['last_bus']} daily."

    # Interchange info: does this route touch any known transfer stop?
    interchange_notes = []
    for s in stops:
        if s in transfer_lookup and len(transfer_lookup[s]) > 1:
            other_routes = [r for r in transfer_lookup[s] if r != route["route_id"]]
            if other_routes:
                interchange_notes.append(f"{s} (connects to {', '.join(other_routes[:4])})")
    if interchange_notes:
        sentence += f" You can change buses at: {'; '.join(interchange_notes[:3])}."

    if route.get("stop_data_status") == "partial":
        sentence += " Note: only the start and end points of this route are confirmed; the full stop sequence is not yet published."

    return sentence


def build_documents():
    routes = load_csv("routes.csv")
    route_stops = load_csv("route_stops.csv")
    fares = load_csv("fares.csv")
    hours = load_csv("operating_hours.csv")
    service_info = load_csv("service_info.csv")
    transfers = load_csv("transfers.csv")

    route_stop_map = build_route_stop_map(route_stops)
    transfer_lookup = build_transfer_map(transfers)
    fares_by_type = {f["bus_type"]: f for f in fares}
    hours_by_type = {h["bus_type"]: h for h in hours}

    documents = []

    # --- 1. One document per route ---
    for route in routes:
        stops = route_stop_map.get(route["route_id"], [route["start_stop"], route["end_stop"]])
        text = route_document(route, stops, fares_by_type, hours_by_type, transfer_lookup)
        documents.append({
            "doc_id": f"route_{route['route_id']}",
            "route_id": route["route_id"],
            "bus_type": route["bus_type"],
            "doc_type": "route",
            "text": text,
            "metadata": {
                "route_no": route["route_no"],
                "start_stop": route["start_stop"],
                "end_stop": route["end_stop"],
                "num_stops": route["num_stops"],
                "verification_status": route.get("verification_status", ""),
            },
        })

    # --- 2. Service overview documents (one per bus_type) ---
    for info in service_info:
        bt = info["bus_type"]
        fare = fares_by_type.get(bt, {})
        hr = hours_by_type.get(bt, {})
        text = (
            f"{info['official_name']} ({bt}) is operated by {info['operator']}. "
            f"{info['notes']} "
        )
        if fare:
            text += f"Fare: Rs {fare['min_fare_pkr']}"
            if fare["min_fare_pkr"] != fare["max_fare_pkr"]:
                text += f" to Rs {fare['max_fare_pkr']}"
            text += f" ({fare['fare_type']}). "
        if hr:
            text += f"Operating hours: {hr['first_bus']} to {hr['last_bus']}, {hr['days_of_operation']}."

        documents.append({
            "doc_id": f"service_{bt}",
            "route_id": None,
            "bus_type": bt,
            "doc_type": "service_info",
            "text": text,
            "metadata": {"operator": info["operator"], "launched": info["launched"]},
        })

    # --- 3. Interchange/transfer hub documents (only the biggest ones, to avoid noise) ---
    for t in transfers:
        if int(t["num_routes"]) >= 3:
            routes_list = t["routes_available"].split("|")
            text = (
                f"{t['stop_name']} is a major interchange stop in Lahore where you can "
                f"transfer between {t['num_routes']} routes: {', '.join(routes_list)}. "
            )
            if t["cross_system_transfer"] == "Yes":
                text += f"This allows switching between different bus systems ({t['bus_types'].replace('|', ' and ')})."
            documents.append({
                "doc_id": f"transfer_{t['transfer_id']}",
                "route_id": None,
                "bus_type": t["bus_types"],
                "doc_type": "transfer_hub",
                "text": text,
                "metadata": {"stop_name": t["stop_name"], "routes": routes_list},
            })

    return documents


if __name__ == "__main__":
    docs = build_documents()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(docs, f, indent=2, ensure_ascii=False)

    print(f"Built {len(docs)} documents -> {OUT_PATH}")
    by_type = {}
    for d in docs:
        by_type[d["doc_type"]] = by_type.get(d["doc_type"], 0) + 1
    print("Breakdown:", by_type)
    print("\n--- Sample documents ---")
    for d in docs[:2]:
        print(f"\n[{d['doc_id']}]")
        print(d["text"])
    # Show one interchange doc as a sample
    hub_docs = [d for d in docs if d["doc_type"] == "transfer_hub"]
    if hub_docs:
        print(f"\n[{hub_docs[0]['doc_id']}]")
        print(hub_docs[0]["text"])
