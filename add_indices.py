import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text('CREATE INDEX IF NOT EXISTS ix_extracted_texts_image_id ON extracted_texts (image_id);'))
    conn.execute(text('CREATE INDEX IF NOT EXISTS ix_keywords_image_id ON keywords (image_id);'))
    conn.commit()

print("Indices created successfully.")
