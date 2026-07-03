"""
Directly reproduce the /api/images/ 500 error without HTTP layer.
"""
import sys, os, traceback
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.models.models import Image, User, ProcessingStatusEnum
from app.schemas import ImageDetailSchema
from pydantic import TypeAdapter
from typing import List

db = SessionLocal()

try:
    # Get admin user
    user = db.query(User).filter(User.username == 'admin').first()
    print(f"Admin user: id={user.id}")

    # Run exact same query as list_images
    images = db.query(Image).filter(Image.user_id == user.id)\
               .order_by(Image.uploaded_at.desc())\
               .offset(0).limit(12).all()

    print(f"Images fetched: {len(images)}")

    # Try to serialize exactly as FastAPI's response_model does
    for img in images:
        print(f"\n  Trying to serialize image id={img.id} ...")
        try:
            schema = ImageDetailSchema.model_validate(img, from_attributes=True)
            print(f"    OK: status={schema.status}, image_type={schema.image_type}")
        except Exception as e:
            print(f"    FAILED: {type(e).__name__}: {e}")
            traceback.print_exc()

except Exception as e:
    print(f"OUTER ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()
finally:
    db.close()
