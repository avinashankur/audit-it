"""In-memory lexical and BM25 similarity store for text chunks."""

import math
import re
from typing import Any

from src.core.logging import get_logger, profile_stage
from src.db.models.entities import TextChunk

logger = get_logger(__name__)

# Stopwords to filter out noise from scoring
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "could", "did", "do", "does", "doing", "down",
    "during", "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only",
    "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "we",
    "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "with", "would", "you", "your", "yours", "yourself", "yourselves",
}


def tokenize(text: str) -> list[str]:
    """Tokenize text into cleaned alphanumeric words, filtering common stopwords."""
    words = re.findall(r"\b[A-Za-z0-9_\$%-]{2,}\b", text.lower())
    return [w for w in words if w not in STOPWORDS]


class VectorStore:
    """Fast, in-memory BM25 retrieval index for TextChunk models."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunks: list[TextChunk] = []
        self.doc_len: list[int] = []
        self.avg_doc_len: float = 0.0
        self.doc_freqs: dict[str, int] = {}
        self.term_freqs: list[dict[str, int]] = []
        self.idf: dict[str, float] = {}

    @profile_stage("vector_store_index")
    def add_chunks(self, chunks: list[TextChunk]) -> None:
        """Add and index text chunks."""
        self.chunks = list(chunks)
        self.doc_len = []
        self.term_freqs = []
        self.doc_freqs = {}

        for chunk in self.chunks:
            # Combine section header and body for broader indexing
            full_text = f"{chunk.section_header or ''} {chunk.text}"
            tokens = tokenize(full_text)
            self.doc_len.append(len(tokens))

            tf: dict[str, int] = {}
            seen: set[str] = set()
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
                if t not in seen:
                    self.doc_freqs[t] = self.doc_freqs.get(t, 0) + 1
                    seen.add(t)

            self.term_freqs.append(tf)

        n = len(self.chunks)
        self.avg_doc_len = sum(self.doc_len) / max(1, n)

        # Precompute BM25 IDF
        self.idf = {}
        for term, df in self.doc_freqs.items():
            self.idf[term] = math.log((n - df + 0.5) / (df + 0.5) + 1.0)

        logger.info(f"Indexed {n} chunks across {len(self.doc_freqs)} distinct terms.")

    def search(self, query: str, top_k: int = 5) -> list[tuple[TextChunk, float]]:
        """Score and rank chunks for a query using BM25.

        Returns:
            list of (chunk, score) tuples sorted by descending relevance.
        """
        if not self.chunks or not query:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores: list[float] = [0.0] * len(self.chunks)

        for token in query_tokens:
            idf = self.idf.get(token)
            if not idf:
                continue

            for idx, tf_dict in enumerate(self.term_freqs):
                freq = tf_dict.get(token, 0)
                if freq == 0:
                    continue

                d_len = self.doc_len[idx]
                norm = 1.0 - self.b + self.b * (d_len / max(1.0, self.avg_doc_len))
                score = idf * ((freq * (self.k1 + 1.0)) / (freq + self.k1 * norm))
                scores[idx] += score

        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        # Filter zero-score chunks so unrelated queries return no matches
        positive = [(self.chunks[i], score) for i, score in ranked if score > 0]
        return positive[:top_k]

    def search_chunks(self, query: str, top_k: int = 5) -> list[TextChunk]:
        """Convenience method returning only the top TextChunk instances."""
        results = self.search(query=query, top_k=top_k)
        return [c for c, _ in results]

    def clear(self) -> None:
        """Clear the index."""
        self.chunks.clear()
        self.doc_len.clear()
        self.doc_freqs.clear()
        self.term_freqs.clear()
        self.idf.clear()
