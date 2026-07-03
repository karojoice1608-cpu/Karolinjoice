"""
OCR & NLP Processing Service for Screendex.

Pipeline:
  Image → Pre-processing → Text Detection (CNN) → OCR Extraction →
  Text Cleaning → NLP (tokenization, stopwords, stemming) → Keywords
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import Counter

from PIL import Image as PILImage

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# NLTK setup (download once)
# ──────────────────────────────────────────────
def _ensure_nltk():
    import nltk
    for pkg in ["punkt", "punkt_tab", "stopwords", "wordnet", "averaged_perceptron_tagger"]:
        try:
            nltk.data.find(f"tokenizers/{pkg}")
        except LookupError:
            try:
                nltk.download(pkg, quiet=True)
            except Exception:
                pass


try:
    _ensure_nltk()
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    from nltk.stem import PorterStemmer
    NLTK_AVAILABLE = True
    STOPWORDS = set(stopwords.words("english"))
    STEMMER   = PorterStemmer()
except Exception:
    NLTK_AVAILABLE = False
    STOPWORDS = {
        "the","a","an","is","in","on","at","to","for","of","and","or","but","it",
        "as","by","be","was","are","with","this","that","from","have","has","had",
        "its","not","he","she","they","we","you","i","my","our","their","will",
        "can","do","did","been","would","could","should","may","might","shall",
    }
    STEMMER = None


# ──────────────────────────────────────────────
# EasyOCR reader (lazy singleton)
# ──────────────────────────────────────────────
_ocr_reader = None

def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            logger.info("EasyOCR reader initialized")
        except Exception as e:
            logger.warning(f"EasyOCR unavailable: {e}")
    return _ocr_reader


# ──────────────────────────────────────────────
# Image pre-processing helpers
# ──────────────────────────────────────────────
def preprocess_image(image_path: str) -> str:
    """
    Pre-process image for better OCR accuracy.
    Returns path to processed image (may be same path if opencv unavailable).
    """
    try:
        import cv2
        import numpy as np

        img = cv2.imread(image_path)
        if img is None:
            return image_path

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        # Adaptive threshold for better contrast
        thresh = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        # Save processed image to temp path
        processed_path = image_path.replace(".", "_processed.", 1)
        cv2.imwrite(processed_path, thresh)
        return processed_path

    except Exception as e:
        logger.debug(f"Pre-processing skipped: {e}")
        return image_path


# ──────────────────────────────────────────────
# Text cleaning
# ──────────────────────────────────────────────
def clean_text(raw_text: str) -> str:
    """Remove noise, normalize whitespace, strip non-printable chars."""
    if not raw_text:
        return ""
    # Remove non-printable characters except newlines
    text = re.sub(r"[^\x20-\x7E\n]", " ", raw_text)
    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ──────────────────────────────────────────────
# NLP keyword extraction
# ──────────────────────────────────────────────
def extract_keywords(text: str) -> List[Tuple[str, int, bool]]:
    """
    Extract keywords from text using NLP.
    Returns list of (keyword, frequency, is_stopword).
    """
    if not text:
        return []

    text_lower = text.lower()

    if NLTK_AVAILABLE:
        tokens = word_tokenize(text_lower)
    else:
        # Fallback: simple split + clean
        tokens = re.findall(r"\b[a-z][a-z0-9_\-]{1,49}\b", text_lower)

    # Count all tokens
    freq = Counter(tokens)
    keywords = []

    for token, count in freq.items():
        if len(token) < 2:
            continue
        if re.match(r"^\d+$", token):
            continue  # skip pure numbers

        is_stop = token in STOPWORDS
        # Apply stemming for non-stopwords
        if STEMMER and not is_stop:
            stem = STEMMER.stem(token)
            keywords.append((stem, count, False))
        keywords.append((token, count, is_stop))

    # Deduplicate
    seen = {}
    for kw, freq_val, is_stop in keywords:
        if kw not in seen:
            seen[kw] = (freq_val, is_stop)
        else:
            seen[kw] = (seen[kw][0] + freq_val, is_stop)

    return [(k, v[0], v[1]) for k, v in seen.items()]


# ──────────────────────────────────────────────
# Smart Categorization
# ──────────────────────────────────────────────
def classify_image_content(text: str, keywords: List[Tuple[str, int, bool]]) -> Tuple[str, float]:
    """
    Heuristic-based classification.
    Returns (category, confidence).
    """
    if not text:
        return "Unknown", 0.0

    text_lower = text.lower()
    kws = [k[0] for k in keywords if not k[2]] # non-stopwords

    # Category patterns
    patterns = {
        "Receipt": ["total", "amount", "tax", "date", "cashier", "order", "sum", "subtotal", "vat", "item", "qty"],
        "Code Snippet": ["def ", "class ", "import ", "public", "static", "void", "fn ", "const ", "let ", "var ", "return ", "if ", "else ", "{", "}"],
        "Document": ["agreement", "contract", "signature", "official", "subject", "dated", "terms", "conditions"],
        "Social Media": ["like", "comment", "share", "subscribe", "follow", "post", "retweet", "trending"],
        "Business Card": ["email", "phone", "website", "address", "company", "position", "tel", "mobile"],
        "Lecture Note": ["abstract", "introduction", "conclusion", "references", "theory", "hypothesis", "analysis"],
    }

    scores = Counter()
    for cat, words in patterns.items():
        for word in words:
            if word in text_lower:
                scores[cat] += 1
            # Check keywords as well
            if word in kws:
                scores[cat] += 2

    if not scores:
        return "Other", 0.3

    best_cat, count = scores.most_common(1)[0]
    # Simple confidence calculation
    confidence = min(0.4 + (count * 0.1), 0.95)

    return best_cat, confidence


# ──────────────────────────────────────────────
# Smart Summarization
# ──────────────────────────────────────────────
def summarize_content(text: str, keywords: List[Tuple[str, int, bool]]) -> Tuple[str, float]:
    """
    Generate a 1-line summary of the image text based on keyword frequencies.
    Returns (summary_text, confidence_score).
    """
    if not text:
        return "", 0.0
    
    # Simple extractive summarizer: score sentences by their keywords
    try:
        from nltk.tokenize import sent_tokenize
        sentences = sent_tokenize(text)
    except Exception:
        # Fallback if punkt is missing
        sentences = [s.strip() for s in text.replace('\n', '. ').split('.') if len(s.strip()) > 5]
        
    if not sentences:
        # If no sentences found, just return first slice
        return text[:100] + ("..." if len(text) > 100 else ""), 0.5
        
    keyword_scores = {kw: count for kw, count, is_stop in keywords if not is_stop}
    
    best_sentence = ""
    best_score = -1
    
    for sent in sentences:
        sent_lower = sent.lower()
        score = sum(keyword_scores.get(w, 0) for w in sent_lower.split())
        
        words = sent_lower.split()
        if len(words) > 0:
             norm_score = score / len(words)
        else:
             norm_score = 0
             
        # Add slight bias to first few sentences
        if best_sentence == "":
             norm_score += 0.5 
             
        if norm_score > best_score and len(words) >= 3:
            best_score = norm_score
            best_sentence = sent
            
    if not best_sentence:
        best_sentence = sentences[0]
        
    summary = best_sentence.replace('\n', ' ').strip()
    if len(summary) > 250:
        summary = summary[:247] + "..."
        
    conf = min(0.3 + (best_score * 0.1), 0.95)
    return summary, conf


# ──────────────────────────────────────────────
# Core OCR extraction
# ──────────────────────────────────────────────
def extract_text_from_image(image_path: str) -> List[Dict]:
    """
    Extract text regions from an image using EasyOCR.

    Returns list of dicts:
      {
        text        : str,
        confidence  : float,   # 0.0–1.0
        bbox        : {x, y, width, height},  # relative 0–1
      }
    """
    results = []

    # Get image dimensions for relative bbox calculation
    try:
        with PILImage.open(image_path) as img:
            img_w, img_h = img.size
    except Exception:
        img_w, img_h = 1, 1

    # Try EasyOCR
    reader = _get_ocr_reader()
    if reader:
        try:
            raw = reader.readtext(image_path, detail=1, paragraph=False)
            for (bbox_pts, text, conf) in raw:
                text = clean_text(text)
                if not text or conf < 0.3:
                    continue

                # bbox_pts is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                xs = [p[0] for p in bbox_pts]
                ys = [p[1] for p in bbox_pts]
                x, y  = min(xs), min(ys)
                w, h  = max(xs) - x, max(ys) - y

                results.append({
                    "text":       text,
                    "confidence": float(conf),
                    "bbox": {
                        "x":      round(x / img_w, 4),
                        "y":      round(y / img_h, 4),
                        "width":  round(w / img_w, 4),
                        "height": round(h / img_h, 4),
                    }
                })
            logger.info(f"EasyOCR extracted {len(results)} text regions from {image_path}")
            return results
        except Exception as e:
            logger.warning(f"EasyOCR failed: {e}")

    # Fallback: Tesseract via pytesseract
    try:
        import pytesseract
        text = pytesseract.image_to_string(PILImage.open(image_path))
        text = clean_text(text)
        if text:
            results.append({
                "text":       text,
                "confidence": 0.75,
                "bbox":       {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
            })
        logger.info(f"Tesseract fallback extracted text from {image_path}")
        return results
    except Exception as e:
        logger.warning(f"Tesseract fallback failed: {e}")

    # Last resort: return empty (image might be non-text)
    logger.warning(f"No OCR engine available; returning empty for {image_path}")
    return []


# ──────────────────────────────────────────────
# Image dimension helper
# ──────────────────────────────────────────────
def get_image_dimensions(image_path: str) -> Tuple[int, int]:
    """Return (width, height) of image."""
    try:
        with PILImage.open(image_path) as img:
            return img.size
    except Exception:
        return (0, 0)


# ──────────────────────────────────────────────
# Thumbnail generator
# ──────────────────────────────────────────────
def generate_thumbnail(image_path: str, thumb_path: str, size: Tuple[int, int] = (300, 300)) -> bool:
    """Generate a thumbnail image. Returns True on success."""
    try:
        with PILImage.open(image_path) as img:
            img.thumbnail(size, PILImage.LANCZOS)
            thumb_dir = os.path.dirname(thumb_path)
            os.makedirs(thumb_dir, exist_ok=True)
            img.save(thumb_path)
        return True
    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")
        return False
