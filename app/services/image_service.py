"""
Image Processing Service for Screendex.
Orchestrates: Upload → Pre-process → OCR → NLP → DB Index
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.models import Image, ExtractedText, Keyword, ProcessingStatusEnum, ImageTypeEnum
from app.services.ocr_service import (
    extract_text_from_image,
    extract_keywords,
    get_image_dimensions,
    generate_thumbnail,
    preprocess_image,
    clean_text,
    classify_image_content,
    summarize_content,
)
from app.services.semantic_service import semantic_service
import hashlib
import cv2
import numpy as np
import joblib

try:
    import imagehash
    from PIL import Image as PILImage
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "static/uploads")
THUMB_DIR  = os.path.join(UPLOAD_DIR, "thumbnails")

# ── Load the trained model ───────────────────────────────────────────────────
MODEL_PATH = 'image_classifier.joblib'
MODEL = None
if os.path.exists(MODEL_PATH):
    try:
        MODEL = joblib.load(MODEL_PATH)
        logger.info(f"Successfully loaded image classifier model from {MODEL_PATH}")
    except Exception as e:
        logger.error(f"Failed to load model from {MODEL_PATH}: {e}")
else:
    logger.warning(f"Image classifier model not found at {MODEL_PATH}. Falling back to heuristic method.")
# ─────────────────────────────────────────────────────────────────────────────


def _extract_features(image_path: str) -> Optional[list]:
    """
    Extracts features from an image file for model prediction.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        total_pixels = gray.shape[0] * gray.shape[1]
        
        # 1. Laplacian variance
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_var = laplacian.var()
        
        # 2. Color diversity
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
        significant_threshold = total_pixels * 0.001
        unique_colors = int(np.sum(hist > significant_threshold))
        
        # 3. Max single color dominance
        max_color_pct = (np.max(hist) / total_pixels) * 100
        
        return [laplacian_var, unique_colors, max_color_pct]
    except Exception as e:
        logger.error(f"Feature extraction failed for {image_path}: {e}")
        return None


def process_image(db: Session, image_id: int) -> bool:
    """
    Full processing pipeline for a single image.
    Called after upload; can be run synchronously or via background task.

    Steps:
      1. Load image record from DB
      2. Pre-process image (denoise, threshold)
      3. Extract text regions via OCR
      4. Save ExtractedText rows
      5. Extract keywords via NLP
      6. Save Keyword rows
      7. Generate thumbnail
      8. Update status
    """
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        logger.error(f"Image {image_id} not found in DB")
        return False

    image.status = ProcessingStatusEnum.processing
    db.commit()

    try:
        # ── Step 0: Hashes & Duplicates ────────────
        calculate_and_check_hashes(db, image)

        # ── Step 1: Pre-process image ──────────────
        processed_path = preprocess_image(image.file_path)

        # ── Step 2: OCR extraction ─────────────────
        text_regions = extract_text_from_image(image.file_path)  # use original for accuracy
        logger.info(f"[Image {image_id}] OCR found {len(text_regions)} text regions")

        if not text_regions:
            # Try on pre-processed version
            text_regions = extract_text_from_image(processed_path)

        # ── Step 3: Save extracted text to DB ─────
        all_text_parts = []
        for order, region in enumerate(text_regions):
            text_content = region["text"]
            all_text_parts.append(text_content)

            et = ExtractedText(
                image_id     = image_id,
                text_content = text_content,
                confidence   = region["confidence"],
                bbox_x       = region["bbox"]["x"],
                bbox_y       = region["bbox"]["y"],
                bbox_width   = region["bbox"]["width"],
                bbox_height  = region["bbox"]["height"],
                text_order   = order,
            )
            db.add(et)

        db.flush()

        # ── Step 4: NLP keyword extraction ────────
        full_text = " ".join(all_text_parts)
        keywords  = extract_keywords(full_text)
        logger.info(f"[Image {image_id}] NLP extracted {len(keywords)} keywords")

        for kw, freq, is_stop in keywords:
            k = Keyword(
                image_id   = image_id,
                keyword    = kw,
                frequency  = freq,
                is_stopword= is_stop,
            )
            db.add(k)

        db.flush()

        # ── Step 5: Thumbnail ──────────────────────
        thumb_filename = f"thumb_{image.filename}"
        thumb_path     = os.path.join(THUMB_DIR, thumb_filename)
        os.makedirs(THUMB_DIR, exist_ok=True)
        success = generate_thumbnail(image.file_path, thumb_path)
        if success:
            image.thumbnail_path = thumb_path

        # ── Step 6: Image dimensions ───────────────
        w, h = get_image_dimensions(image.file_path)
        image.width  = w
        image.height = h

        # ── Step 7: Classification & Summarization ───────────
        category, confidence = classify_image_content(full_text, keywords)
        image.category      = category
        image.category_conf = confidence
        logger.info(f"[Image {image_id}] Categorized as {category} ({confidence:.2f})")
        
        subject, subj_conf = summarize_content(full_text, keywords)
        image.subject      = subject
        image.subject_conf = subj_conf
        logger.info(f"[Image {image_id}] Summarized subject extracted")

        # ── Step 8: Consolidated Search Index ─────
        # Filter out stopwords and join into a single key
        search_words = [kw for kw, freq, is_stop in keywords if not is_stop]
        index_key    = " ".join(search_words)
        
        from app.models.models import ImageSearchIndex
        idx = db.query(ImageSearchIndex).filter(ImageSearchIndex.image_id == image_id).first()
        if not idx:
            idx = ImageSearchIndex(image_id=image_id)
            db.add(idx)
        
        idx.index_key  = index_key
        idx.word_count = len(search_words)
        idx.indexed_at = datetime.utcnow()

        # ── Step 8a: Semantic Indexing ───────────
        try:
            semantic_service.add_to_index(image_id, full_text)
        except Exception as sem_e:
            logger.warning(f"[Image {image_id}] Failed to semantically index: {sem_e}")

        # ── Step 9: Duplicates ───────────────────
        # (Already handled in calculate_hashes but let's re-verify)
        if image.is_duplicate:
            logger.info(f"[Image {image_id}] Marked as duplicate of Image {image.original_id}")

        # ── Step 10: Update status ──────────────────
        image.status       = ProcessingStatusEnum.completed
        image.processed_at = datetime.utcnow()
        db.commit()

        # Cleanup processed file if different
        if processed_path != image.file_path and os.path.exists(processed_path):
            os.remove(processed_path)

        logger.info(f"[Image {image_id}] Processing completed successfully")
        return True

    except Exception as e:
        logger.error(f"[Image {image_id}] Processing failed: {e}", exc_info=True)
        image.status        = ProcessingStatusEnum.failed
        image.error_message = str(e)
        db.commit()
        return False


def save_uploaded_file(file_data: bytes, original_filename: str) -> Tuple[str, str]:
    """
    Save uploaded file bytes to disk.
    Returns (absolute_path, unique_filename).
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    ext      = os.path.splitext(original_filename)[1].lower()
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(file_data)

    return os.path.abspath(filepath), filename


def detect_image_type(file_path: str, filename: str) -> ImageTypeEnum:
    """
    Intelligently detect Born-Digital vs Scene Text.
    Uses a trained classifier if available, otherwise falls back to heuristics.
    """
    # --- MODEL-BASED CLASSIFICATION -----------------------------------------
    if MODEL:
        features = _extract_features(file_path)
        if features:
            try:
                # Model expects a 2D array
                features_2d = np.array(features).reshape(1, -1)
                prediction = MODEL.predict(features_2d)[0]
                
                if prediction == 0:
                    logger.info(f"Model classified '{filename}' as Born-Digital.")
                    return ImageTypeEnum.born_digital
                else:
                    logger.info(f"Model classified '{filename}' as Scene Text.")
                    return ImageTypeEnum.scene_text
            except Exception as e:
                logger.error(f"Model prediction failed for '{filename}', falling back to heuristics: {e}")
    
    # --- HEURISTIC-BASED FALLBACK -------------------------------------------
    logger.warning(f"Using heuristic classification for '{filename}'.")
    name_lower = filename.lower()
    digital_hints = ["screenshot", "screen", "capture", "snap", "whatsapp", "img_", "photo_"]
    
    try:
        img = cv2.imread(file_path)
        if img is None:
            raise ValueError("Unreadable image")
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        total_pixels = gray.shape[0] * gray.shape[1]
        
        # Metric 1 (PRIMARY): Laplacian variance
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_var = laplacian.var()
        
        # Metric 2: Color diversity
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
        significant_threshold = total_pixels * 0.001
        unique_colors = int(np.sum(hist > significant_threshold))
        
        # Metric 3: Max single color dominance
        max_color_pct = (np.max(hist) / total_pixels) * 100
        
        logging.info(
            f"CV classify '{filename}': laplacian_var={laplacian_var:.1f}, "
            f"max_color={max_color_pct:.1f}%, unique_colors={unique_colors}/256"
        )
        
        if laplacian_var > 100:
            return ImageTypeEnum.scene_text
        elif laplacian_var < 30 and unique_colors < 120:
            return ImageTypeEnum.born_digital
        elif laplacian_var < 50 and max_color_pct > 25.0:
            return ImageTypeEnum.born_digital
        elif unique_colors >= 200:
            return ImageTypeEnum.scene_text
        else:
            score = 0
            score += min(laplacian_var / 2, 40)
            score += min(unique_colors / 5, 30)
            score -= min(max_color_pct, 30)
            
            if score > 30:
                return ImageTypeEnum.scene_text
            else:
                return ImageTypeEnum.born_digital
            
    except Exception as e:
        logging.warning(f"Heuristic classification failed for {filename}, falling back: {e}")
        if any(hint in name_lower for hint in digital_hints):
            return ImageTypeEnum.born_digital
        return ImageTypeEnum.scene_text


def calculate_and_check_hashes(db: Session, image: Image):
    """Calculate file hash and phash, and check for duplicates."""
    try:
        # File Hash (exact match)
        with open(image.file_path, "rb") as f:
            file_bytes = f.read()
            image.file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Perceptual Hash (similar match)
        if HAS_IMAGEHASH:
            with PILImage.open(image.file_path) as img:
                image.phash = str(imagehash.average_hash(img))

        # Check for duplicates
        # 1. Exact match
        duplicate = db.query(Image).filter(
            Image.file_hash == image.file_hash,
            Image.id != image.id
        ).first()

        if duplicate:
            image.is_duplicate = True
            image.original_id  = duplicate.id
            return

        # 2. Similar match (using phash)
        if image.phash:
            similar = db.query(Image).filter(
                Image.phash == image.phash,
                Image.id != image.id
            ).first()
            if similar:
                image.is_duplicate = True
                image.original_id  = similar.id

    except Exception as e:
        logger.warning(f"Hash calculation failed for Image {image.id}: {e}")
