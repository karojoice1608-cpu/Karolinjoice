import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def reset_and_seed():
    with engine.connect() as conn:
        print(f"Connecting to: {DATABASE_URL}")
        
        # 1. Truncate
        print("Truncating users table...")
        conn.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        conn.commit()
        print("Truncated.")
        
        # 2. Insert admin
        print("Inserting admin user...")
        conn.execute(text("INSERT INTO users (username, created_at) VALUES ('admin', now())"))
        conn.commit()
        print("Inserted admin.")
        
        # 3. Verify
        res = conn.execute(text("SELECT count(*) FROM users"))
        count = res.scalar()
        print(f"Total users now: {count}")
        
        if count > 0:
            res = conn.execute(text("SELECT * FROM users"))
            print(f"User data: {res.fetchone()}")

if __name__ == "__main__":
    reset_and_seed()
