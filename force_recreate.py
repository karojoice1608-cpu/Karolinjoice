import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from app.dependencies import hash_password, CORRECT_PASSWORD

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def force_recreate():
    with engine.connect() as conn:
        print(f"Connecting to: {DATABASE_URL}")
        
        # 1. Drop
        try:
            print("Dropping users table...")
            conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
            conn.commit()
            print("Dropped.")
        except Exception as e:
            print(f"FAIL DROP: {e}")
            conn.rollback()

        # 2. Re-create (re-using info from models.py)
        try:
            print("Re-creating users table...")
            conn.execute(text("""
                CREATE TABLE users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE,
                    hashed_password VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.commit()
            print("Re-created.")
        except Exception as e:
            print(f"FAIL CREATE: {e}")
            conn.rollback()

        # 3. Insert admin
        try:
            print("Inserting admin user...")
            admin_hash = hash_password(CORRECT_PASSWORD)
            conn.execute(text(f"INSERT INTO users (username, hashed_password) VALUES ('admin', '{admin_hash}')"))
            conn.commit()
            print("Inserted admin.")
        except Exception as e:
            print(f"FAIL INSERT: {e}")
            conn.rollback()

        # 4. Final verify
        res = conn.execute(text("SELECT username FROM users"))
        print(f"Users in DB: {[r[0] for r in res]}")

if __name__ == "__main__":
    force_recreate()
