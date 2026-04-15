import os
import chromadb


class VectorStore:
    """
    Wraps ChromaDB for storing and querying document embeddings.

    Member variables:
        db_path (str): Path to the persistent vector database.
        collection_name (str): Name of the ChromaDB collection.
        client (chromadb.PersistentClient): ChromaDB client instance.
        embedding_fn (ApiEmbeddingFunction): Embedding function wrapping the Embedder.
        collection (chromadb.Collection): The active collection.

    Member functions:
        add_documents(docs, ids, metadatas): Add documents to the vector store.
        query(query_text, top_k) -> list[dict]: Query for similar documents.
        count() -> int: Return the number of documents in the collection.
        reset(): Delete and recreate the collection.
    """

    def __init__(self, embedder, db_path=None, collection_name="cisb_knowledge"):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "vector_db")

        self.db_path = db_path
        self.collection_name = collection_name
        self.embedder = embedder

        self.client = chromadb.PersistentClient(path=self.db_path)
        # Do not bind collection-level embedding_function, because persisted
        # collection configs can conflict across runs/providers.
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
        except Exception:
            self.collection = self.client.create_collection(name=self.collection_name)

    def add_documents(self, docs, ids, metadatas=None):
        embeddings = self.embedder.embed(docs)
        kwargs = {"documents": docs, "ids": ids, "embeddings": embeddings}
        if metadatas is not None:
            kwargs["metadatas"] = metadatas
        self.collection.upsert(**kwargs)

    def query(self, query_text, top_k=3):
        query_embedding = self.embedder.embed([query_text])[0]
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.collection.count()),
        )

        output = []
        if results and results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                entry = {
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i]
                    if results["documents"]
                    else None,
                    "metadata": results["metadatas"][0][i]
                    if results["metadatas"]
                    else None,
                    "distance": results["distances"][0][i]
                    if results["distances"]
                    else None,
                }
                output.append(entry)

        return output

    def count(self):
        return self.collection.count()

    def reset(self):
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(name=self.collection_name)


if __name__ == "__main__":
    from embedder import Embedder

    API_KEY = ""
    BASE_URL = ""
    MODEL_NAME = ""

    embedder = Embedder(api_key=API_KEY, base_url=BASE_URL, model_name=MODEL_NAME)
    store = VectorStore(embedder=embedder)
    store.reset()

    store.add_documents(
        docs=[
            "CISB stands for Compiler-Introduced Security Bugs.",
            "Undefined Behavior is when the standard imposes no requirements.",
        ],
        ids=["test_1", "test_2"],
        metadatas=[{"source": "test"}, {"source": "test"}],
    )

    print(f"Document count: {store.count()}")

    results = store.query("What is CISB?", top_k=2)
    for r in results:
        print(f"  [{r['id']}] (distance: {r['distance']:.4f})")
        print(f"    {r['document'][:80]}")
        print()
