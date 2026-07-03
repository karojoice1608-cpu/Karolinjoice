"""
Search Service for Screendex.
Provides keyword-based retrieval with relevance ranking.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple

from sqlalchemy import or_, func, text
from sqlalchemy.orm import Session

from app.models.models import Image, ExtractedText, Keyword, ProcessingStatusEnum

logger = logging.getLogger(__name__)


def search_images(
    db: Session,
    query: str,
    user_id: int,
    image_type: Optional[str] = None,
    category:   Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    use_semantic: bool = False,
) -> Tuple[List[Dict], int]:
    """
    Search images by keyword query.

    Algorithm:
      1. Tokenize query into keywords
      2. Match against keywords table (index scan) — fast path
      3. Also match against extracted_texts (full-text ILIKE) — recall
      4. Score results: keyword freq + confidence + text occurrence count
      5. Deduplicate and rank by relevance score

    Returns (results_list, total_count)
    """
    if not query or not query.strip():
        return [], 0

    if use_semantic:
        from app.services.semantic_service import semantic_service
        semantic_results = semantic_service.search(query, top_k=limit+offset)
        if not semantic_results:
            return [], 0
            
        image_ids = [res[0] for res in semantic_results]
        
        image_query = (
            db.query(Image)
            .filter(Image.id.in_(image_ids))
            .filter(Image.user_id == user_id)
            .filter(Image.status == ProcessingStatusEnum.completed)
        )
        if image_type:
            image_query = image_query.filter(Image.image_type == image_type)
        if category:
            image_query = image_query.filter(Image.category == category)
            
        images = image_query.all()
        score_map = {res[0]: res[1] for res in semantic_results}
        
        # keep only authorized valid images
        filtered_images = [img for img in images if img.id in score_map]
        filtered_images.sort(key=lambda x: score_map[x.id], reverse=True)
        
        total = len(semantic_results) # approximate total context based on top K lookup
        subset = filtered_images[offset:offset+limit]
        
        results = []
        for img in subset:
            query_tokens = _tokenize_query(query)
            _, snippets, bboxes = _compute_score_and_snippets(db, img, query_tokens) # get highlights
            
            # cosine sim is roughly -1 to 1; transform to 0-100% roughly
            score_val = score_map[img.id]
            # scale similarity if using Inner Product with normalized vectors (like all-MiniLM)
            pct_score = max(0.0, min(100.0, (score_val + 0.1) * 90.0)) 
            
            results.append({
                "id":            img.id,
                "filename":      img.original_name,
                "file_path":     img.file_path,
                "thumbnail_path":img.thumbnail_path,
                "image_type":    img.image_type.value if img.image_type else "unknown",
                "uploaded_at":   img.uploaded_at.isoformat() if img.uploaded_at else None,
                "relevance_score": round(pct_score, 1),
                "category":      img.category,
                "subject":       getattr(img, "subject", None),
                "subject_conf":  getattr(img, "subject_conf", 0.0),
                "is_duplicate":  img.is_duplicate,
                "original_id":   img.original_id,
                "matched_snippets": snippets[:3],
                "text_regions":  bboxes,
            })
            
        return results, total

    query_tokens = _tokenize_query(query)
    if not query_tokens:
        return [], 0

    # ── Keyword table search ───────────────────────────
    kw_conditions = [Keyword.keyword.in_(query_tokens)]
    kw_image_ids  = (
        db.query(Keyword.image_id, func.sum(Keyword.frequency).label("kw_score"))
        .filter(or_(*kw_conditions))
        .filter(Keyword.is_stopword == False)
        .group_by(Keyword.image_id)
        .subquery()
    )

    # ── Full-text search in extracted_texts ───────────
    ft_conditions = [ExtractedText.text_content.ilike(f"%{t}%") for t in query_tokens]
    ft_image_ids  = (
        db.query(
            ExtractedText.image_id,
            func.count(ExtractedText.id).label("ft_score"),
            func.avg(ExtractedText.confidence).label("avg_confidence"),
        )
        .filter(or_(*ft_conditions))
        .group_by(ExtractedText.image_id)
        .subquery()
    )

    # ── Join and score ─────────────────────────────────
    image_query = (
        db.query(Image)
        .outerjoin(kw_image_ids, Image.id == kw_image_ids.c.image_id)
        .outerjoin(ft_image_ids, Image.id == ft_image_ids.c.image_id)
        .filter(
            or_(
                kw_image_ids.c.image_id.isnot(None),
                ft_image_ids.c.image_id.isnot(None),
            )
        )
        .filter(Image.user_id == user_id)
        .filter(Image.status == ProcessingStatusEnum.completed)
    )

    if image_type:
        image_query = image_query.filter(Image.image_type == image_type)
    if category:
        image_query = image_query.filter(Image.category == category)

    total = image_query.count()
    images = image_query.offset(offset).limit(limit).all()

    # ── Build result dicts with snippets & scores ─────
    results = []
    for img in images:
        score, snippets, bboxes = _compute_score_and_snippets(db, img, query_tokens)

        results.append({
            "id":            img.id,
            "filename":      img.original_name,
            "file_path":     img.file_path,
            "thumbnail_path":img.thumbnail_path,
            "image_type":    img.image_type.value if img.image_type else "unknown",
            "uploaded_at":   img.uploaded_at.isoformat() if img.uploaded_at else None,
            "relevance_score": round(score * 100, 1),   # percentage 0–100
            "category":      img.category,
            "subject":       getattr(img, "subject", None),
            "subject_conf":  getattr(img, "subject_conf", 0.0),
            "is_duplicate":  img.is_duplicate,
            "original_id":   img.original_id,
            "matched_snippets": snippets[:3],            # top 3 snippets
            "text_regions":  bboxes,
        })

    # Sort by relevance score descending
    results.sort(key=lambda r: r["relevance_score"], reverse=True)
    return results, total


def _tokenize_query(query: str) -> List[str]:
    """Clean and tokenize search query."""
    query = query.lower().strip()
    tokens = re.findall(r"\b[a-z0-9][a-z0-9_\-]{0,49}\b", query)
    # Remove pure stopwords only if multiple tokens
    from app.services.ocr_service import STOPWORDS, STEMMER
    filtered = []
    has_multiple = len(tokens) > 1
    
    for t in tokens:
        if has_multiple and t in STOPWORDS:
            continue
        filtered.append(t)
        if STEMMER is not None and t not in STOPWORDS and not re.match(r"^\d+$", t):
            stemmed = STEMMER.stem(t)
            if stemmed != t:
                filtered.append(stemmed)
                
    return list(set(filtered)) if filtered else tokens


def _compute_score_and_snippets(
    db: Session,
    image: Image,
    query_tokens: List[str],
) -> Tuple[float, List[str], List[Dict]]:
    """
    Compute relevance score and extract matching text snippets.

    Score formula:
      base_score = sum(kw_frequency for matching keywords) / total_keywords
      confidence_boost = avg(confidence of matching text regions)
      final = 0.6 * base_score + 0.4 * confidence_boost
    """
    # Keyword score
    matching_kws = (
        db.query(Keyword)
        .filter(Keyword.image_id == image.id)
        .filter(Keyword.is_stopword == False)
        .filter(Keyword.keyword.in_(query_tokens))
        .all()
    )
    total_kw_freq = sum(k.frequency for k in db.query(Keyword).filter(Keyword.image_id == image.id).all()) or 1
    kw_score = sum(k.frequency for k in matching_kws) / total_kw_freq

    # Snippet extraction
    matching_texts = (
        db.query(ExtractedText)
        .filter(ExtractedText.image_id == image.id)
        .filter(or_(*[ExtractedText.text_content.ilike(f"%{t}%") for t in query_tokens]))
        .order_by(ExtractedText.confidence.desc())
        .all()
    )

    snippets = []
    bboxes   = []
    confidences = []

    for et in matching_texts:
        snippet = _highlight_snippet(et.text_content, query_tokens)
        snippets.append(snippet)
        confidences.append(et.confidence)
        bboxes.append({
            "x":      et.bbox_x,
            "y":      et.bbox_y,
            "width":  et.bbox_width,
            "height": et.bbox_height,
            "text":   et.text_content,
            "confidence": et.confidence,
        })

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    final_score = min(1.0, 0.6 * kw_score + 0.4 * avg_conf + (0.1 if matching_texts else 0))

    return final_score, snippets, bboxes


def _highlight_snippet(text: str, tokens: List[str], context_chars: int = 80) -> str:
    """Return text snippet with query terms highlighted (using ** marks)."""
    text_lower = text.lower()
    best_pos   = 0

    for token in tokens:
        pos = text_lower.find(token)
        if pos >= 0:
            best_pos = pos
            break

    start   = max(0, best_pos - context_chars // 2)
    end     = min(len(text), best_pos + context_chars // 2)
    snippet = ("..." if start > 0 else "") + text[start:end] + ("..." if end < len(text) else "")

    # Highlight tokens
    for token in tokens:
        pattern     = re.compile(re.escape(token), re.IGNORECASE)
        snippet     = pattern.sub(lambda m: f"**{m.group()}**", snippet)

    return snippet
