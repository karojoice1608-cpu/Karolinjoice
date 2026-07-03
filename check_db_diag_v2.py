import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def check():
    with engine.connect() as conn:
        print(f"Connecting to: {DATABASE_URL}")
        
        # Check users more deeply
        res = conn.execute(text("SELECT username, LENGTH(username) as len, octet_length(username) as bytes FROM users"))
        users = res.fetchall()
        print(f"Users in DB ({len(users)}):")
        for u in users:
            print(f"  - '{u[0]}' (len: {u[1]}, bytes: {u[2]})")
            # Print hex representation
            res_hex = conn.execute(text(f"SELECT encode('{u[0]}', 'hex')"))
            print(f"    Hex: {res_hex.scalar()}")

        # Try a direct match with admin
        res = conn.execute(text("SELECT * FROM users WHERE username = 'admin'"))
        row = res.fetchone()
        print(f"Direct match 'admin': {row}")

if __name__ == "__main__":
    check()
