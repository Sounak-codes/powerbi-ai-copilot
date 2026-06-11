"""
BM25 keyword search for RAG retrieval.

Provides traditional keyword-based search using the BM25 algorithm
for lexical matching. Complements semantic vector search.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import math
import re
from collections import Counter
from config import get_logger

logger = get_logger(__name__)


@dataclass
class BM25Result:
    """A single BM25 search result."""
    document_id: str
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    matched_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "text": self.text,
            "score": round(self.score, 4),
            "metadata": self.metadata,
            "matched_terms": self.matched_terms,
        }


class BM25Search:
    """
    BM25 keyword search implementation.

    Parameters:
        k1: Term frequency saturation parameter (default 1.5).
        b: Document length normalization parameter (default 0.75).
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._documents: List[Dict[str, Any]] = []
        self._tokenized_docs: List[List[str]] = []
        self._doc_lengths: List[int] = []
        self._avg_doc_length: float = 0.0
        self._idf_cache: Dict[str, float] = {}
        self._doc_freqs: Dict[str, int] = {}
        self._n_docs: int = 0

    def index_documents(self, documents: List[Dict[str, Any]]):
        """
        Index documents for BM25 search.

        Args:
            documents: List of dicts with "id", "text", and optional "metadata".
        """
        self._documents = documents
        self._tokenized_docs = []
        self._doc_freqs = {}

        for doc in documents:
            tokens = self._tokenize(doc.get("text", ""))
            self._tokenized_docs.append(tokens)

            # Count document frequency for each unique term
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self._doc_freqs[token] = self._doc_freqs.get(token, 0) + 1

        self._n_docs = len(documents)
        self._doc_lengths = [len(tokens) for tokens in self._tokenized_docs]
        self._avg_doc_length = (
            sum(self._doc_lengths) / self._n_docs if self._n_docs > 0 else 0
        )

        # Precompute IDF
        self._idf_cache = {
            term: self._compute_idf(df)
            for term, df in self._doc_freqs.items()
        }

        logger.info(f"BM25: Indexed {self._n_docs} documents, {len(self._doc_freqs)} unique terms")

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> List[BM25Result]:
        """
        Search for documents matching the query.

        Args:
            query: Search query text.
            top_k: Number of results to return.
            min_score: Minimum BM25 score threshold.

        Returns:
            List of BM25Results ranked by score.
        """
        if not self._tokenized_docs:
            return []

        query_tokens = self._tokenize(query)
        scores = []

        for i, doc_tokens in enumerate(self._tokenized_docs):
            score, matched = self._score_document(query_tokens, doc_tokens, i)
            if score > min_score:
                scores.append((i, score, matched))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for i, score, matched in scores[:top_k]:
            doc = self._documents[i]
            results.append(BM25Result(
                document_id=doc.get("id", str(i)),
                text=doc.get("text", ""),
                score=score,
                metadata=doc.get("metadata", {}),
                matched_terms=matched,
            ))

        return results

    def _score_document(
        self, query_tokens: List[str], doc_tokens: List[str], doc_idx: int
    ) -> tuple:
        """Compute BM25 score for a document."""
        doc_length = self._doc_lengths[doc_idx]
        term_freqs = Counter(doc_tokens)
        score = 0.0
        matched_terms = []

        for term in query_tokens:
            if term not in self._idf_cache:
                continue

            tf = term_freqs.get(term, 0)
            if tf == 0:
                continue

            idf = self._idf_cache[term]

            # BM25 formula
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (
                1 - self.b + self.b * (doc_length / self._avg_doc_length)
            )

            score += idf * (numerator / denominator)
            matched_terms.append(term)

        return score, matched_terms

    def _compute_idf(self, doc_freq: int) -> float:
        """Compute IDF for a term."""
        return math.log(
            (self._n_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1
        )

    def _tokenize(self, text: str) -> List[str]:
        """Simple whitespace + punctuation tokenizer with lowercasing."""
        text = text.lower()
        # Remove punctuation, keep alphanumeric and spaces
        text = re.sub(r"[^\w\s]", " ", text)
        tokens = text.split()
        # Remove very short tokens
        return [t for t in tokens if len(t) > 1]

    @property
    def document_count(self) -> int:
        return self._n_docs
