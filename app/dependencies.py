import os
import secrets
import hashlib
import logging
from fastapi import Request
from fastapi.responses import RedirectResponse
from app.database import SessionLocal
from app.models.models import User

logger = logging.getLogger(__name__)

CORRECT_USERNAME = os.getenv("AUTH_USERNAME", "admin")
CORRECT_PASSWORD = os.getenv("AUTH_PASSWORD", "password")


def hash_password(plain: str) -> str:
    """Hash a plain-text password with a random salt using SHA-256."""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + plain).encode("utf-8")).hexdigest()
    return f"{salt}${hashed}"


def verify_password(plain: str, stored: str) -> bool:
    """Verify a plain-text password against a stored salt$hash string."""
    try:
        salt, hashed = stored.split("$", 1)
        return hashlib.sha256((salt + plain).encode("utf-8")).hexdigest() == hashed
    except Exception:
        return False


class RedirectException(Exception):
    def __init__(self, url: str):
        self.url = url


async def get_current_user(request: Request):
    """Session-based auth. Returns User object or raises RedirectException."""
    username = request.session.get("username")
    if not username:
        raise RedirectException("/login")
    
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    
    # Auto-create admin user if it doesn't exist yet (for first-time setup)
    if not user and username == CORRECT_USERNAME:
        try:
            user = User(username=username, hashed_password=hash_password(CORRECT_PASSWORD))
            db.add(user)
            db.commit()
            db.refresh(user)
        except Exception:
            logger.exception(f"Failed to auto-create admin user '{username}'")
            db.rollback()
            # If commit failed, someone else likely created it; try fetching again
            user = db.query(User).filter(User.username == username).first()
    
    db.close()
    
    if not user:
        request.session.clear()
        raise RedirectException("/login")
        
    return user


def verify_credentials(username: str, password: str) -> bool:
    """Check username and password against env vars."""
    ok_user = secrets.compare_digest(
        username.encode("utf8"),
        CORRECT_USERNAME.encode("utf8"),
    )
    ok_pass = secrets.compare_digest(
        password.encode("utf8"),
        CORRECT_PASSWORD.encode("utf8"),
    )
    return ok_user and ok_pass
