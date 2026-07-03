#!/usr/bin/env python3
"""
Build Semantic Index Script
Iterates through all completed images and adds their OCR text to the Semantic index.
"""

import sys
import os
import logging
logging.basicConfig(level=logging.INFO)

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.models import Image, ProcessingStatusEnum
from app.services.semantic_service import semantic_service

def main():
    if not semantic_service.model:
        print("Error: Semantic service failed to initialize (is sentence-transformers installed?)")
        sys.exit(1)

    db = SessionLocal()
    try:
        images = db.query(Image).filter(Image.status == ProcessingStatusEnum.completed).all()
        print(f"Found {len(images)} completed images to index.")
        
        success_count = 0
        for i, img in enumerate(images, 1):
            text = img.full_text
            if not text.strip():
                print(f"[{i}/{len(images)}] Skipping Image {img.id} (No text)")
                continue

            success = semantic_service.add_to_index(img.id, text)
            if success:
                success_count += 1
                print(f"[{i}/{len(images)}] Added Image {img.id} to semantic index.")
            else:
                print(f"[{i}/{len(images)}] Failed to add Image {img.id}.")
                
        # Force save
        semantic_service.save_index()
        print(f"\nDone! Successfully indexed {success_count} images.")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
