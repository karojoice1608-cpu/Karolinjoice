"""
Images Router for Screendex.
Handles upload, retrieval, deletion, and batch operations.
"""

import os
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Image, ExtractedText, Keyword, ProcessingStatusEnum, ImageTypeEnum, User
from app.schemas import ImageUploadResponse, ImageDetailSchema
from app.services.image_service import save_uploaded_file, process_image, detect_image_type
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/images", tags=["images"], dependencies=[Depends(get_current_user)])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}
MAX_FILE_SIZE      = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))  # 10 MB


@router.post("/upload", response_model=ImageUploadResponse)
async def upload_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    image_type: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Upload a single image for OCR indexing.
    Processing happens asynchronously in background.
    """
    # Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file
    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10 MB.")

    # Save to disk
    file_path, filename = save_uploaded_file(file_data, file.filename)

    # Detect image type using intelligent CV heuristic
    detected_type = detect_image_type(file_path, file.filename)
    if image_type:
        try:
            detected_type = ImageTypeEnum(image_type)
        except ValueError:
            pass

    # Create DB record
    db_image = Image(
        filename      = filename,
        original_name = file.filename,
        file_path     = file_path,
        file_size     = len(file_data),
        image_type    = detected_type,
        status        = ProcessingStatusEnum.pending,
        user_id       = user.id,
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)

    # Trigger background processing
    background_tasks.add_task(process_image, db, db_image.id)

    return ImageUploadResponse(
        id            = db_image.id,
        filename      = db_image.filename,
        original_name = db_image.original_name,
        status        = db_image.status.value,
        message       = "Image uploaded successfully. OCR processing started in background.",
    )


@router.post("/upload-batch", response_model=List[ImageUploadResponse])
async def upload_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload multiple images at once (max 20)."""
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per batch upload.")

    responses = []
    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue  # Skip invalid files

        file_data = await file.read()
        if len(file_data) > MAX_FILE_SIZE:
            continue

        file_path, filename = save_uploaded_file(file_data, file.filename)
        detected_type = detect_image_type(file_path, file.filename)

        db_image = Image(
            filename      = filename,
            original_name = file.filename,
            file_path     = file_path,
            file_size     = len(file_data),
            image_type    = detected_type,
            status        = ProcessingStatusEnum.pending,
            user_id       = user.id,
        )
        db.add(db_image)
        db.commit()
        db.refresh(db_image)

        background_tasks.add_task(process_image, db, db_image.id)

        responses.append(ImageUploadResponse(
            id            = db_image.id,
            filename      = db_image.filename,
            original_name = db_image.original_name,
            status        = db_image.status.value,
            message       = "Queued for processing",
        ))

    return responses


@router.get("/", response_model=List[ImageDetailSchema])
def list_images(
    page:       int = 1,
    page_size:  int = 12,
    status:     Optional[str] = None,
    image_type: Optional[str] = None,
    category:   Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all indexed images with pagination and optional filters."""
    query = db.query(Image).filter(Image.user_id == user.id)
    if status:
        try:
            query = query.filter(Image.status == ProcessingStatusEnum(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if image_type:
        try:
            query = query.filter(Image.image_type == ImageTypeEnum(image_type))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid image_type: {image_type}")
    if category:
        query = query.filter(Image.category == category)

    offset = (page - 1) * page_size
    images = query.order_by(Image.uploaded_at.desc()).offset(offset).limit(page_size).all()
    return images


@router.get("/{image_id}", response_model=ImageDetailSchema)
def get_image(image_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get full details of a specific image including all extracted text and keywords."""
    image = db.query(Image).filter(Image.id == image_id, Image.user_id == user.id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    # Build full_text
    full_text = " ".join([et.text_content for et in image.extracted_texts])

    result = ImageDetailSchema(
        id              = image.id,
        filename        = image.filename,
        original_name   = image.original_name,
        file_path       = image.file_path,
        thumbnail_path  = image.thumbnail_path,
        image_type      = image.image_type.value if image.image_type else "unknown",
        width           = image.width,
        height          = image.height,
        status          = image.status.value,
        uploaded_at     = image.uploaded_at,
        processed_at    = image.processed_at,
        extracted_texts = image.extracted_texts,
        keywords        = image.keywords,
        full_text       = full_text,
        category        = image.category,
        category_conf   = image.category_conf,
        is_duplicate    = image.is_duplicate,
        original_id     = image.original_id,
    )
    return result


@router.post("/{image_id}/reprocess")
def reprocess_image(
    image_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Reprocess an image (useful if OCR failed or settings changed)."""
    image = db.query(Image).filter(Image.id == image_id, Image.user_id == user.id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    # Clear existing data
    db.query(ExtractedText).filter(ExtractedText.image_id == image_id).delete()
    db.query(Keyword).filter(Keyword.image_id == image_id).delete()
    image.status        = ProcessingStatusEnum.pending
    image.error_message = None
    db.commit()

    background_tasks.add_task(process_image, db, image_id)
    return {"message": f"Reprocessing started for image {image_id}"}


@router.delete("/{image_id}")
def delete_image(image_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Delete an image and all associated data."""
    image = db.query(Image).filter(Image.id == image_id, Image.user_id == user.id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    # Remove files
    for path in [image.file_path, image.thumbnail_path]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    # Unlink any duplicates that reference this image to prevent IntegrityError
    db.query(Image).filter(Image.original_id == image_id).update({"original_id": None})

    db.delete(image)
    db.commit()
    return {"message": f"Image {image_id} deleted successfully"}


@router.get("/{image_id}/status")
def get_image_status(image_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Poll processing status of an image (used by frontend for progress updates)."""
    image = db.query(Image).filter(Image.id == image_id, Image.user_id == user.id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    return {
        "id":             image.id,
        "status":         image.status.value,
        "error_message":  image.error_message,
        "processed_at":   image.processed_at.isoformat() if image.processed_at else None,
        "text_regions":   len(image.extracted_texts),
        "keywords_count": len(image.keywords),
        "category":       image.category,
        "is_duplicate":    image.is_duplicate,
    }
