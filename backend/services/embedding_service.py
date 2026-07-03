"""
Semantic Embedding Service
───────────────────────────
Generates dense vector embeddings from text using a sentence-transformer model.
These embeddings enable semantic search: finding images whose extracted text is
semantically similar to the query, even without exact keyword overlap.

Example:
    Query: "payment due"
    Keyword search: finds images containing "payment due" literally
    Semantic search: also finds images containing "amount payable", "invoice total"

[Inference] Semantic similarity quality depends on the sentence-transformer model
chosen and the domain of the text. 'all-MiniLM-L6-v2' is a general-purpose model
and may not be optimal for all use cases.

pgvector:
    If the PostgreSQL pgvector extension is installed, embeddings are stored in a
    proper VECTOR column for fast approximate nearest-neighbour search.
    If not available, cosine similarity is computed in Python on retrieval
    (slower, acceptable for small-to-medium repositories).
"""

import json
import logging
import math
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)

# ─── Lazy singleton ───────────────────────────────────────────────────────────

_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(settings.sentence_transformer_model)
            logger.info(f"Sentence transformer loaded: {settings.sentence_transformer_model}")
        except ImportError:
            logger.warning("sentence-transformers not installed — semantic search disabled")
        except Exception as e:
            logger.error(f"Failed to load sentence transformer: {e}")
    return _model


# ─── Public interface ─────────────────────────────────────────────────────────

def embed_text(text: str) -> Optional[list[float]]:
    """
    Generate a normalised embedding vector for the given text.
    Returns None if the model is unavailable.
    """
    if not text or not text.strip():
        return None

    model = _get_model()
    if model is None:
        return None

    try:
        embedding = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return None


def embedding_to_json(embedding: list[float]) -> str:
    """Serialise embedding to JSON string for storage in TEXT column."""
    return json.dumps(embedding)


def embedding_from_json(json_str: str) -> Optional[list[float]]:
    """Deserialise embedding from JSON string."""
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except Exception:
        return None


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two equal-length vectors.
    Both vectors are assumed to be normalised (unit length), so this
    reduces to a dot product.
    """
    if len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    # Clamp to [-1, 1] due to floating-point imprecision
    return max(-1.0, min(1.0, dot))


def rank_by_semantic_similarity(
    query: str,
    candidates: list[dict],  # Each must have "embedding_json" and "id"
    threshold: float = None,
    top_k: int = 50,
) -> list[dict]:
    """
    Score and rank candidates by semantic similarity to the query.

    Args:
        query: User search string.
        candidates: List of dicts with at minimum {"id": ..., "embedding_json": ...}
        threshold: Minimum cosine similarity to include in results.
                   Defaults to settings.semantic_threshold.
        top_k: Maximum number of results to return.

    Returns:
        Candidates sorted by semantic_score descending, filtered by threshold.
        Each dict gets a "semantic_score" key added.

    [Inference] In-Python cosine similarity is O(n * dim) and may be slow for
    repositories > 10,000 images. Use pgvector for production-scale deployments.
    """
    if threshold is None:
        threshold = settings.semantic_threshold

    query_embedding = embed_text(query)
    if query_embedding is None:
        return candidates  # Semantic ranking unavailable; return as-is

    scored = []
    for candidate in candidates:
        emb_json = candidate.get("embedding_json")
        if not emb_json:
            candidate["semantic_score"] = 0.0
            scored.append(candidate)
            continue

        emb = embedding_from_json(emb_json)
        if emb is None:
            candidate["semantic_score"] = 0.0
            scored.append(candidate)
            continue

        score = cosine_similarity(query_embedding, emb)
        candidate["semantic_score"] = round(score, 4)
        scored.append(candidate)

    filtered = [c for c in scored if c["semantic_score"] >= threshold]
    filtered.sort(key=lambda c: c["semantic_score"], reverse=True)
    return filtered[:top_k]
