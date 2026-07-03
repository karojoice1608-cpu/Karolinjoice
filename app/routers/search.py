"""
Search Router for Screendex.
Provides keyword search endpoints with relevance ranking.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.models import Image, Keyword, ProcessingStatusEnum, User
from app.schemas import SearchResponse, StatsSchema, KeywordEntry
from app.services.search_service import search_images
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"], dependencies=[Depends(get_current_user)])


@router.get("/", response_model=SearchResponse)
def search(
    q:          str            = Query(..., min_length=1, description="Search query"),
    image_type: Optional[str]  = Query(None, description="Filter: born_digital | scene_text"),
    category:   Optional[str]  = Query(None, description="Filter: Receipt | Document | etc."),
    semantic:   bool           = Query(False, description="Use semantic search"),
    page:       int            = Query(1, ge=1),
    page_size:  int            = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Search indexed images by keyword.

    Examples:
      /api/search/?q=python+error
      /api/search/?q=CNN+architecture&image_type=born_digital
      /api/search/?q=contract+violation&page=2
    """
    offset = (page - 1) * page_size
    results, total = search_images(
        db         = db,
        query      = q,
        user_id    = user.id,
        image_type = image_type,
        category   = category,
        limit      = page_size,
        offset     = offset,
        use_semantic = semantic,
    )

    return SearchResponse(
        query         = q,
        total_results = total,
        page          = page,
        page_size     = page_size,
        results       = results,
    )


@router.get("/suggest")
def suggest_keywords(
    q:  str     = Query(..., min_length=1),
    limit: int  = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Auto-complete suggestions based on indexed keywords.
    Useful for search input suggestions.
    """
    suggestions = (
        db.query(Keyword.keyword, func.sum(Keyword.frequency).label("total"))
        .join(Image, Image.id == Keyword.image_id)
        .filter(Image.user_id == user.id)
        .filter(Keyword.keyword.ilike(f"{q}%"))
        .filter(Keyword.is_stopword == False)
        .group_by(Keyword.keyword)
        .order_by(func.sum(Keyword.frequency).desc())
        .limit(limit)
        .all()
    )
    return [{"keyword": s.keyword, "frequency": s.total} for s in suggestions]


@router.get("/stats", response_model=StatsSchema)
def get_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Return system-wide statistics about the index."""
    from app.models.models import ImageTypeEnum

    total     = db.query(Image).filter(Image.user_id == user.id).count()
    processed = db.query(Image).filter(Image.user_id == user.id, Image.status == ProcessingStatusEnum.completed).count()
    failed    = db.query(Image).filter(Image.user_id == user.id, Image.status == ProcessingStatusEnum.failed).count()
    pending   = db.query(Image).filter(Image.user_id == user.id, Image.status == ProcessingStatusEnum.pending).count()
    total_kw  = db.query(func.count(Keyword.id)).join(Image).filter(Image.user_id == user.id).scalar() or 0
    born_d    = db.query(Image).filter(Image.user_id == user.id, Image.image_type == ImageTypeEnum.born_digital).count()
    scene_t   = db.query(Image).filter(Image.user_id == user.id, Image.image_type == ImageTypeEnum.scene_text).count()

    return StatsSchema(
        total_images     = total,
        processed_images = processed,
        failed_images    = failed,
        pending_images   = pending,
        total_keywords   = total_kw,
        born_digital     = born_d,
        scene_text       = scene_t,
    )


@router.get("/keywords", response_model=List[KeywordEntry])
def list_keywords(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all indexed keywords with their IDs and associated metadata."""
    return db.query(Keyword).join(Image).filter(Image.user_id == user.id).limit(limit).all()
