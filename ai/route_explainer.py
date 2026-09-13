"""Grounded AI explanation layer for RAASTA AI.

The transport graph remains the source of truth for routing. This module uses
local semantic RAG (SentenceTransformers + FAISS) to retrieve relevant verified
transport documents and then turns the already-verified route result into a
clear explanation. If the local model/index is not ready yet, the explanation
still falls back to the structured route facts instead of inventing anything.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Set

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAG_DIR = os.path.join(ROOT, "rag")
DOCS_PATH = os.path.join(RAG_DIR, "rag_documents.json")


def _used_route_ids(variant: dict) -> Set[str]:
    return {
        str(item.get("route_id"))
        for item in variant.get("path_stops", [])
        if item.get("route_id")
    }


def _exact_route_documents(route_ids: Set[str]) -> List[dict]:
    if not route_ids or not os.path.exists(DOCS_PATH):
        return []
    try:
        with open(DOCS_PATH, encoding="utf-8") as f:
            docs = json.load(f)
    except Exception:
        return []
    return [
        d for d in docs
        if d.get("doc_type") == "route" and str(d.get("route_id")) in route_ids
    ]


def _semantic_documents(query: str) -> List[dict]:
    """Use the project's local transformer/FAISS RAG when available."""
    try:
        from rag.retriever import retrieve_route_only
        return retrieve_route_only(query, k=6)
    except Exception:
        # First run can still work while the local model/index is being prepared,
        # or on a machine where the optional AI dependencies have not installed.
        return []


def explain_route(start: str, destination: str, variant: dict) -> Dict[str, object]:
    """Return a grounded, user-facing AI explanation and evidence metadata."""
    route_ids = _used_route_ids(variant)
    query = (
        f"Public transport from {start} to {destination}. "
        f"Preferred route type: {variant.get('label', 'Fastest')}. "
        f"Services used: {', '.join(leg.get('bus', '') for leg in variant.get('legs', []))}."
    )

    semantic = _semantic_documents(query)
    exact = _exact_route_documents(route_ids)

    # Favor documents that actually describe services used by the verified route.
    semantic_used = [d for d in semantic if str(d.get("route_id")) in route_ids]
    evidence_docs = semantic_used or exact or semantic[:2]

    label = variant.get("label", "Recommended")
    transfers = int(variant.get("changes", 0))
    walk = int(round(variant.get("walk", 0)))
    duration = int(round(variant.get("time", 0)))
    fare = int(round(variant.get("fare", 0)))
    legs = variant.get("legs", [])

    reason_by_label = {
        "Fastest": "it has the lowest estimated journey time among the route candidates checked",
        "Cheapest": "it has the lowest estimated fare among the route candidates checked",
        "Fewest Bus Changes": "it minimizes bus changes before considering travel time",
        "Least Walking": "it minimizes the estimated walking portion of the journey",
    }
    reason = reason_by_label.get(label, "it is the strongest match for your selected priority")

    if transfers == 0:
        transfer_text = "You can stay on one service without changing buses."
    elif transfers == 1:
        transfer_text = "The journey needs one bus change."
    else:
        transfer_text = f"The journey needs {transfers} bus changes."

    if legs:
        sequence = " → ".join(leg.get("bus", "") for leg in legs)
        service_text = f"The verified service sequence is {sequence}."
    else:
        service_text = "The service sequence comes directly from the verified transport graph."

    explanation = (
        f"RAASTA AI recommends this option because {reason}. "
        f"{service_text} {transfer_text} "
        f"The current estimate is about {duration} minutes, including roughly {walk} minutes of walking, "
        f"with an estimated fare of Rs. {fare}. "
        "The bus services, boarding points and drop-off points come from the structured transport dataset; "
        "the AI layer only retrieves relevant verified context and explains the computed route."
    )

    sources = []
    for doc in evidence_docs[:3]:
        meta = doc.get("metadata", {})
        sources.append({
            "route_id": doc.get("route_id"),
            "route_no": meta.get("route_no"),
            "start_stop": meta.get("start_stop"),
            "end_stop": meta.get("end_stop"),
            "score": doc.get("score"),
        })

    return {
        "text": explanation,
        "rag_active": bool(semantic),
        "sources": sources,
    }
