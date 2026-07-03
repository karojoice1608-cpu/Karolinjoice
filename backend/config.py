from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Database - Using SQLite for local development
    database_url: str = "sqlite+aiosqlite:///./screendex.db"
    database_url_sync: str = "sqlite:///./screendex.db"

    # Storage
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 20

    # OCR
    ocr_engine: str = "both"  # "easyocr" | "tesseract" | "both"
    ocr_confidence_threshold: float = 0.4
    easyocr_languages: str = "en"

    # EAST
    east_model_path: str = "models/frozen_east_text_detection.pb"
    east_confidence_threshold: float = 0.5
    east_nms_threshold: float = 0.4

    # Semantic search
    sentence_transformer_model: str = "all-MiniLM-L6-v2"
    semantic_threshold: float = 0.3

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True
    secret_key: str = "change-this-in-production"

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def easyocr_language_list(self) -> list[str]:
        return [lang.strip() for lang in self.easyocr_languages.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
