"""
RAASTA AI - rag/embeddings.py
Member 1: Data + RAG

STEP 3 of the RAG pipeline.

Turns each text document (from document_builder.py) into a numeric vector
("embedding") using a free, offline sentence-embedding model. Two pieces of
text that mean similar things end up with similar vectors -- that's what
lets us search by *meaning* instead of exact keyword matching. This means
a query like "kaise Model Town jaana hai Kalma Chowk se" can still match a
route document written in plain English, because the model captures meaning
across phrasing (though for best multilingual results across Urdu/Roman
Urdu, see the NOTE at the bottom about swapping the model).

Model used: sentence-transformers/all-MiniLM-L6-v2
  - Free, runs fully offline (no API key, no internet needed after first
    download), ~80MB, fast on CPU. Good default for a hackathon.

Usage:
    python3 embeddings.py
    -> reads rag_documents.json (from document_builder.py)
    -> writes embeddings.npy (the vectors) and doc_ids.json (matching order)
"""
import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer

RAG_DIR = os.path.dirname(__file__)
DOCS_PATH = os.path.join(RAG_DIR, "rag_documents.json")
EMBEDDINGS_PATH = os.path.join(RAG_DIR, "embeddings.npy")
DOC_IDS_PATH = os.path.join(RAG_DIR, "doc_ids.json")

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model = None  # lazy-loaded singleton so repeated calls don't reload the model


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_text(text_or_texts):
    """
    Embed a single string or a list of strings.
    Returns a numpy array of shape (n, 384) for all-MiniLM-L6-v2.
    """
    model = get_model()
    is_single = isinstance(text_or_texts, str)
    texts = [text_or_texts] if is_single else text_or_texts
    vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return vectors[0] if is_single else vectors


def build_embeddings():
    with open(DOCS_PATH, encoding="utf-8") as f:
        docs = json.load(f)

    texts = [d["text"] for d in docs]
    doc_ids = [d["doc_id"] for d in docs]

    print(f"Embedding {len(texts)} documents with {MODEL_NAME} ...")
    vectors = embed_text(texts)

    np.save(EMBEDDINGS_PATH, vectors)
    with open(DOC_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(doc_ids, f)

    print(f"Saved embeddings -> {EMBEDDINGS_PATH}  shape={vectors.shape}")
    print(f"Saved doc_id order -> {DOC_IDS_PATH}")
    return vectors, doc_ids


if __name__ == "__main__":
    build_embeddings()

# ---------------------------------------------------------------------------
# NOTE for Member 3 (Generative AI + Voice) / future improvement:
# all-MiniLM-L6-v2 is English-only. If Urdu/Roman Urdu queries perform
# poorly in testing (Step 6), swap MODEL_NAME to a multilingual model, e.g.:
#   "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# It's a drop-in replacement -- no other code changes needed, just re-run
# this script to regenerate embeddings.npy with the new model.
# ---------------------------------------------------------------------------
