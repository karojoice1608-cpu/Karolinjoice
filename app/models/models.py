"""
Database models for Screendex.

Tables:
  - images        : stores uploaded image metadata
  - extracted_texts: stores OCR-extracted text blocks per image
  - keywords      : normalized keyword index for fast search
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime,
    Boolean, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class User(Base):
    __tablename__ = "users"
    
    id             = Column(Integer, primary_key=True, index=True)
    username       = Column(String(255), unique=True, index=True, nullable=False)
    email          = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password= Column(String(255), nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)

    # Relationships
    images         = relationship("Image", back_populates="owner", cascade="all, delete-orphan")


class ImageTypeEnum(str, enum.Enum):
    born_digital = "born_digital"   # screenshots, digital receipts, WhatsApp
    scene_text   = "scene_text"     # photos of signboards, physical docs


class ProcessingStatusEnum(str, enum.Enum):
    pending    = "pending"
    processing = "processing"
    completed  = "completed"
    failed     = "failed"


class Image(Base):
    __tablename__ = "images"

    id              = Column(Integer, primary_key=True, index=True)
    filename        = Column(String(255), nullable=False)
    original_name   = Column(String(255), nullable=False)
    file_path       = Column(String(500), nullable=False)
    file_size       = Column(Integer)
    image_type      = Column(SAEnum(ImageTypeEnum), default=ImageTypeEnum.born_digital)
    width           = Column(Integer)
    height          = Column(Integer)
    status          = Column(SAEnum(ProcessingStatusEnum), default=ProcessingStatusEnum.pending)
    uploaded_at     = Column(DateTime, default=datetime.utcnow)
    processed_at    = Column(DateTime, nullable=True)
    error_message   = Column(Text, nullable=True)
    thumbnail_path  = Column(String(500), nullable=True)
    
    # Organization & Management Features
    category        = Column(String(100), nullable=True)   # Receipt, Document, Code, etc.
    category_conf   = Column(Float, default=0.0)
    file_hash       = Column(String(64), index=True)       # SHA256 for exact duplicates
    phash           = Column(String(64), index=True)       # Perceptual hash for similar images
    is_duplicate    = Column(Boolean, default=False)
    original_id     = Column(Integer, ForeignKey("images.id"), nullable=True) # Link to original if duplicate

    # AI Summarization
    subject         = Column(String(255), nullable=True)   # 1-line auto-summary
    subject_conf    = Column(Float, default=0.0)

    # Multi-user Support
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    owner           = relationship("User", back_populates="images")
    extracted_texts = relationship("ExtractedText", back_populates="image", cascade="all, delete-orphan")
    keywords        = relationship("Keyword", back_populates="image", cascade="all, delete-orphan")
    search_index    = relationship("ImageSearchIndex", back_populates="image", uselist=False, cascade="all, delete-orphan")

    @property
    def full_text(self):
        return " ".join([t.text_content for t in self.extracted_texts])


class ExtractedText(Base):
    __tablename__ = "extracted_texts"

    id              = Column(Integer, primary_key=True, index=True)
    image_id        = Column(Integer, ForeignKey("images.id"), nullable=False, index=True)
    text_content    = Column(Text, nullable=False)
    confidence      = Column(Float, default=0.0)          # OCR confidence 0.0–1.0
    bbox_x          = Column(Float, nullable=True)        # bounding box (relative 0–1)
    bbox_y          = Column(Float, nullable=True)
    bbox_width      = Column(Float, nullable=True)
    bbox_height     = Column(Float, nullable=True)
    text_order      = Column(Integer, default=0)          # reading order

    image = relationship("Image", back_populates="extracted_texts")


class Keyword(Base):
    __tablename__ = "keywords"

    id         = Column(Integer, primary_key=True, index=True)
    image_id   = Column(Integer, ForeignKey("images.id"), nullable=False, index=True)
    keyword    = Column(String(255), nullable=False, index=True)
    frequency  = Column(Integer, default=1)
    is_stopword= Column(Boolean, default=False)

    image = relationship("Image", back_populates="keywords")


class ImageSearchIndex(Base):
    """
    Consolidated search index for an image.
    Stores 'Index No' (id) and 'Key' (index_key).
    """
    __tablename__ = "image_search_indices"

    id           = Column(Integer, primary_key=True, index=True)
    image_id     = Column(Integer, ForeignKey("images.id"), nullable=False, unique=True, index=True)
    index_key    = Column(Text, nullable=False)   # Space-separated consolidated keywords
    word_count   = Column(Integer, default=0)
    indexed_at   = Column(DateTime, default=datetime.utcnow)

    image = relationship("Image", back_populates="search_index")
