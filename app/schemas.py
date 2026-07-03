"""
Pydantic schemas for Screendex API request/response validation.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ── Upload ────────────────────────────────────────────────────────────────────

class ImageUploadResponse(BaseModel):
    id:            int
    filename:      str
    original_name: str
    status:        str
    message:       str

    class Config:
        from_attributes = True


# ── Image detail ──────────────────────────────────────────────────────────────

class BoundingBox(BaseModel):
    x:      Optional[float]
    y:      Optional[float]
    width:  Optional[float]
    height: Optional[float]


class ExtractedTextSchema(BaseModel):
    id:           int
    text_content: str
    confidence:   float
    bbox_x:       Optional[float] = None
    bbox_y:       Optional[float] = None
    bbox_width:   Optional[float] = None
    bbox_height:  Optional[float] = None
    text_order:   int

    class Config:
        from_attributes = True


class KeywordSchema(BaseModel):
    keyword:    str
    frequency:  int
    is_stopword:bool

    class Config:
        from_attributes = True


class KeywordEntry(BaseModel):
    id:         int
    image_id:   int
    keyword:    str
    frequency:  int
    is_stopword:bool

    class Config:
        from_attributes = True


class ImageDetailSchema(BaseModel):
    id:              int
    filename:        str
    original_name:   str
    file_path:       str
    thumbnail_path:  Optional[str]
    image_type:      str
    width:           Optional[int]
    height:          Optional[int]
    status:          str
    uploaded_at:     Optional[datetime]
    processed_at:    Optional[datetime]
    extracted_texts: List[ExtractedTextSchema] = []
    keywords:        List[KeywordSchema] = []
    full_text:       Optional[str]
    
    # New Organization & Management Fields
    category:        Optional[str] = None
    category_conf:   float = 0.0
    is_duplicate:    bool = False
    original_id:     Optional[int] = None
    
    # AI Summarization
    subject:         Optional[str] = None
    subject_conf:    float = 0.0

    class Config:
        from_attributes = True


# ── Search ────────────────────────────────────────────────────────────────────

class SearchResultItem(BaseModel):
    id:               int
    filename:         str
    file_path:        str
    thumbnail_path:   Optional[str]
    image_type:       str
    uploaded_at:      Optional[str]
    relevance_score:  float = Field(..., description="Relevance 0–100%")
    category:         Optional[str] = None
    subject:          Optional[str] = None
    subject_conf:     float = 0.0
    is_duplicate:     bool = False
    original_id:      Optional[int] = None
    matched_snippets: List[str] = []
    text_regions:     List[Dict[str, Any]] = []


class SearchResponse(BaseModel):
    query:        str
    total_results:int
    page:         int
    page_size:    int
    results:      List[SearchResultItem]


# ── Stats ─────────────────────────────────────────────────────────────────────

class StatsSchema(BaseModel):
    total_images:     int
    processed_images: int
    failed_images:    int
    pending_images:   int
    total_keywords:   int
    born_digital:     int
    scene_text:       int
