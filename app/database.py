"""
Database configuration for Screendex.
Uses SQLAlchemy with PostgreSQL via psycopg2.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://screendex_user:screendex_pass@localhost:5432/screendex_db")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency injector for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
