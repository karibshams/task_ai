import json
import math
import os
import re
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from rag.indexer import build_or_load_index, get_embedding

def cosine_similarity(v1: list, v2: list) -> float:
    """Compute cosine similarity between two numeric vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)

def keyword_overlap_score(query: str, text: str) -> float:
    """Calculates simple term overlap ratio between query and chunk text."""
    query_terms = set(re.findall(r"\w+", query.lower()))
    if not query_terms:
        return 0.0
    # Filter common stop words
    stop_words = {"what", "is", "the", "for", "a", "an", "in", "to", "of", "and", "or", "how", "can", "do", "does"}
    meaningful_terms = query_terms - stop_words
    if not meaningful_terms:
        meaningful_terms = query_terms

    text_words = set(re.findall(r"\w+", text.lower()))
    overlap = meaningful_terms.intersection(text_words)
    return len(overlap) / len(meaningful_terms)

class PolicyVectorStore:
    def __init__(self):
        self.chunks = build_or_load_index()

    def search(self, query: str, top_k: int = 3, min_similarity: float = 0.50):
        """
        Performs hybrid vector + keyword search over policy document chunks.
        Returns a list of dicts with score, citations, and content.
        """
        if not self.chunks:
            return []

        # Get query embedding
        try:
            q_emb = get_embedding(query)
        except Exception as e:
            print(f"[VectorStore] Embedding error: {e}. Falling back to keyword search.")
            q_emb = None

        results = []
        for chunk in self.chunks:
            c_emb = chunk.get("embedding")
            sim = cosine_similarity(q_emb, c_emb) if (q_emb and c_emb) else 0.0
            kw = keyword_overlap_score(query, f"{chunk['title']} {chunk['content']}")

            # Hybrid score
            if q_emb:
                score = (0.75 * sim) + (0.25 * kw)
            else:
                score = kw

            results.append({
                "id": chunk["id"],
                "section": chunk["section"],
                "policy_ref": chunk.get("policy_ref", "SRV-POL-001"),
                "page": chunk["page"],
                "title": chunk["title"],
                "content": chunk["content"],
                "similarity": sim,
                "keyword_score": kw,
                "score": score,
                "citation": f"Policy {chunk.get('policy_ref', 'SRV-POL-001')}, Section {chunk['section']} (Page {chunk['page']}: {chunk['title']})"
            })

        # Sort descending by composite score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def format_context_for_llm(self, query: str, top_k: int = 3) -> tuple[str, list]:
        """
        Returns (formatted_context_string, citations_list).
        """
        matches = self.search(query, top_k=top_k)
        if not matches:
            return "No relevant policy context found.", []

        context_blocks = []
        citations = []
        for m in matches:
            citation_str = m["citation"]
            citations.append(citation_str)
            block = (
                f"--- [CITATION: {citation_str}] ---\n"
                f"{m['content']}\n"
            )
            context_blocks.append(block)

        formatted_context = "\n".join(context_blocks)
        return formatted_context, citations

# Global singleton
_vector_store_instance = None

def get_vector_store() -> PolicyVectorStore:
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = PolicyVectorStore()
    return _vector_store_instance

if __name__ == "__main__":
    store = get_vector_store()
    print("\n--- Test Search 1: Maximum Price ---")
    res1 = store.search("What is the maximum price allowed for creating a service?")
    for r in res1:
        print(f"Score: {r['score']:.3f} | Citation: {r['citation']}")

    print("\n--- Test Search 2: Employee Bonus ---")
    res2 = store.search("What is the company's employee bonus policy?")
    for r in res2:
        print(f"Score: {r['score']:.3f} | Citation: {r['citation']}")

