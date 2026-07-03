"""
Screendex - AI-Powered Image Indexing & Search System
Main FastAPI Application

Architecture:
  FastAPI (async) → PostgreSQL (SQLAlchemy ORM) → EasyOCR / Tesseract → NLTK NLP
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.database import engine, Base, SessionLocal
from app.models.models import User
from app.routers import images, search, admin
from app.dependencies import get_current_user, verify_credentials, RedirectException, hash_password, verify_password, CORRECT_USERNAME

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Startup / Shutdown ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables and required directories on startup."""
    logger.info("Starting Screendex...")
    Base.metadata.create_all(bind=engine)

    # Ensure upload directories exist
    for d in ["static/uploads", "static/uploads/thumbnails"]:
        os.makedirs(d, exist_ok=True)

    logger.info("Database tables created / verified.")
    logger.info("Screendex ready.")
    yield
    logger.info("Screendex shutting down.")


# ── App Instance ───────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "Screendex API",
    description = (
        "AI-Powered Image Indexing and Search System. "
        "Extracts text from Born-Digital and Scene Text images "
        "using OCR and deep learning, then enables keyword-based search."
    ),
    version     = "1.0.0",
    lifespan    = lifespan,
    docs_url    = "/api/docs",
    redoc_url   = "/api/redoc",
)

@app.exception_handler(RedirectException)
async def redirect_exception_handler(request: Request, exc: RedirectException):
    return RedirectResponse(exc.url)

# ── Session Middleware ─────────────────────────────────────────────────────────
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "screendex-secret-key-change-in-production"),
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Static Files ───────────────────────────────────────────────────────────────
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Templates ──────────────────────────────────────────────────────────────────
templates = Jinja2Templates(directory="templates")

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(images.router)
app.include_router(search.router)
app.include_router(admin.router)


# ── Auth Routes ────────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # If already logged in, redirect home
    if request.session.get("username"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    # 1. First, check static env-based admin credentials for convenience/override
    if verify_credentials(username, password):
        request.session["username"] = username
        return RedirectResponse("/", status_code=302)

    # 2. Check Database for regular users or migrated admin
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user and user.hashed_password:
            if verify_password(password, user.hashed_password):
                request.session["username"] = username
                return RedirectResponse("/", status_code=302)
    finally:
        db.close()

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid username or password. Please try again."},
        status_code=401,
    )


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


# ── Signup Routes ──────────────────────────────────────────────────────────────
@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    # If already logged in, redirect home
    if request.session.get("username"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("signup.html", {"request": request, "error": None, "success": None})


@app.post("/signup", response_class=HTMLResponse)
async def signup_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(""),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    # Basic validation
    if password != confirm_password:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Passwords do not match.", "success": None},
            status_code=400,
        )
    if len(password) < 6:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Password must be at least 6 characters.", "success": None},
            status_code=400,
        )

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            return templates.TemplateResponse(
                "signup.html",
                {"request": request, "error": f"Username '{username}' is already taken.", "success": None},
                status_code=400,
            )
        new_user = User(
            username=username,
            email=email or None,
            hashed_password=hash_password(password),
        )
        db.add(new_user)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Signup failed")
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Registration failed. Please try again.", "success": None},
            status_code=500,
        )
    finally:
        db.close()

    # Auto-login after successful signup
    request.session["username"] = username
    return RedirectResponse("/", status_code=302)


# ── Frontend Routes ────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("index.html", {"request": request, "username": user.username})


@app.get("/admin", response_class=HTMLResponse)
async def admin_shell(request: Request, user: User = Depends(get_current_user)):
    # Only allow the designated admin user
    if user.username != CORRECT_USERNAME:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("admin.html", {"request": request, "username": user.username})


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("upload.html", {"request": request, "username": user.username})


@app.get("/gallery", response_class=HTMLResponse)
async def gallery_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("gallery.html", {"request": request, "username": user.username})


@app.get("/image/{image_id}", response_class=HTMLResponse)
async def image_detail_page(request: Request, image_id: int, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("image_detail.html", {"request": request, "image_id": image_id, "username": user.username})


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("profile.html", {"request": request, "username": user.username})

# ── Health Check ───────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Screendex", "version": "1.0.0"}
