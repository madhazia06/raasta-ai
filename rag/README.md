# RAASTA AI — rag/ (Data + RAG pipeline)

## Setup (one-time)
```bash
pip install sentence-transformers faiss-cpu numpy
```

## Run order (important — each step depends on the previous one's output)
```bash
cd rag
python3 document_builder.py   # Step 2: CSVs -> plain-language text chunks
python3 embeddings.py         # Step 3: text chunks -> vectors (downloads a
                               #         small model the first time, needs
                               #         internet once, then works offline)
python3 vector_store.py       # Step 4: builds the searchable FAISS index
python3 test_retrieval.py     # Step 6: runs the test suite, prints pass/fail
```

After that, anyone (Member 3's chatbot, Member 4's UI) can just do:
```python
from retriever import retrieve

results = retrieve("bus from Bhatti Chowk to Thokar Niaz Baig", k=5)
for r in results:
    print(r["text"], r["score"])
```

## Files
| File | What it does |
|---|---|
| `document_builder.py` | Reads `../data/*.csv`, writes `rag_documents.json` (plain-language route descriptions) |
| `embeddings.py` | Reads `rag_documents.json`, writes `embeddings.npy` + `doc_ids.json` (the vectors) |
| `vector_store.py` | Reads the embeddings, builds/loads `faiss_index.bin` (the searchable index) |
| `retriever.py` | The main function everyone else calls: `retrieve(query, k=5)` |
| `test_retrieval.py` | Test suite with expected-route assertions; run `--interactive` to try your own queries |

## Generated files (not checked into git — regenerate locally)
`embeddings.npy`, `doc_ids.json`, and `faiss_index.bin` are binary/generated
files that depend on the embedding model. Add these to `.gitignore` and have
each teammate generate them locally by running the 3 build steps above —
don't commit them, they'll just cause merge conflicts and bloat the repo.

`rag_documents.json` IS checked in (it's small, human-readable, and useful
for teammates to inspect without running Python) — but if you change the
CSVs in `data/`, re-run `document_builder.py` and commit the updated version.

## A note on Urdu/Roman Urdu queries
The default model (`all-MiniLM-L6-v2`) is English-focused. If `test_retrieval.py`
shows failures specifically on Roman Urdu queries, open `embeddings.py` and
swap `MODEL_NAME` to `"sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"` —
it's a drop-in replacement, just re-run the 3 build steps afterward.
