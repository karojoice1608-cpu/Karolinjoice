"""
OCR Service
────────────
Primary engine: EasyOCR  (deep learning, handles complex fonts and orientations)
Fallback engine: Tesseract (deterministic, fast, well-understood failure modes)

Strategy:
1. Try EasyOCR on the image/region.
2. If EasyOCR returns no results OR average confidence < threshold, fall back to Tesseract.
3. Return results from whichever engine produced the higher average confidence.

[Inference] This fallback strategy is expected to improve recall on edge cases
where one engine fails. Actual comparative accuracy depends on image characteristics
and model versions.
"""

import logging
from typing import Optional

import cv2
import numpy as np

from backend.config import settings

logger = logging.getLogger(__name__)

# ─── Lazy singletons ─────────────────────────────────────────────────────────

_easyocr_reader = None
_tesseract_available = False


def _get_easyocr():
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            _easyocr_reader = easyocr.Reader(
                settings.easyocr_language_list,
                gpu=False,  # Set True if CUDA available
                verbose=False,
            )
            logger.info("EasyOCR reader initialised")
        except ImportError:
            logger.warning("EasyOCR not installed — will use Tesseract only")
    return _easyocr_reader


def _check_tesseract():
    global _tesseract_available
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        _tesseract_available = True
        logger.info("Tesseract available")
    except Exception as e:
        logger.warning(f"Tesseract not available: {e}")
    return _tesseract_available


# ─── Result type ──────────────────────────────────────────────────────────────

def _make_result(text: str, confidence: float, engine: str,
                 bbox: Optional[dict] = None) -> dict:
    return {
        "text": text.strip(),
        "confidence": round(float(confidence), 4),
        "engine": engine,
        "bbox": bbox,  # {"x", "y", "w", "h"} or None (full-image result)
    }


# ─── EasyOCR ──────────────────────────────────────────────────────────────────

def _run_easyocr(image_bgr: np.ndarray) -> list[dict]:
    reader = _get_easyocr()
    if reader is None:
        return []

    try:
        # EasyOCR expects RGB
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        raw_results = reader.readtext(image_rgb, detail=1, paragraph=False)

        results = []
        for (bbox_pts, text, conf) in raw_results:
            if not text.strip():
                continue
            # bbox_pts is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            xs = [int(p[0]) for p in bbox_pts]
            ys = [int(p[1]) for p in bbox_pts]
            x, y = min(xs), min(ys)
            w, h = max(xs) - x, max(ys) - y
            results.append(_make_result(text, conf, "easyocr",
                                        {"x": x, "y": y, "w": w, "h": h}))
        return results
    except Exception as e:
        logger.error(f"EasyOCR failed: {e}")
        return []


# ─── Tesseract ────────────────────────────────────────────────────────────────

def _run_tesseract(image_bgr: np.ndarray) -> list[dict]:
    if not _tesseract_available and not _check_tesseract():
        return []

    try:
        import pytesseract
        from PIL import Image as PILImage

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        pil_image = PILImage.fromarray(image_rgb)

        data = pytesseract.image_to_data(
            pil_image,
            output_type=pytesseract.Output.DICT,
            config="--psm 11",  # PSM 11: sparse text — finds text anywhere
        )

        results = []
        n_boxes = len(data["level"])
        for i in range(n_boxes):
            text = str(data["text"][i]).strip()
            conf_raw = int(data["conf"][i])
            if not text or conf_raw < 0:
                continue
            conf = conf_raw / 100.0  # Tesseract returns 0–100
            x = int(data["left"][i])
            y = int(data["top"][i])
            w = int(data["width"][i])
            h = int(data["height"][i])
            results.append(_make_result(text, conf, "tesseract",
                                        {"x": x, "y": y, "w": w, "h": h}))
        return results
    except Exception as e:
        logger.error(f"Tesseract failed: {e}")
        return []


# ─── Public interface ─────────────────────────────────────────────────────────

def _avg_confidence(results: list[dict]) -> float:
    if not results:
        return 0.0
    return sum(r["confidence"] for r in results) / len(results)


def run_ocr(image_bgr: np.ndarray, engine: str = "both") -> tuple[list[dict], str]:
    """
    Run OCR on a BGR numpy array.

    Args:
        image_bgr: Input image as BGR numpy array.
        engine: "easyocr" | "tesseract" | "both"

    Returns:
        (results, engine_used)
        results: list of OCR result dicts
        engine_used: which engine produced the final results
    """
    threshold = settings.ocr_confidence_threshold

    if engine == "easyocr":
        results = _run_easyocr(image_bgr)
        return results, "easyocr"

    if engine == "tesseract":
        results = _run_tesseract(image_bgr)
        return results, "tesseract"

    # engine == "both": try EasyOCR first, fallback to Tesseract
    easy_results = _run_easyocr(image_bgr)
    easy_avg = _avg_confidence(easy_results)

    if easy_results and easy_avg >= threshold:
        logger.debug(f"EasyOCR accepted (avg conf={easy_avg:.2f})")
        return easy_results, "easyocr"

    logger.debug(f"EasyOCR insufficient (avg conf={easy_avg:.2f}), trying Tesseract")
    tess_results = _run_tesseract(image_bgr)
    tess_avg = _avg_confidence(tess_results)

    # Return whichever produced higher average confidence
    if tess_avg >= easy_avg:
        logger.debug(f"Tesseract selected (avg conf={tess_avg:.2f})")
        return tess_results, "tesseract"

    logger.debug(f"EasyOCR selected despite low confidence (easy={easy_avg:.2f} > tess={tess_avg:.2f})")
    return easy_results, "easyocr"


def run_ocr_on_region(image_bgr: np.ndarray, bbox: dict, engine: str = "both") -> tuple[list[dict], str]:
    """
    Crop image to bbox and run OCR on that region only.
    Adjusts result bounding boxes back to original image coordinates.
    """
    x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
    crop = image_bgr[y:y+h, x:x+w]
    if crop.size == 0:
        return [], engine

    results, engine_used = run_ocr(crop, engine)

    # Shift bbox coordinates to original image space
    for r in results:
        if r["bbox"]:
            r["bbox"]["x"] += x
            r["bbox"]["y"] += y

    return results, engine_used
