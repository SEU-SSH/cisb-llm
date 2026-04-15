import requests


class Reranker:
    """
    Calls an OpenAI-compatible rerank API to reorder candidate documents.

    Expected endpoint: {base_url}/rerank
    Expected request payload keys: model, query, documents, top_n
    """

    def __init__(self, api_key, base_url, model_name, timeout=30):
        self.api_key = api_key
        self.base_url = self._normalize_base_url(base_url)
        self.model_name = model_name
        self.timeout = timeout

    def _candidate_models(self):
        raw = (self.model_name or "").strip()
        if not raw:
            return []

        variants = [raw]
        if "Reranking" in raw:
            variants.append(raw.replace("Reranking", "Reranker"))

        prefixed = []
        for v in variants:
            prefixed.append(v)
            if "/" not in v and v.startswith("Qwen3-"):
                prefixed.append(f"Qwen/{v}")

        deduped = []
        for m in prefixed:
            if m not in deduped:
                deduped.append(m)
        return deduped

    @staticmethod
    def _normalize_base_url(base_url):
        if not base_url:
            return base_url

        normalized = base_url.rstrip("/")
        for suffix in ("/rerank", "/v1/rerank"):
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]
                break
        return normalized

    def rerank(self, query, documents, top_n=None):
        if not documents:
            return []

        if top_n is None:
            top_n = len(documents)

        url = f"{self.base_url}/rerank"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        data = None
        last_err = None
        for model_name in self._candidate_models():
            payload = {
                "model": model_name,
                "query": query,
                "documents": documents,
                "top_n": top_n,
            }

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )

            if response.ok:
                data = response.json()
                self.model_name = model_name
                break

            last_err = response
            try:
                err_json = response.json()
                err_text = str(err_json).lower()
            except Exception:
                err_text = response.text.lower()

            if "model does not exist" not in err_text and "invalid model" not in err_text:
                response.raise_for_status()

        if data is None:
            if last_err is not None:
                last_err.raise_for_status()
            raise ValueError("No valid rerank model candidate found.")

        # Common shape: {"results": [{"index": 0, "relevance_score": 0.9, ...}, ...]}
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            output = []
            for item in data["results"]:
                output.append(
                    {
                        "index": item.get("index"),
                        "relevance_score": item.get("relevance_score"),
                    }
                )
            return output

        # Alternative shape: {"data": [{"index": 0, "score": 0.9, ...}, ...]}
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            output = []
            for item in data["data"]:
                output.append(
                    {
                        "index": item.get("index"),
                        "relevance_score": item.get("relevance_score", item.get("score")),
                    }
                )
            return output

        raise ValueError(f"Unsupported rerank response format: {data}")
