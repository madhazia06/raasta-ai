"""
RAASTA AI - rag/retriever.py
Member 1: Data + RAG

STEP 5 of the RAG pipeline. This is the function everyone else's code
(Member 3's LLM/chatbot, and Member 4's UI) will actually call.

    from rag.retriever import retrieve
    results = retrieve("bus from Bhatti Chowk to Thokar Niaz Baig")

Give it a question in plain English/Urdu/Roman Urdu, it returns the most
relevant routes with their full details -- not just an ID, but everything
Member 3's LLM needs to generate a proper answer (route name, stops, fare,
hours) without having to go query the CSVs itself.
"""
import json
import os
from embeddings import embed_text
from vector_store import search

RAG_DIR = os.path.dirname(__file__)
DOCS_PATH = os.path.join(RAG_DIR, "rag_documents.json")

_documents_by_id = None  # lazy-loaded cache


def _load_documents():
    global _documents_by_id
    if _documents_by_id is None:
        with open(DOCS_PATH, encoding="utf-8") as f:
            docs = json.load(f)
        _documents_by_id = {d["doc_id"]: d for d in docs}
    return _documents_by_id


def retrieve(query, k=5, bus_type_filter=None):
    """
    Retrieve the top-k most relevant documents for a natural-language query.

    Args:
        query: user's question, e.g. "Kalma Chowk se Model Town kaise jana hai"
        k: how many results to return
        bus_type_filter: optional, restrict to "Metro" / "Speedo" / "Electro"

    Returns:
        List of dicts, each with: doc_id, route_id, bus_type, doc_type,
        text, metadata, score (0-1, higher = more relevant).
    """
    documents = _load_documents()

    query_vector = embed_text(query)
    # Over-fetch a bit when filtering by bus_type, so we still return k
    # results after filtering instead of fewer.
    raw_k = k * 3 if bus_type_filter else k
    raw_results = search(query_vector, k=raw_k)

    results = []
    for doc_id, score in raw_results:
        doc = documents.get(doc_id)
        if doc is None:
            continue
        if bus_type_filter and doc["bus_type"] != bus_type_filter:
            continue
        results.append({**doc, "score": score})
        if len(results) >= k:
            break

    return results


def retrieve_route_only(query, k=3):
    """
    Convenience wrapper: same as retrieve(), but only returns actual route
    documents (excludes service_info / transfer_hub summary docs). This is
    what most user queries ("how do I get from X to Y") actually want.
    """
    documents = _load_documents()
    query_vector = embed_text(query)
    raw_results = search(query_vector, k=k * 4)  # over-fetch since we filter to routes only

    results = []
    for doc_id, score in raw_results:
        doc = documents.get(doc_id)
        if doc and doc["doc_type"] == "route":
            results.append({**doc, "score": score})
        if len(results) >= k:
            break
    return results


if __name__ == "__main__":
    # Quick manual smoke test -- see Step 6 (test_retrieval.py) for the
    # real test suite with expected-route assertions.
    test_queries = [
        "bus from Bhatti Chowk to Thokar Niaz Baig",
        "Kalma Chowk se Model Town kaise jana hai",
        "electric bus route in Lahore",
        "how much does the metro cost",
    ]
    for q in test_queries:
        print(f"\nQuery: {q}")
        for r in retrieve(q, k=3):
            print(f"  [{r['score']:.3f}] {r['doc_id']}: {r['text'][:100]}...")
