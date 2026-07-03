import os
import logging
import secrets
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Import models
from app.database import SessionLocal, engine
from app.models.models import User

load_dotenv()

CORRECT_USERNAME = os.getenv("AUTH_USERNAME", "admin")
CORRECT_PASSWORD = os.getenv("AUTH_PASSWORD", "password")

def test_login_logic(username, password):
    print(f"Testing login for: {username}")
    
    # 1. Verify credentials (simulating verify_credentials)
    ok_user = secrets.compare_digest(username.encode("utf8"), CORRECT_USERNAME.encode("utf8"))
    ok_pass = secrets.compare_digest(password.encode("utf8"), CORRECT_PASSWORD.encode("utf8"))
    if not (ok_user and ok_pass):
        print("FAIL: Invalid credentials")
        return

    print("PASS: Credentials valid")

    # 2. Get/Create user (simulating get_current_user logic)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"User '{username}' not found. Attempting to create...")
            try:
                user = User(username=username)
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"SUCCESS: Created user '{username}' (ID: {user.id})")
            except Exception as e:
                print(f"FAIL: Could not create user: {e}")
                db.rollback()
                # Re-check
                user = db.query(User).filter(User.username == username).first()
                if user:
                    print(f"RE-CHECK: User found after all (ID: {user.id})")
                else:
                    print("RE-CHECK: User STILL not found")
        else:
            print(f"SUCCESS: User '{username}' found (ID: {user.id})")
    finally:
        db.close()

if __name__ == "__main__":
    test_login_logic("admin", "password")
