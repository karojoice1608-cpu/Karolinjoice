import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def check():
    with engine.connect() as conn:
        print(f"Connecting to: {DATABASE_URL}")
        
        # 1. Check indexes
        res = conn.execute(text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'users'"))
        for r in res:
            print(f"Index: {r[0]}, Def: {r[1]}")
            
        # 2. Try to insert a DIFFERENT user
        try:
            print("Trying to insert user 'testuser'...")
            conn.execute(text("INSERT INTO users (username, created_at) VALUES ('testuser', now())"))
            conn.commit()
            print("SUCCESS: Inserted 'testuser'")
        except Exception as e:
            print(f"FAIL: {e}")
            conn.rollback()

        # 3. Try to insert 'admin' again
        try:
            print("Trying to insert user 'admin'...")
            conn.execute(text("INSERT INTO users (username, created_at) VALUES ('admin', now())"))
            conn.commit()
            print("SUCCESS: Inserted 'admin'")
        except Exception as e:
            print(f"FAIL: {e}")
            conn.rollback()

if __name__ == "__main__":
    check()
