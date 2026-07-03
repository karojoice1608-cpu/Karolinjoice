import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def check():
    with engine.connect() as conn:
        print(f"Connecting to: {DATABASE_URL}")
        
        # Check images
        res = conn.execute(text("SELECT id, filename, status, category, is_duplicate, original_id FROM images"))
        rows = res.fetchall()
        print(f"Total images: {len(rows)}")
        for r in rows:
            print(f"  - {r}")

if __name__ == "__main__":
    check()
