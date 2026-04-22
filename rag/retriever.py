import os
try:
    from .vector_store import VectorStore
    from .reranker import Reranker
except ImportError:
    from vector_store import VectorStore
    from reranker import Reranker
try:
    import dotenv
except ImportError:  # pragma: no cover - optional for __main__ usage.
    dotenv = None


class Retriever:
    """
    RAG retrieval logic: loads knowledge base documents, indexes them
    in a vector store, and retrieves relevant context for queries.

    Member variables:
        vector_store (VectorStore): The underlying vector store.
        knowledge_base_path (str): Path to the knowledge base directory.
    """

    def __init__(self, embedder, reranker=None, knowledge_base_path=None, db_path=None):
        if knowledge_base_path is None:
            knowledge_base_path = os.path.join(
                os.path.dirname(__file__), "knowledge_base"
            )
        self.knowledge_base_path = knowledge_base_path
        self.vector_store = VectorStore(embedder=embedder, db_path=db_path)
        self.reranker = reranker

    def _split_by_sections(self, text, source_file):
        sections = []
        current_header = source_file
        current_lines = []

        for line in text.split("\n"):
            if line.startswith("## "):
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    if content:
                        sections.append(
                            {
                                "content": content,
                                "header": current_header,
                                "source": source_file,
                            }
                        )
                current_header = line.lstrip("# ").strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                sections.append(
                    {
                        "content": content,
                        "header": current_header,
                        "source": source_file,
                    }
                )

        return sections

    def ingest_knowledge_base(self):
        self.vector_store.reset()

        all_docs = []
        all_ids = []
        all_metadatas = []

        for filename in sorted(os.listdir(self.knowledge_base_path)):
            if not filename.endswith(".md"):
                continue

            filepath = os.path.join(self.knowledge_base_path, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()

            sections = self._split_by_sections(text, filename)
            for i, section in enumerate(sections):
                all_docs.append(section["content"])
                all_ids.append(f"{filename}_{i}")
                all_metadatas.append(
                    {
                        "source": section["source"],
                        "header": section["header"],
                    }
                )

        if all_docs:
            self.vector_store.add_documents(
                docs=all_docs,
                ids=all_ids,
                metadatas=all_metadatas,
            )

        return len(all_docs)

    def retrieve(self, query, top_k=3, candidate_k=None, use_rerank=True):
        """
        Retrieve relevant document sections for a query.

        Returns list of dicts with: content, source, header, distance.
        """
        if candidate_k is None:
            candidate_k = top_k * 4 if self.reranker and use_rerank else top_k

        results = self.vector_store.query(query, top_k=candidate_k)

        if self.reranker and use_rerank and results:
            docs = [r["document"] for r in results]
            try:
                reranked = self.reranker.rerank(
                    query,
                    docs,
                    top_n=min(top_k, len(docs)),
                )

                ordered = []
                for item in reranked:
                    idx = item.get("index")
                    if idx is None:
                        continue
                    if 0 <= idx < len(results):
                        entry = dict(results[idx])
                        entry["rerank_score"] = item.get("relevance_score")
                        ordered.append(entry)
                if ordered:
                    results = ordered
            except Exception as e:
                print(f"Warning: rerank failed, fallback to vector order. Error: {e}")

        results = results[:top_k]

        return [
            {
                "content": r["document"],
                "source": r["metadata"]["source"] if r["metadata"] else None,
                "header": r["metadata"]["header"] if r["metadata"] else None,
                "distance": r["distance"],
                "rerank_score": r.get("rerank_score"),
            }
            for r in results
        ]

    def retrieve_as_context(self, query, top_k=5):
        """
        Retrieve relevant context formatted for prompt injection.

        Returns a single string with retrieved sections separated by
        dividers, suitable for inserting into an LLM system prompt.
        """
        results = self.retrieve(query, top_k=top_k)

        if not results:
            return ""

        context_parts = []
        for r in results:
            source_info = f"[Source: {r['source']} > {r['header']}]"
            context_parts.append(f"{source_info}\n{r['content']}")

        return "\n\n---\n\n".join(context_parts)


if __name__ == "__main__":
    try:
        from .embedder import Embedder
    except ImportError:
        from embedder import Embedder

    if dotenv is not None:
        dotenv.load_dotenv()
    API_KEY = os.getenv("RAG_API_KEY")
    BASE_URL = os.getenv("EMBEDDING_API_URL")
    MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")

    RERANK_API_KEY = os.getenv("RAG_API_KEY")
    RERANK_BASE_URL = os.getenv("RERANK_API_URL") or os.getenv("RERANKING_API_URL")
    RERANK_MODEL_NAME = os.getenv("RERANK_MODEL_NAME") or os.getenv("RERANKING_MODEL_NAME")

    embedder = Embedder(api_key=API_KEY, base_url=BASE_URL, model_name=MODEL_NAME)
    reranker = None
    if RERANK_API_KEY and RERANK_BASE_URL and RERANK_MODEL_NAME:
        reranker = Reranker(
            api_key=RERANK_API_KEY,
            base_url=RERANK_BASE_URL,
            model_name=RERANK_MODEL_NAME,
        )

    retriever = Retriever(embedder=embedder, reranker=reranker)

    print("Ingesting knowledge base...")
    num_docs = retriever.ingest_knowledge_base()
    print(f"Indexed {num_docs} document sections.\n")

    query = "What is the definition of CISB?"
    print(f"Query: {query}")
    results = retriever.retrieve(query, top_k=2)
    for r in results:
        score_text = (
            f"rerank: {r['rerank_score']:.4f}" if r["rerank_score"] is not None else "rerank: N/A"
        )
        print(
            f"  [{r['source']} > {r['header']}] (distance: {r['distance']:.4f}, {score_text})"
        )
        print(f"    {r['content'][:120]}...")
        print()
