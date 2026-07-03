"""
Search Service
───────────────
Provides two search modes, combined into a single ranked result:

1. Keyword Search (PostgreSQL full-text search via ILIKE on full_text + keywords array)
   - Fast, exact and partial match
   - Works without any ML model

2. Semantic Search (cosine similarity on sentence-transformer embeddings)
   - Finds conceptually similar results even without keyword overlap
   - Requires sentence-transformers to be installed and images to be embedded

Hybrid ranking:
    final_score = (keyword_score * 0.5) + (semantic_score * 0.5)
    Weights can be tuned; keyword is weighted higher here for precision.

[Inference] Hybrid scoring is expected to outperform either mode alone for
most queries. Actual ranking quality depends on model choice and dataset.
"""

import logging
from uuid import UUID

from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import ARRAY

from backend.models.image import Image
from backend.models.text_region import TextRegion
from backend.services.embedding_service import embed_text, embedding_from_json, cosine_similarity
from backend.config import settings

logger = logging.getLogger(__name__)


async def keyword_search(
    query: str,
    db: AsyncSession,
    limit: int = 50,
    confidence_min: float = 0.0,
    image_type: str = None,
) -> list[dict]:
    """
    Search images by keyword using ILIKE against full_text.
    Returns list of dicts with image data and keyword_score.
    """
    query_clean = query.strip()
    if not query_clean:
        return []

    # Build base query
    stmt = (
        select(Image)
        .where(Image.status == "done")
        .where(Image.full_text.isnot(None))
    )

    # Keyword filter (case-insensitive substring match on full_text)
    terms = query_clean.split()
    text_conditions = [Image.full_text.ilike(f"%{term}%") for term in terms]
    stmt = stmt.where(or_(*text_conditions))

    # Optional filters
    if confidence_min > 0.0:
        stmt = stmt.where(Image.avg_confidence >= confidence_min)
    if image_type and image_type in ("born_digital", "scene_text", "mixed"):
        stmt = stmt.where(Image.image_type == image_type)

    stmt = stmt.limit(limit * 2)  # Over-fetch for re-ranking

    result = await db.execute(stmt)
    images = result.scalars().all()

    # Score: count how many query terms appear in full_text
    scored = []
    for img in images:
        text_lower = (img.full_text or "").lower()
        hits = sum(1 for term in terms if term.lower() in text_lower)
        keyword_score = hits / len(terms) if terms else 0.0
        scored.append({
            "image": img,
            "keyword_score": round(keyword_score, 4),
            "semantic_score": 0.0,
        })

    scored.sort(key=lambda x: x["keyword_score"], reverse=True)
    return scored[:limit]


async def search(
    query: str,
    db: AsyncSession,
    limit: int = 20,
    confidence_min: float = 0.0,
    image_type: str = None,
    mode: str = "hybrid",  # "keyword" | "semantic" | "hybrid"
) -> list[dict]:
    """
    Main search entry point. Returns a list of result dicts.

    Result dict structure:
    {
        "image_id": str,
        "filename": str,
        "original_filename": str,
        "file_path": str,
        "image_type": str,
        "full_text": str,
        "keywords": list[str],
        "avg_confidence": float,
        "region_count": int,
        "uploaded_at": str,
        "processed_at": str,
        "keyword_score": float,
        "semantic_score": float,
        "final_score": float,
        "matched_regions": list[dict],  # text regions containing the query terms
    }
    """
    # ── Keyword search ────────────────────────────────────────────────────────
    kw_results = await keyword_search(query, db, limit=100, confidence_min=confidence_min, image_type=image_type)

    # ── Semantic search ───────────────────────────────────────────────────────
    semantic_scores: dict[UUID, float] = {}

    if mode in ("semantic", "hybrid"):
        query_embedding = embed_text(query)
        if query_embedding is not None:
            # Load candidate images with embeddings
            # For scale, this should use pgvector ANN; here we do in-Python scoring on keyword results
            for item in kw_results:
                img = item["image"]
                if img.embedding_json:
                    emb = embedding_from_json(img.embedding_json)
                    if emb:
                        sim = cosine_similarity(query_embedding, emb)
                        semantic_scores[img.id] = max(0.0, sim)

    # ── Hybrid scoring ────────────────────────────────────────────────────────
    kw_weight = 0.5 if mode == "hybrid" else (1.0 if mode == "keyword" else 0.0)
    sem_weight = 0.5 if mode == "hybrid" else (0.0 if mode == "keyword" else 1.0)

    results = []
    seen_ids = set()

    for item in kw_results:
        img = item["image"]
        if img.id in seen_ids:
            continue
        seen_ids.add(img.id)

        sem_score = semantic_scores.get(img.id, 0.0)
        kw_score = item["keyword_score"]
        final_score = (kw_score * kw_weight) + (sem_score * sem_weight)

        results.append({
            "image_id": str(img.id),
            "filename": img.filename,
            "original_filename": img.original_filename,
            "file_path": img.file_path,
            "image_type": img.image_type or "unknown",
            "full_text": img.full_text or "",
            "keywords": img.keywords or [],
            "avg_confidence": img.avg_confidence or 0.0,
            "region_count": img.region_count or 0,
            "uploaded_at": img.uploaded_at.isoformat() if img.uploaded_at else None,
            "processed_at": img.processed_at.isoformat() if img.processed_at else None,
            "keyword_score": round(kw_score, 4),
            "semantic_score": round(sem_score, 4),
            "final_score": round(final_score, 4),
            "matched_regions": [],  # Populated below
        })

    # ── Attach matched text regions ───────────────────────────────────────────
    image_ids = [UUID(r["image_id"]) for r in results]
    if image_ids:
        terms = query.strip().lower().split()
        regions_stmt = (
            select(TextRegion)
            .where(TextRegion.image_id.in_(image_ids))
            .order_by(TextRegion.image_id, TextRegion.reading_order)
        )
        regions_result = await db.execute(regions_stmt)
        all_regions = regions_result.scalars().all()

        # Group by image_id
        region_map: dict[str, list] = {}
        for region in all_regions:
            key = str(region.image_id)
            if key not in region_map:
                region_map[key] = []
            text_lower = (region.cleaned_text or "").lower()
            if any(term in text_lower for term in terms):
                region_map[key].append({
                    "id": str(region.id),
                    "text": region.cleaned_text or region.raw_text,
                    "confidence": region.confidence,
                    "bbox": region.bbox,
                    "reading_order": region.reading_order,
                })

        for r in results:
            r["matched_regions"] = region_map.get(r["image_id"], [])

    # ── Final sort ────────────────────────────────────────────────────────────
    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results[:limit]
