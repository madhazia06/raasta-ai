# RAASTA AI — Bas Batao Kahan Jana Hai

RAASTA AI is a Lahore public-transport assistant that combines a verified local transport dataset, graph-based routing, key-free place lookup, and a local semantic RAG layer to present clear journey instructions.

## Final product flow

1. Enter any Lahore starting place and destination.
2. Known transit stops are matched directly from the dataset.
3. Other places are geocoded with OpenStreetMap Nominatim (no API key).
4. RAASTA AI searches several nearby stops and selects the nearest **usable** stop combination with a valid transit route.
5. The route engine computes the journey from the structured bus data.
6. The local AI/RAG layer retrieves relevant verified transport documents and explains the computed route in plain language.
7. The map shows only the entered start and destination pins.

## AI architecture

RAASTA AI does **not** let AI invent bus routes. The routing engine and CSV dataset determine buses, stops, transfers, fare estimates and journey estimates. AI is used as a grounded explanation/retrieval layer:

- `sentence-transformers/all-MiniLM-L6-v2` creates semantic embeddings.
- FAISS retrieves relevant verified route documents.
- `ai/route_explainer.py` combines retrieved context with the computed route to explain why the route was recommended.
- RAG artifacts are created automatically on first use if they do not exist.

No Groq/OpenAI/Google API key is required.

## Voice

Voice guidance was intentionally removed from this final build because it was unstable and is not part of the agreed final scope.

## Run

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

The first AI explanation can take longer because the SentenceTransformer model may need to download once. Later runs reuse the local model/cache and FAISS index.

## Main folders

- `data/` — Lahore routes, stops, fares, transfers and service data
- `routing/` — graph, Dijkstra routing and route ranking
- `maps/` — key-free location lookup / walking estimate helpers
- `rag/` — semantic documents, embeddings and FAISS retrieval
- `ai/` — grounded AI route explanation layer

## Important limitations

- Bus travel times are estimates because the dataset has route distance but not live per-segment timings.
- Walking distance/time is an estimate; the map intentionally does not draw a walking path.
- Fare values are estimates derived from fare ranges and are primarily useful for comparing route options.
- OpenStreetMap place lookup requires an internet connection but no key or card details.

## Final UI decisions

- Header branding is **RAASTA AI**.
- The header contains only the project brand and light/dark theme toggle.
- “How it works”, “About”, and the English/Urdu switcher were removed.
- The map and AI explanation no longer show technical captions underneath them.
- Voice is intentionally excluded.

## Stop-name disambiguation

The latest routing graph prefers the most likely major transit stop when a short name matches multiple stops. For example, `Shahdara` resolves to `Shahdara Metro Bus Station`. Once an exact dataset stop is resolved, the app preserves that stop through route calculation rather than selecting a different nearby stop from coordinates.
