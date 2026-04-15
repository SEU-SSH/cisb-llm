"""
RAG PoC test script.
Demonstrates: knowledge base ingestion -> query -> context retrieval.
"""

import sys
import os
import dotenv

sys.path.insert(0, os.path.dirname(__file__))

from embedder import Embedder
from retriever import Retriever
from reranker import Reranker

dotenv.load_dotenv()

API_KEY = os.getenv("RAG_API_KEY", "")
BASE_URL = os.getenv("EMBEDDING_API_URL", "")
MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "")
RERANK_API_KEY = os.getenv("RAG_API_KEY", "")
RERANK_BASE_URL = os.getenv("RERANK_API_URL") or os.getenv("RERANKING_API_URL", "")
RERANK_MODEL_NAME = os.getenv("RERANK_MODEL_NAME") or os.getenv("RERANKING_MODEL_NAME", "")


def run_test_query(retriever, query, top_k=3):
    print(f"\n{'=' * 60}")
    print(f"Query: {query}")
    print(f"{'=' * 60}")

    results = retriever.retrieve(query, top_k=top_k)

    if not results:
        print("  No results found.")
        return False

    for i, r in enumerate(results):
        score_text = (
            f"rerank: {r['rerank_score']:.4f}" if r["rerank_score"] is not None else "rerank: N/A"
        )
        print(f"\n  Result {i + 1} (distance: {r['distance']:.4f}, {score_text}):")
        print(f"  Source: {r['source']} > {r['header']}")
        print(f"  Content preview:")
        preview = r["content"][:200].replace("\n", "\n    ")
        print(f"    {preview}...")

    return True


def test_context_augmentation(retriever, query):
    print(f"\n{'=' * 60}")
    print(f"Context Augmentation Demo")
    print(f"Query: {query}")
    print(f"{'=' * 60}")

    context = retriever.retrieve_as_context(query, top_k=2)

    prompt_template = (
        "You are an expert in software security.\n\n"
        "[Reference Knowledge]\n{context}\n\n"
        "[Task]\nUsing the reference knowledge above, answer: {query}"
    )
    augmented_prompt = prompt_template.format(context=context, query=query)

    print(f"\nAugmented prompt ({len(augmented_prompt)} chars):")
    print("-" * 40)
    if len(augmented_prompt) > 500:
        print(augmented_prompt[:500])
        print(f"... ({len(augmented_prompt) - 500} more chars)")
    else:
        print(augmented_prompt)
    print("-" * 40)

    return True


def main():
    print("=" * 60)
    print("CISB RAG PoC - Test Script")
    print("=" * 60)

    embedder = Embedder(api_key=API_KEY, base_url=BASE_URL, model_name=MODEL_NAME)
    reranker = None
    if RERANK_API_KEY and RERANK_BASE_URL and RERANK_MODEL_NAME:
        reranker = Reranker(
            api_key=RERANK_API_KEY,
            base_url=RERANK_BASE_URL,
            model_name=RERANK_MODEL_NAME,
        )

    retriever = Retriever(embedder=embedder, reranker=reranker)

    print("\n[Step 1] Ingesting knowledge base documents...")
    num_docs = retriever.ingest_knowledge_base()
    print(f"  Indexed {num_docs} document sections.")
    print(f"  Vector store count: {retriever.vector_store.count()}")

    if num_docs == 0:
        print("ERROR: No documents were indexed. Check knowledge_base/ directory.")
        sys.exit(1)

    print("\n[Step 2] Running test queries...")

    test_queries = [
        "What is the definition of CISB?",
        "Explain Implicit Specification",
        "What is the difference between Undefined Behavior and Programming Error?",
        "How does Dead Store Elimination cause security bugs?",
        "What are orthogonal security properties?",
    ]

    all_passed = True
    for query in test_queries:
        result = run_test_query(retriever, query, top_k=3)
        if not result:
            all_passed = False

    print("\n[Step 3] Context augmentation demo...")
    test_context_augmentation(
        retriever, "Is signed integer overflow a programming error or a CISB?"
    )

    print(f"\n{'=' * 60}")
    print("Test Summary")
    print(f"{'=' * 60}")
    print(f"  Documents indexed: {num_docs}")
    print(f"  Queries executed: {len(test_queries)}")
    print(f"  All queries returned results: {all_passed}")
    print(f"  Status: {'PASS' if all_passed else 'FAIL'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
