import os

from openai import OpenAI
try:
    import dotenv
except ImportError:  # pragma: no cover - optional for __main__ usage.
    dotenv = None


class Embedder:
    """
    Calls an OpenAI-compatible embedding API to generate text embeddings.

    Member variables:
        model_name (str): Name of the embedding model.
        client (OpenAI): OpenAI-compatible API client.

    Member functions:
        embed(texts) -> list[list[float]]: Generate embeddings for a list of texts.
    """

    def __init__(self, api_key, base_url, model_name):
        self.model_name = model_name
        self.base_url = self._normalize_base_url(base_url)
        self.client = OpenAI(api_key=api_key, base_url=self.base_url)

    def _candidate_models(self):
        raw = (self.model_name or "").strip()
        if not raw:
            return []

        candidates = [raw]

        if "/" not in raw and raw.startswith("Qwen3-"):
            candidates.append(f"Qwen/{raw}")

        deduped = []
        for m in candidates:
            if m not in deduped:
                deduped.append(m)
        return deduped

    @staticmethod
    def _normalize_base_url(base_url):
        if not base_url:
            return base_url

        normalized = base_url.rstrip("/")
        for suffix in ("/embeddings", "/chat/completions", "/responses"):
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]
                break
        return normalized

    def embed(self, texts):
        last_err = None
        for model_name in self._candidate_models():
            try:
                response = self.client.embeddings.create(
                    input=texts,
                    model=model_name,
                )
                self.model_name = model_name
                return [item.embedding for item in response.data]
            except Exception as e:
                last_err = e
                err_text = str(e).lower()
                if "model does not exist" not in err_text and "invalid model" not in err_text:
                    raise

        if last_err:
            raise last_err
        raise ValueError("No valid embedding model candidate found.")


if __name__ == "__main__":
    if dotenv is not None:
        dotenv.load_dotenv()
    API_KEY = os.getenv("RAG_API_KEY")
    BASE_URL = os.getenv("EMBEDDING_API_URL")
    MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")

    embedder = Embedder(api_key=API_KEY, base_url=BASE_URL, model_name=MODEL_NAME)
    test_texts = [
        "What is CISB?",
        "Compiler-Introduced Security Bugs are vulnerabilities from optimizations.",
        "Undefined behavior in C language standard.",
    ]
    results = embedder.embed(test_texts)
    for text, vec in zip(test_texts, results):
        print(f"Text: {text[:50]}...")
        print(f"  Dimension: {len(vec)}")
        print(f"  First 5 values: {vec[:5]}")
        print()
