"""
Image Router
─────────────
Endpoints:
    POST   /api/images/upload          Upload one or more images
    GET    /api/images/                List all images (paginated)
    GET    /api/images/{image_id}      Get single image detail
    DELETE /api/images/{image_id}      Delete image and all associated data
    GET    /api/images/{image_id}/regions  Get text regions for an image
"""

import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models.image import Image
from backend.models.text_region import TextRegion
from backend.services.pipeline import process_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/images", tags=["images"])

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/jpg", "image/png",
    "image/webp", "image/bmp", "image/tiff",
}


async def _save_upload(file: UploadFile) -> tuple[str, str, int, str]:
    """
    Save uploaded file to disk. Returns (filename, file_path, size_bytes, mime_type).
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. Allowed: JPEG, PNG, WEBP, BMP, TIFF"
        )

    suffix = Path(file.filename or "upload").suffix or ".jpg"
    unique_name = f"{uuid.uuid4()}{suffix}"
    dest = settings.upload_path / unique_name

    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):  # 1 MB chunks
            size += len(chunk)
            if size > settings.max_upload_size_mb * 1024 * 1024:
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB"
                )
            out.write(chunk)

    return unique_name, str(dest), size, file.content_type


@router.post("/upload")
async def upload_images(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload one or more images. Processing (OCR, indexing) runs as a background task.

    Returns immediately with image IDs and 'pending' status.
    Poll GET /api/images/{image_id} to check processing status.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 files per request")

    created = []
    for file in files:
        filename, file_path, size, mime = await _save_upload(file)

        image = Image(
            filename=filename,
            original_filename=file.filename or filename,
            file_path=file_path,
            file_size_bytes=size,
            mime_type=mime,
            status="pending",
        )
        db.add(image)
        await db.flush()  # Get the ID before background task runs

        # Queue processing as a background task
        # Each task gets its own DB session via a new context
        background_tasks.add_task(_process_in_background, str(image.id))

        created.append({
            "image_id": str(image.id),
            "original_filename": image.original_filename,
            "status": "pending",
            "file_size_bytes": size,
        })

    return {
        "uploaded": len(created),
        "images": created,
        "message": "Images queued for processing. Poll status via GET /api/images/{image_id}",
    }


async def _process_in_background(image_id: str):
    """Wrapper to create a fresh DB session for background processing."""
    from backend.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await process_image(uuid.UUID(image_id), db)
            await db.commit()
        except Exception as e:
            logger.exception(f"Background processing failed for {image_id}: {e}")
            await db.rollback()


@router.get("/")
async def list_images(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    image_type: Optional[str] = Query(None),
):
    """List all images with optional status and type filters."""
    offset = (page - 1) * page_size

    stmt = select(Image).order_by(desc(Image.uploaded_at)).offset(offset).limit(page_size)
    if status:
        stmt = stmt.where(Image.status == status)
    if image_type:
        stmt = stmt.where(Image.image_type == image_type)

    result = await db.execute(stmt)
    images = result.scalars().all()

    return {
        "page": page,
        "page_size": page_size,
        "images": [_image_summary(img) for img in images],
    }


@router.get("/{image_id}")
async def get_image(image_id: str, db: AsyncSession = Depends(get_db)):
    """Get full detail for a single image including processing status."""
    try:
        uid = uuid.UUID(image_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid image ID format")

    image = await db.get(Image, uid)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    return _image_detail(image)


@router.get("/{image_id}/file")
async def get_image_file(image_id: str, db: AsyncSession = Depends(get_db)):
    """Serve the raw image file."""
    try:
        uid = uuid.UUID(image_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid image ID format")

    image = await db.get(Image, uid)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    file_path = Path(image.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    return FileResponse(str(file_path), media_type=image.mime_type)


@router.get("/{image_id}/regions")
async def get_image_regions(image_id: str, db: AsyncSession = Depends(get_db)):
    """Get all detected text regions for an image."""
    try:
        uid = uuid.UUID(image_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid image ID format")

    stmt = (
        select(TextRegion)
        .where(TextRegion.image_id == uid)
        .order_by(TextRegion.reading_order)
    )
    result = await db.execute(stmt)
    regions = result.scalars().all()

    return {
        "image_id": image_id,
        "region_count": len(regions),
        "regions": [_region_dict(r) for r in regions],
    }


@router.delete("/{image_id}")
async def delete_image(image_id: str, db: AsyncSession = Depends(get_db)):
    """Delete an image and all its associated text regions. Also removes the file from disk."""
    try:
        uid = uuid.UUID(image_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid image ID format")

    image = await db.get(Image, uid)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    # Remove file from disk
    file_path = Path(image.file_path)
    file_path.unlink(missing_ok=True)

    await db.delete(image)
    return {"deleted": True, "image_id": image_id}


# ─── Serialisation helpers ────────────────────────────────────────────────────

def _image_summary(img: Image) -> dict:
    return {
        "image_id": str(img.id),
        "original_filename": img.original_filename,
        "image_type": img.image_type,
        "status": img.status,
        "avg_confidence": img.avg_confidence,
        "region_count": img.region_count,
        "uploaded_at": img.uploaded_at.isoformat() if img.uploaded_at else None,
    }


def _image_detail(img: Image) -> dict:
    return {
        **_image_summary(img),
        "filename": img.filename,
        "file_path": img.file_path,
        "file_size_bytes": img.file_size_bytes,
        "mime_type": img.mime_type,
        "width_px": img.width_px,
        "height_px": img.height_px,
        "full_text": img.full_text,
        "keywords": img.keywords or [],
        "ocr_engine_used": img.ocr_engine_used,
        "error_message": img.error_message,
        "processed_at": img.processed_at.isoformat() if img.processed_at else None,
    }


def _region_dict(r: TextRegion) -> dict:
    return {
        "id": str(r.id),
        "bbox": r.bbox,
        "raw_text": r.raw_text,
        "cleaned_text": r.cleaned_text,
        "confidence": r.confidence,
        "ocr_engine": r.ocr_engine,
        "region_type": r.region_type,
        "reading_order": r.reading_order,
    }
