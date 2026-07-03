import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("SELECT id, status, error_message FROM images WHERE original_name = 'pharmacy_receipt.png'")).fetchone()
    print(result)
