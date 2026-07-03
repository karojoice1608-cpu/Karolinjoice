"""
Search Router
──────────────
Endpoints:
    GET  /api/search          Keyword + semantic search
    GET  /api/search/suggest  Keyword autocomplete from indexed keywords
"""

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.image import Image
from backend.services.search_service import search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/")
async def search_images(
    q: str = Query(..., min_length=1, description="Search query"),
    mode: str = Query("hybrid", description="Search mode: keyword | semantic | hybrid"),
    limit: int = Query(20, ge=1, le=100),
    confidence_min: float = Query(0.0, ge=0.0, le=1.0, description="Minimum OCR confidence filter"),
    image_type: str = Query(None, description="Filter by: born_digital | scene_text | mixed"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search indexed images by keyword and/or semantic similarity.

    - **keyword** mode: exact and partial text matches (fast)
    - **semantic** mode: concept similarity via sentence-transformer embeddings
    - **hybrid** mode: combines both scores (recommended)

    Results are ranked by final_score (0.0–1.0) descending.
    Each result includes matched text regions with bounding box coordinates
    that can be used to highlight text within the image.
    """
    if mode not in ("keyword", "semantic", "hybrid"):
        raise HTTPException(status_code=400, detail="mode must be 'keyword', 'semantic', or 'hybrid'")

    results = await search(
        query=q,
        db=db,
        limit=limit,
        confidence_min=confidence_min,
        image_type=image_type,
        mode=mode,
    )

    return {
        "query": q,
        "mode": mode,
        "result_count": len(results),
        "results": results,
    }


@router.get("/suggest")
async def suggest_keywords(
    q: str = Query(..., min_length=1, description="Partial keyword prefix"),
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """
    Return keyword suggestions from the indexed keyword arrays.
    Useful for search autocomplete.
    """
    # Unnest all keyword arrays and find those matching the prefix
    stmt = (
        select(func.unnest(Image.keywords).label("kw"))
        .where(Image.status == "done")
        .where(Image.keywords.isnot(None))
        .distinct()
        .limit(limit * 5)
    )
    result = await db.execute(stmt)
    all_keywords = [row[0] for row in result.fetchall()]

    q_lower = q.lower()
    matching = [kw for kw in all_keywords if kw.startswith(q_lower)]
    matching = sorted(set(matching))[:limit]

    return {"query": q, "suggestions": matching}


@router.get("/stats")
async def search_stats(db: AsyncSession = Depends(get_db)):
    """
    Return basic statistics about the indexed image repository.
    """
    stmt = select(
        func.count(Image.id).label("total"),
        func.count(Image.id).filter(Image.status == "done").label("indexed"),
        func.count(Image.id).filter(Image.status == "pending").label("pending"),
        func.count(Image.id).filter(Image.status == "processing").label("processing"),
        func.count(Image.id).filter(Image.status == "failed").label("failed"),
        func.avg(Image.avg_confidence).filter(Image.status == "done").label("avg_confidence"),
        func.sum(Image.region_count).filter(Image.status == "done").label("total_regions"),
    )
    result = await db.execute(stmt)
    row = result.one()

    return {
        "total_images": row.total or 0,
        "indexed": row.indexed or 0,
        "pending": row.pending or 0,
        "processing": row.processing or 0,
        "failed": row.failed or 0,
        "avg_confidence": round(float(row.avg_confidence or 0), 4),
        "total_text_regions": row.total_regions or 0,
    }
