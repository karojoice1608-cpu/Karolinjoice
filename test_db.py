import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import User, Image, ImageSearchIndex
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test():
    db = SessionLocal()
    try:
        print("Checking users...")
        users = db.query(User).all()
        print(f"Total users: {len(users)}")
        for u in users:
            print(f" - {u.username}")
        
        print("Checking images...")
        images = db.query(Image).all()
        print(f"Total images: {len(images)}")
        
        print("Checking index...")
        indices = db.query(ImageSearchIndex).all()
        print(f"Total indices: {len(indices)}")
        
        print("Success: Database and models are fine.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test()
