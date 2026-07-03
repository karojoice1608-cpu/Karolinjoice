import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def check():
    with engine.connect() as conn:
        print(f"Connecting to: {DATABASE_URL}")
        
        # Check tables
        res = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        tables = [r[0] for r in res]
        print(f"Tables: {tables}")
        
        if "users" in tables:
            res = conn.execute(text("SELECT * FROM users"))
            users = res.fetchall()
            print(f"Users in DB ({len(users)}):")
            for u in users:
                print(f"  - {u}")
        else:
            print("ERROR: 'users' table not found!")

if __name__ == "__main__":
    check()
