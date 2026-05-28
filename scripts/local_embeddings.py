import math
import os
import requests
import sys

def get_embedding(text: str, model: str = "nomic-embed-text") -> list:
    """
    Fetches text embeddings using the local Ollama API.
    Ensure `ollama pull nomic-embed-text` has been run.
    """
    from utils import load_llm_settings
    settings = load_llm_settings()
    base_url = settings.get('localUrl') or os.getenv('OLLAMA_HOST') or 'http://localhost:11434'
    endpoint = base_url.rstrip('/') + '/api/embeddings'

    try:
        res = requests.post(
            endpoint,
            json={"model": model, "prompt": text},
            timeout=10
        )
        if res.status_code == 200:
            return res.json().get("embedding", [])
    except Exception as e:
        print(f"    [Embedding Error] Failed to fetch from Ollama: {e}", file=sys.stderr)
    return []


def cosine_similarity(v1: list, v2: list) -> float:
    """Computes cosine similarity between two vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = math.sqrt(sum(a * a for a in v1))
    norm_v2 = math.sqrt(sum(b * b for b in v2))
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)


class BM25:
    """
    Lightweight BM25 implementation for context pruning.
    No heavy dependencies required.
    """
    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.avgdl = 0
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []

        self._initialize()

    def _tokenize(self, text: str) -> list[str]:
        # Simple tokenization: lowercase, remove non-alphanumeric
        import re
        text = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())
        return text.split()

    def _initialize(self):
        df = {}
        num_docs = 0
        total_length = 0

        for document in self.corpus:
            num_docs += 1
            tokens = self._tokenize(document)
            self.doc_len.append(len(tokens))
            total_length += len(tokens)
            
            frequencies = {}
            for token in tokens:
                frequencies[token] = frequencies.get(token, 0) + 1
            self.doc_freqs.append(frequencies)
            
            for token in set(tokens):
                df[token] = df.get(token, 0) + 1

        self.avgdl = total_length / num_docs if num_docs > 0 else 0

        # Calculate IDF
        for token, freq in df.items():
            # Standard BM25 IDF formula
            idf_score = math.log(1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))
            self.idf[token] = idf_score

    def get_scores(self, query: str) -> list[float]:
        scores = [0.0] * self.corpus_size
        query_tokens = self._tokenize(query)
        
        for index in range(self.corpus_size):
            score = 0.0
            doc_len = self.doc_len[index]
            frequencies = self.doc_freqs[index]
            for token in query_tokens:
                if token not in frequencies:
                    continue
                freq = frequencies[token]
                num = freq * (self.k1 + 1)
                den = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                score += self.idf.get(token, 0) * (num / den)
            scores[index] = score
        return scores

    def get_top_n(self, query: str, n: int = 2) -> list[tuple[int, float]]:
        scores = self.get_scores(query)
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        return indexed_scores[:n]

_TAG_ANCHORS = None
def fast_tag_jd(jd_vector: list) -> list[str]:
    """
    Rapidly tags a JD based on cosine similarity to predefined anchor vectors.
    Saves LLM inference time by using cheap vector arithmetic.
    """
    global _TAG_ANCHORS
    if not jd_vector:
        return []
        
    tags = {
        "B2B SaaS": "Business to business software as a service enterprise platform",
        "Data Platform": "Data pipeline data platform analytics data warehouse",
        "AI / ML": "Artificial intelligence machine learning LLM predictive models",
        "Healthcare / Regulated": "Healthcare HIPAA regulated compliance medical",
        "FinTech": "Financial technology payments banking compliance ledger"
    }
    
    if _TAG_ANCHORS is None:
        _TAG_ANCHORS = {}
        for tag, text in tags.items():
            vec = get_embedding(text)
            if vec:
                _TAG_ANCHORS[tag] = vec
                
    results = []
    for tag, anchor_vec in _TAG_ANCHORS.items():
        if cosine_similarity(jd_vector, anchor_vec) > 0.65:
            results.append(tag)
            
    return results


_COMPETITOR_VECTORS = None
def build_competitor_matrix(jd_text: str) -> list[str]:
    """
    Finds the closest competitors based on JD text using pre-computed vector embeddings.
    """
    global _COMPETITOR_VECTORS
    if _COMPETITOR_VECTORS is None:
        competitors = [
            "Salesforce CRM Enterprise", "HubSpot Marketing Automation B2B",
            "Snowflake Cloud Data Warehouse", "Databricks AI Data Platform",
            "Stripe Payments API FinTech", "Plaid Financial Data Network",
            "Twilio Cloud Communications API", "Okta Identity Access Management",
            "CrowdStrike Endpoint Security", "Palo Alto Networks Cybersecurity",
            "Epic Systems Healthcare IT", "Cerner Medical Records EHR"
        ]
        _COMPETITOR_VECTORS = {c: get_embedding(c) for c in competitors}
        
    jd_vector = get_embedding(jd_text)
    if not jd_vector:
        return []
        
    scores = []
    for comp, c_vec in _COMPETITOR_VECTORS.items():
        if c_vec:
            scores.append((comp, cosine_similarity(jd_vector, c_vec)))
            
    scores.sort(key=lambda x: x[1], reverse=True)
    return [c[0] for c in scores[:3]]
