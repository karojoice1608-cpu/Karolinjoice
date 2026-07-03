"""
Semantic Search Service for Screendex.
Manages SentenceTransformer embedding model and NumPy vector index.
"""

import os
import atexit
import logging
import numpy as np
import pickle
from typing import List, Tuple

try:
    from sentence_transformers import SentenceTransformer
    HAS_SEMANTIC = True
except ImportError:
    HAS_SEMANTIC = False

logger = logging.getLogger(__name__)

# Constants
INDEX_FILE = "semantic_index.pkl"
MODEL_NAME = "all-MiniLM-L6-v2"  # Fast, lightweight model
EMBEDDING_DIM = 384             # all-MiniLM-L6-v2 produces 384-dimensional embeddings

class SemanticService:
    def __init__(self):
        self.model = None
        self.embeddings = {}
        if HAS_SEMANTIC:
            self._initialize()

    def _initialize(self):
        try:
            logger.info(f"Loading SentenceTransformer model: {MODEL_NAME}")
            self.model = SentenceTransformer(MODEL_NAME)
            
            # Load embeddings dictionary
            if os.path.exists(INDEX_FILE):
                with open(INDEX_FILE, 'rb') as f:
                    self.embeddings = pickle.load(f)
                logger.info(f"Loading Numpy embeddings from {INDEX_FILE} (found {len(self.embeddings)})")
            else:
                logger.info("Creating new Numpy embeddings dict")
                
            # Register save on exit
            atexit.register(self.save_index)
        except Exception as e:
            logger.error(f"Failed to initialize SemanticService: {e}")
            self.model = None

    def add_to_index(self, image_id: int, text: str) -> bool:
        """Generate embedding for text and add to memory mapping."""
        if not self.model or not text.strip():
            return False

        try:
            # Generate embedding
            emb = self.model.encode([text])[0]
            # Normalize for cosine similarity
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            
            self.embeddings[image_id] = emb
            logger.info(f"Added Image {image_id} to semantic index.")
            return True
        except Exception as e:
            logger.error(f"Failed to add Image {image_id} to semantic index: {e}")
            return False

    def search(self, query: str, top_k: int = 20) -> List[Tuple[int, float]]:
        """
        Search for query in the index via cosine similarity dot product.
        Returns a list of tuples: (image_id, similarity_score).
        Similarity score is Cosine Similarity (-1.0 to 1.0)
        """
        if not self.model or not self.embeddings or not query.strip():
            return []

        try:
            # Generate and normalize embedding
            q_emb = self.model.encode([query])[0]
            norm = np.linalg.norm(q_emb)
            if norm > 0:
                q_emb = q_emb / norm
            
            results = []
            for img_id, emb in self.embeddings.items():
                score = float(np.dot(q_emb, emb))
                results.append((img_id, score))
                    
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def save_index(self):
        """Save index to disk."""
        if getattr(self, "embeddings", None) is not None:
            try:
                with open(INDEX_FILE, 'wb') as f:
                    pickle.dump(self.embeddings, f)
                logger.debug(f"Saved {len(self.embeddings)} embeddings to {INDEX_FILE}")
            except Exception as e:
                logger.error(f"Failed to save Numpy index: {e}")

# Global singleton
semantic_service = SemanticService()
