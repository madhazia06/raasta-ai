"""
RAASTA AI - rag/vector_store.py
Member 1: Data + RAG

STEP 4 of the RAG pipeline.

Wraps a FAISS index around the embeddings from Step 3. FAISS is just a very
fast lookup structure for vectors -- think of it as a search engine index,
except it searches by "closeness in meaning" instead of matching keywords.

This module exposes two functions:
    build_index()   -> builds the FAISS index from embeddings.npy + doc_ids.json
                        and saves it to disk (run this once, or whenever the
                        data / embeddings change)
    load_index()    -> loads the saved index back into memory (call this at
                        app startup, it's much faster than rebuilding)

The index only stores vectors + doc_ids (position -> which document). The
actual document text/metadata stays in rag_documents.json -- retriever.py
(Step 5) is what joins the two back together.
"""
import json
import os
import numpy as np
import faiss

RAG_DIR = os.path.dirname(__file__)
EMBEDDINGS_PATH = os.path.join(RAG_DIR, "embeddings.npy")
DOC_IDS_PATH = os.path.join(RAG_DIR, "doc_ids.json")
INDEX_PATH = os.path.join(RAG_DIR, "faiss_index.bin")


def build_index():
    """Build a FAISS index from embeddings.npy and save it to disk."""
    vectors = np.load(EMBEDDINGS_PATH).astype("float32")
    dim = vectors.shape[1]

    # Vectors from embeddings.py are already normalized, so inner product
    # search (IndexFlatIP) is equivalent to cosine similarity -- higher
    # score = more similar. This is the standard choice for sentence
    # embeddings used for semantic search.
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    faiss.write_index(index, INDEX_PATH)
    print(f"Built FAISS index: {index.ntotal} vectors, dim={dim} -> {INDEX_PATH}")
    return index


def _ensure_artifacts():
    """Create embeddings/doc-id files and FAISS index on first use."""
    if not os.path.exists(EMBEDDINGS_PATH) or not os.path.exists(DOC_IDS_PATH):
        from .embeddings import build_embeddings
        build_embeddings()
    if not os.path.exists(INDEX_PATH):
        build_index()


def load_index():
    """Load the FAISS index, building local RAG artifacts on first use."""
    _ensure_artifacts()
    return faiss.read_index(INDEX_PATH)


def load_doc_ids():
    _ensure_artifacts()
    with open(DOC_IDS_PATH, encoding="utf-8") as f:
        return json.load(f)


def search(query_vector, k=5):
    """
    Search the index for the k most similar documents to query_vector.
    Returns a list of (doc_id, score) tuples, best match first.
    """
    index = load_index()
    doc_ids = load_doc_ids()

    query_vector = np.array(query_vector, dtype="float32").reshape(1, -1)
    scores, indices = index.search(query_vector, k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        results.append((doc_ids[idx], float(score)))
    return results


if __name__ == "__main__":
    build_index()
