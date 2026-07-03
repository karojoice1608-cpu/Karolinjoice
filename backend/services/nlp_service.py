"""
NLP / Text Cleaning Service
────────────────────────────
Responsibilities:
1. Clean raw OCR output (normalise whitespace, strip noise characters).
2. Classify image type (Born-Digital vs Scene Text) based on confidence distribution.
3. Extract meaningful keywords using NLTK (stopword removal + frequency ranking).
4. Assign reading order to text regions (top-to-bottom, left-to-right).
"""

import re
import logging
import unicodedata
from collections import Counter

logger = logging.getLogger(__name__)

# ─── NLTK setup (lazy) ────────────────────────────────────────────────────────

_nltk_ready = False


def _ensure_nltk():
    global _nltk_ready
    if _nltk_ready:
        return
    try:
        import nltk
        for pkg in ("stopwords", "punkt", "punkt_tab"):
            try:
                nltk.data.find(f"tokenizers/{pkg}" if pkg.startswith("punkt") else f"corpora/{pkg}")
            except LookupError:
                nltk.download(pkg, quiet=True)
        _nltk_ready = True
    except ImportError:
        logger.warning("NLTK not available — keyword extraction will use simple tokenisation")


# ─── Text cleaning ────────────────────────────────────────────────────────────

# Characters that are almost certainly OCR noise when appearing in isolation
_NOISE_PATTERN = re.compile(r"^[^\w\s]{1,2}$")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_NON_PRINTABLE = re.compile(r"[^\x20-\x7E\u00A0-\uFFFF]")


def clean_text(raw: str) -> str:
    """
    Normalise raw OCR output into clean text suitable for indexing.

    Steps:
    1. Unicode normalisation (NFC).
    2. Remove non-printable control characters.
    3. Collapse multiple whitespace to single space.
    4. Strip leading/trailing whitespace.
    5. Filter out pure-noise tokens (single punctuation symbols isolated by spaces).
    """
    if not raw:
        return ""

    text = unicodedata.normalize("NFC", raw)
    text = _NON_PRINTABLE.sub(" ", text)
    text = _WHITESPACE_PATTERN.sub(" ", text)
    text = text.strip()

    # Token-level noise filter
    tokens = text.split()
    filtered = [t for t in tokens if not _NOISE_PATTERN.match(t)]
    return " ".join(filtered)


# ─── Keyword extraction ───────────────────────────────────────────────────────

def extract_keywords(text: str, max_keywords: int = 30) -> list[str]:
    """
    Extract meaningful keywords from cleaned text.

    Strategy:
    1. Lowercase and tokenise.
    2. Remove NLTK English stopwords (fallback: simple list).
    3. Remove tokens shorter than 3 characters.
    4. Rank by frequency and return top `max_keywords`.

    Returns a deduplicated list of lowercase keyword strings.
    """
    if not text:
        return []

    _ensure_nltk()

    try:
        from nltk.tokenize import word_tokenize
        from nltk.corpus import stopwords
        tokens = word_tokenize(text.lower())
        stop_words = set(stopwords.words("english"))
    except Exception:
        # Fallback: simple split
        tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
        stop_words = _SIMPLE_STOPWORDS

    # Filter: alpha-numeric only, length >= 3, not a stopword
    meaningful = [
        t for t in tokens
        if re.match(r"^[a-z0-9][a-z0-9_\-]*$", t)
        and len(t) >= 3
        and t not in stop_words
    ]

    # Rank by frequency
    freq = Counter(meaningful)
    ranked = [word for word, _ in freq.most_common(max_keywords)]
    return ranked


# ─── Image type classification ────────────────────────────────────────────────

def classify_image_type(ocr_results: list[dict]) -> str:
    """
    Classify image as 'born_digital', 'scene_text', or 'mixed' based on
    the distribution of OCR confidence scores.

    [Inference] Born-Digital images typically yield higher, tighter confidence
    clusters. Scene Text images tend to show more variance and lower mean confidence.
    Thresholds are heuristic and may require tuning per deployment.
    """
    if not ocr_results:
        return "unknown"

    confidences = [r["confidence"] for r in ocr_results if r.get("confidence") is not None]
    if not confidences:
        return "unknown"

    avg = sum(confidences) / len(confidences)
    variance = sum((c - avg) ** 2 for c in confidences) / len(confidences)

    if avg >= 0.80 and variance < 0.02:
        return "born_digital"
    elif avg < 0.60 or variance >= 0.05:
        return "scene_text"
    else:
        return "mixed"


# ─── Reading order ────────────────────────────────────────────────────────────

def assign_reading_order(regions: list[dict]) -> list[dict]:
    """
    Sort text regions in natural reading order: top-to-bottom, left-to-right.
    Regions within the same horizontal band (similar y) are sorted left-to-right.

    Adds a 'reading_order' integer to each region dict.
    """
    if not regions:
        return regions

    # Determine band height as ~50% of median region height
    heights = [r.get("h", 20) for r in regions]
    heights.sort()
    median_h = heights[len(heights) // 2]
    band_tolerance = max(10, int(median_h * 0.5))

    def sort_key(r):
        y = r.get("y", 0)
        x = r.get("x", 0)
        band = round(y / band_tolerance)
        return (band, x)

    sorted_regions = sorted(regions, key=sort_key)
    for i, r in enumerate(sorted_regions):
        r["reading_order"] = i

    return sorted_regions


# ─── Simple stopword fallback (no NLTK) ─────────────────────────────────────

_SIMPLE_STOPWORDS = {
    "the", "and", "for", "are", "was", "that", "this", "with", "you", "have",
    "from", "they", "will", "been", "has", "not", "but", "what", "all", "were",
    "when", "your", "can", "said", "there", "use", "each", "which", "she", "how",
    "their", "its", "also", "than", "then", "may", "any", "more", "about", "out",
    "into", "just", "like", "him", "such", "could", "would", "should", "these",
    "other", "some", "time", "our", "very", "per", "now", "two", "one", "had",
}
