import sys
import os

# Ensure the app directory is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.database import SessionLocal, engine
    from sqlalchemy import text
    
    print("Attempting to connect to the database...")
    db = SessionLocal()
    result = db.execute(text("SELECT 1"))
    print(f"Success! Result: {result.fetchone()}")
    db.close()
except Exception as e:
    print(f"Error connecting to database: {e}")
    import traceback
    traceback.print_exc()
