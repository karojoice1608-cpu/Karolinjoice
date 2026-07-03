
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, Index
from sqlalchemy.orm import relationship

from backend.database import Base


class Image(Base):
    __tablename__ = "images"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(512), nullable=False)
    original_filename = Column(String(512), nullable=False)
    file_path = Column(String(1024), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(64), nullable=False)
    width_px = Column(Integer, nullable=True)
    height_px = Column(Integer, nullable=True)

    # Image classification
    image_type = Column(String(32), nullable=True)  # "born_digital" | "scene_text" | "mixed"

    # Aggregated extraction results
    full_text = Column(Text, nullable=True)           # All extracted text concatenated
    keywords = Column(Text, nullable=True)   # JSON-serialised list of keywords
    avg_confidence = Column(Float, nullable=True)      # Mean OCR confidence across regions
    region_count = Column(Integer, default=0)          # Number of text regions detected

    # Processing state
    status = Column(String(32), default="pending")    # pending | processing | done | failed
    error_message = Column(Text, nullable=True)
    ocr_engine_used = Column(String(32), nullable=True)  # easyocr | tesseract | both

    # Semantic embedding stored as text-encoded vector (pgvector via raw SQL if extension present)
    # If pgvector is unavailable, this field is unused and keyword search serves as fallback
    embedding_json = Column(Text, nullable=True)  # JSON-serialised float list

    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    text_regions = relationship("TextRegion", back_populates="image", cascade="all, delete-orphan")

    # Full-text search index on full_text column
    __table_args__ = (
        Index("ix_images_status", "status"),
        Index("ix_images_uploaded_at", "uploaded_at"),
    )

    def __repr__(self):
        return f"<Image id={self.id} filename={self.original_filename} status={self.status}>"
