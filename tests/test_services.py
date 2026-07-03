"""
Tests for NLP and OCR utility functions.
Run with: pytest tests/ -v
"""

import pytest
import numpy as np


# ─── NLP Service Tests ────────────────────────────────────────────────────────

class TestCleanText:
    def test_basic_cleaning(self):
        from backend.services.nlp_service import clean_text
        assert clean_text("  hello   world  ") == "hello world"

    def test_noise_removal(self):
        from backend.services.nlp_service import clean_text
        result = clean_text("Python | error | :")
        assert "|" not in result
        assert "Python" in result

    def test_empty_string(self):
        from backend.services.nlp_service import clean_text
        assert clean_text("") == ""
        assert clean_text(None) == ""

    def test_unicode_normalisation(self):
        from backend.services.nlp_service import clean_text
        assert clean_text("caf\u0065\u0301") == "café"


class TestExtractKeywords:
    def test_returns_list(self):
        from backend.services.nlp_service import extract_keywords
        result = extract_keywords("Python machine learning neural network")
        assert isinstance(result, list)

    def test_removes_stopwords(self):
        from backend.services.nlp_service import extract_keywords
        result = extract_keywords("the quick brown fox")
        assert "the" not in result

    def test_min_length_filter(self):
        from backend.services.nlp_service import extract_keywords
        result = extract_keywords("an of it Python")
        assert "an" not in result
        assert "of" not in result
        assert "python" in result

    def test_empty_text(self):
        from backend.services.nlp_service import extract_keywords
        assert extract_keywords("") == []
        assert extract_keywords(None) == []

    def test_max_keywords_respected(self):
        from backend.services.nlp_service import extract_keywords
        long_text = " ".join([f"word{i}" for i in range(100)])
        result = extract_keywords(long_text, max_keywords=10)
        assert len(result) <= 10


class TestClassifyImageType:
    def test_high_confidence_born_digital(self):
        from backend.services.nlp_service import classify_image_type
        results = [{"confidence": 0.95}, {"confidence": 0.97}, {"confidence": 0.93}]
        assert classify_image_type(results) == "born_digital"

    def test_low_confidence_scene_text(self):
        from backend.services.nlp_service import classify_image_type
        results = [{"confidence": 0.45}, {"confidence": 0.55}, {"confidence": 0.35}]
        assert classify_image_type(results) == "scene_text"

    def test_empty_results(self):
        from backend.services.nlp_service import classify_image_type
        assert classify_image_type([]) == "unknown"


class TestAssignReadingOrder:
    def test_top_to_bottom_ordering(self):
        from backend.services.nlp_service import assign_reading_order
        regions = [
            {"x": 0, "y": 100, "w": 100, "h": 20},
            {"x": 0, "y": 10,  "w": 100, "h": 20},
            {"x": 0, "y": 50,  "w": 100, "h": 20},
        ]
        result = assign_reading_order(regions)
        # Sort the mutated region dicts by reading_order and verify y is ascending
        sorted_by_order = sorted(result, key=lambda r: r["reading_order"])
        y_values = [r["y"] for r in sorted_by_order]
        assert y_values == sorted(y_values), f"Expected ascending y, got {y_values}"

    def test_empty_regions(self):
        from backend.services.nlp_service import assign_reading_order
        assert assign_reading_order([]) == []


# ─── Embedding Service Tests ──────────────────────────────────────────────────

class TestEmbeddingService:
    def test_cosine_similarity_identical(self):
        from backend.services.embedding_service import cosine_similarity
        v = [1.0, 0.0, 0.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        from backend.services.embedding_service import cosine_similarity
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(cosine_similarity(a, b)) < 1e-6

    def test_cosine_similarity_mismatched_length(self):
        from backend.services.embedding_service import cosine_similarity
        assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0

    def test_embedding_json_round_trip(self):
        from backend.services.embedding_service import embedding_to_json, embedding_from_json
        original = [0.1, 0.2, 0.3, -0.4, 0.5]
        json_str = embedding_to_json(original)
        recovered = embedding_from_json(json_str)
        assert recovered is not None
        assert all(abs(a - b) < 1e-9 for a, b in zip(original, recovered))

    def test_embedding_from_invalid_json(self):
        from backend.services.embedding_service import embedding_from_json
        assert embedding_from_json("not-json") is None
        assert embedding_from_json("") is None
        assert embedding_from_json(None) is None


# ─── OCR Service Unit Tests ───────────────────────────────────────────────────

class TestOCRServiceHelpers:
    def test_avg_confidence_empty(self):
        from backend.services.ocr_service import _avg_confidence
        assert _avg_confidence([]) == 0.0

    def test_avg_confidence_calculation(self):
        from backend.services.ocr_service import _avg_confidence
        results = [{"confidence": 0.8}, {"confidence": 0.9}, {"confidence": 0.7}]
        avg = _avg_confidence(results)
        assert abs(avg - 0.8) < 1e-9

    def test_make_result_structure(self):
        from backend.services.ocr_service import _make_result
        r = _make_result("Hello", 0.95, "easyocr", {"x": 10, "y": 20, "w": 100, "h": 30})
        assert r["text"] == "Hello"
        assert r["confidence"] == 0.95
        assert r["engine"] == "easyocr"
        assert r["bbox"]["x"] == 10
