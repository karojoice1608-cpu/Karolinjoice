import uuid
from sqlalchemy import Column, String, Float, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

from backend.database import Base


class TextRegion(Base):
    __tablename__ = "text_regions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    image_id = Column(String(36), ForeignKey("images.id", ondelete="CASCADE"), nullable=False)

    # Bounding box — pixel coordinates (top-left origin)
    bbox_x = Column(Integer, nullable=False)   # left
    bbox_y = Column(Integer, nullable=False)   # top
    bbox_w = Column(Integer, nullable=False)   # width
    bbox_h = Column(Integer, nullable=False)   # height

    # Extracted content
    raw_text = Column(Text, nullable=False)
    cleaned_text = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False)   # 0.0–1.0
    ocr_engine = Column(String(32), nullable=False)  # "easyocr" | "tesseract"

    # Region classification
    region_type = Column(String(32), nullable=True)  # "born_digital" | "scene_text"

    # Reading order (top-to-bottom, left-to-right sort index)
    reading_order = Column(Integer, default=0)

    # Relationship
    image = relationship("Image", back_populates="text_regions")

    __table_args__ = (
        Index("ix_text_regions_image_id", "image_id"),
        Index("ix_text_regions_confidence", "confidence"),
    )

    @property
    def bbox(self) -> dict:
        return {"x": self.bbox_x, "y": self.bbox_y, "w": self.bbox_w, "h": self.bbox_h}

    def __repr__(self):
        return f"<TextRegion image={self.image_id} text='{self.raw_text[:40]}' conf={self.confidence:.2f}>"
