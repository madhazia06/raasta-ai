"""
RAASTA AI - rag/test_retrieval.py
Member 1: Data + RAG

STEP 6 of the RAG pipeline: retrieval testing.

Run this AFTER you've run document_builder.py, embeddings.py, and
vector_store.py once (in that order) to generate rag_documents.json,
embeddings.npy, doc_ids.json, and faiss_index.bin.

    python3 document_builder.py
    python3 embeddings.py
    python3 vector_store.py
    python3 test_retrieval.py

This isn't just a smoke test -- each test case has an EXPECTED route_id, so
you get a pass/fail count instead of just eyeballing output. This is what
you show your team (and judges) as proof the retrieval actually works
before Member 3 builds the chatbot on top of it.
"""
from retriever import retrieve, retrieve_route_only

# Each test: (query, expected_route_id_substring, description)
# expected_route_id_substring just needs to appear in ONE of the top-k
# results' route_id -- we're testing "is the right route findable", not
# demanding it's always rank #1.
TEST_CASES = [
    ("bus from Bhatti Chowk to Thokar Niaz Baig", ["S-21", "S-22"],
     "Cross-city trip, should surface Speedo routes ending at Thokar Niaz Baig"),

    ("Kalma Chowk se Model Town kaise jana hai", ["S-13", "M-MAIN"],
     "Roman Urdu query, should find Metro or Speedo route covering both stops"),

    ("electric bus route in Lahore", ["E-1"],
     "Should surface the Electro main line"),

    ("how much does the metro cost", ["M-MAIN"],
     "Fare question should surface Metro's route doc (has fare info embedded)"),

    ("route from Railway Station to Green Town", ["E-1"],
     "Exact route match by endpoints -- Electro's defining trip"),

    ("bus from Gulberg to Kalma Chowk", ["S-11"],
     "Should find Speedo Route 11 (passes through Main Market Gulberg + Kalma Chowk)"),

    ("Shahdara to Gajju Matta", ["M-MAIN"],
     "Metro's exact endpoints"),

    ("mini bus Lahore", ["S-5", "S-6", "S-9", "S-15", "S-16", "S-18", "S-19", "S-20",
                          "S-23", "S-27", "S-28", "S-31", "S-32", "S-33", "S-34"],
     "Vehicle-class query, should surface at least one Mini Bus Speedo route"),
]


def run_tests():
    passed = 0
    failed = 0

    print("=" * 70)
    print("RAASTA AI -- Retrieval Test Suite")
    print("=" * 70)

    for query, expected_ids, description in TEST_CASES:
        results = retrieve_route_only(query, k=5)
        result_route_ids = [r["route_id"] for r in results]

        found = any(exp in result_route_ids for exp in expected_ids)
        status = "PASS" if found else "FAIL"
        if found:
            passed += 1
        else:
            failed += 1

        print(f"\n[{status}] {description}")
        print(f"  Query: \"{query}\"")
        print(f"  Expected one of: {expected_ids}")
        print(f"  Got: {result_route_ids}")
        if results:
            print(f"  Top match: {results[0]['doc_id']} (score={results[0]['score']:.3f})")
            print(f"    -> {results[0]['text'][:120]}...")

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed, out of {len(TEST_CASES)} tests")
    print("=" * 70)

    if failed > 0:
        print(
            "\nSome tests failed. This usually means either:\n"
            "  1. The route data changed (re-run document_builder.py + embeddings.py)\n"
            "  2. all-MiniLM-L6-v2 doesn't handle Roman Urdu / Urdu well enough --\n"
            "     see the NOTE at the bottom of embeddings.py about swapping to a\n"
            "     multilingual model\n"
            "  3. The test's expected route_id needs updating (data changed)\n"
        )

    return passed, failed


def interactive_mode():
    """Optional: run this file with an argument to test your own queries."""
    print("\nInteractive mode -- type a query (or 'quit' to exit):")
    while True:
        q = input("> ").strip()
        if q.lower() in ("quit", "exit", ""):
            break
        results = retrieve(q, k=5)
        for r in results:
            print(f"  [{r['score']:.3f}] ({r['doc_type']}) {r['text'][:120]}...")


if __name__ == "__main__":
    import sys
    if "--interactive" in sys.argv:
        interactive_mode()
    else:
        run_tests()
