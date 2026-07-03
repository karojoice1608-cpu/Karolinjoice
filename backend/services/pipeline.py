"""
Image Processing Pipeline
──────────────────────────
Orchestrates the full pipeline for a single image:

    Image File
        │
        ▼
    Load & Validate (OpenCV)
        │
        ▼
    EAST Text Detection  ─── (if EAST model available)
        │
        ▼
    OCR Extraction  ─── EasyOCR (primary) + Tesseract (fallback)
        │
        ▼
    Text Cleaning & NLP (NLTK)
        │
        ▼
    Sentence-Transformer Embedding
        │
        ▼
    PostgreSQL Indexing
"""

import logging
from datetime import datetime
from pathlib import Path
from uuid import UUID

import cv2
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.image import Image
from backend.models.text_region import TextRegion
from backend.services.east_detector import east_detector
from backend.services.ocr_service import run_ocr, run_ocr_on_region
from backend.services.nlp_service import (
    clean_text, extract_keywords, classify_image_type, assign_reading_order
)
from backend.services.embedding_service import embed_text, embedding_to_json

logger = logging.getLogger(__name__)


async def process_image(image_id: UUID, db: AsyncSession) -> None:
    """
    Full pipeline for a single image identified by `image_id`.
    Updates the Image record in-place throughout processing.

    This function is designed to be called from a background task
    (FastAPI BackgroundTasks or an async worker).
    """
    # ── Load DB record ───────────────────────────────────────────────────────
    image_record: Image = await db.get(Image, image_id)
    if image_record is None:
        logger.error(f"Image {image_id} not found in DB")
        return

    image_record.status = "processing"
    await db.flush()

    try:
        # ── Load image from disk ─────────────────────────────────────────────
        image_path = Path(image_record.file_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"OpenCV could not decode image: {image_path}")

        h, w = img_bgr.shape[:2]
        image_record.width_px = w
        image_record.height_px = h

        # ── EAST Text Detection ──────────────────────────────────────────────
        # Try to detect text regions; fall back to whole-image OCR if EAST unavailable
        east_regions = east_detector.detect(img_bgr)
        logger.debug(f"Image {image_id}: EAST found {len(east_regions)} regions")

        # ── OCR Extraction ───────────────────────────────────────────────────
        all_ocr_results = []
        engine_used = settings.ocr_engine

        if east_regions:
            # Run OCR per detected region
            for region in east_regions:
                region_results, eng = run_ocr_on_region(img_bgr, region, settings.ocr_engine)
                for r in region_results:
                    r["east_region"] = region
                    r["engine"] = eng
                all_ocr_results.extend(region_results)
                engine_used = eng
        else:
            # No EAST regions → run OCR on entire image
            logger.debug(f"Image {image_id}: No EAST regions, running whole-image OCR")
            whole_results, eng = run_ocr(img_bgr, settings.ocr_engine)
            all_ocr_results.extend(whole_results)
            engine_used = eng

        # ── NLP Processing ───────────────────────────────────────────────────
        # Clean each text result
        for r in all_ocr_results:
            r["cleaned_text"] = clean_text(r.get("text", ""))

        # Assign reading order
        regions_for_ordering = [
            {"x": r["bbox"]["x"], "y": r["bbox"]["y"],
             "w": r["bbox"]["w"], "h": r["bbox"]["h"],
             "_idx": i}
            for i, r in enumerate(all_ocr_results)
            if r.get("bbox")
        ]
        regions_for_ordering = assign_reading_order(regions_for_ordering)
        order_map = {r["_idx"]: r["reading_order"] for r in regions_for_ordering}

        # Build full concatenated text in reading order
        indexed_results = sorted(
            [(order_map.get(i, i), r) for i, r in enumerate(all_ocr_results)],
            key=lambda x: x[0]
        )
        full_text_parts = [r["cleaned_text"] for _, r in indexed_results if r["cleaned_text"]]
        full_text = " ".join(full_text_parts)

        # Extract keywords from concatenated text
        keywords = extract_keywords(full_text, max_keywords=30)

        # Classify image type
        image_type = classify_image_type(all_ocr_results)

        # Compute average confidence
        confidences = [r["confidence"] for r in all_ocr_results if r.get("confidence") is not None]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        # ── Semantic Embedding ───────────────────────────────────────────────
        embedding = embed_text(full_text)
        embedding_json = embedding_to_json(embedding) if embedding else None

        # ── Persist TextRegion records ───────────────────────────────────────
        for order, r in indexed_results:
            bbox = r.get("bbox") or {}
            region = TextRegion(
                image_id=image_id,
                bbox_x=bbox.get("x", 0),
                bbox_y=bbox.get("y", 0),
                bbox_w=bbox.get("w", 0),
                bbox_h=bbox.get("h", 0),
                raw_text=r.get("text", ""),
                cleaned_text=r.get("cleaned_text", ""),
                confidence=r.get("confidence", 0.0),
                ocr_engine=r.get("engine", engine_used),
                region_type=image_type,
                reading_order=order,
            )
            db.add(region)

        # ── Update Image record ──────────────────────────────────────────────
        image_record.full_text = full_text
        image_record.keywords = keywords
        image_record.avg_confidence = round(avg_conf, 4)
        image_record.region_count = len(all_ocr_results)
        image_record.image_type = image_type
        image_record.ocr_engine_used = engine_used
        image_record.embedding_json = embedding_json
        image_record.status = "done"
        image_record.processed_at = datetime.utcnow()

        await db.flush()
        logger.info(
            f"Image {image_id} processed: {len(all_ocr_results)} regions, "
            f"engine={engine_used}, type={image_type}, conf={avg_conf:.2f}"
        )

    except Exception as e:
        logger.exception(f"Pipeline failed for image {image_id}: {e}")
        image_record.status = "failed"
        image_record.error_message = str(e)
        await db.flush()
