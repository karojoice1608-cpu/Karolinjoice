#!/usr/bin/env python3
"""
Screendex Database Setup Script
Run this BEFORE starting the application for the first time.

Usage:
  python setup_db.py

What it does:
  1. Creates the PostgreSQL database and user (requires superuser psql access)
  2. Creates all tables
  3. Optionally seeds demo data
"""

import os
import sys
import subprocess

DB_NAME = "screendex_db"
DB_USER = "screendex_user"
DB_PASS = "screendex_pass"


def run_psql(cmd, superuser=True):
    """Execute a psql command."""
    user_flag = ["-U", "postgres"] if superuser else ["-U", DB_USER]
    result = subprocess.run(
        ["psql"] + user_flag + ["-c", cmd],
        capture_output=True, text=True
    )
    return result.returncode == 0, result.stdout, result.stderr


def create_db():
    print("=== Screendex Database Setup ===\n")

    # Create user
    print(f"[1/3] Creating user '{DB_USER}'...")
    ok, out, err = run_psql(f"CREATE USER {DB_USER} WITH PASSWORD '{DB_PASS}';")
    if ok:
        print(f"      ✅ User created.")
    else:
        print(f"      ⚠️  User may already exist: {err.strip()}")

    # Create database
    print(f"[2/3] Creating database '{DB_NAME}'...")
    ok, out, err = run_psql(f"CREATE DATABASE {DB_NAME} OWNER {DB_USER};")
    if ok:
        print(f"      ✅ Database created.")
    else:
        print(f"      ⚠️  Database may already exist: {err.strip()}")

    # Grant privileges
    print(f"[3/3] Granting privileges...")
    run_psql(f"GRANT ALL PRIVILEGES ON DATABASE {DB_NAME} TO {DB_USER};")
    run_psql(f"ALTER USER {DB_USER} CREATEDB;")
    print(f"      ✅ Privileges granted.")

    print("\n✅ Database setup complete!")


def create_tables():
    print("\n=== Creating Tables ===\n")

    # Import app database setup
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from app.database import engine, Base
    from app.models.models import Image, ExtractedText, Keyword

    Base.metadata.create_all(bind=engine)
    print("✅ All tables created successfully!")

    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"   Tables: {', '.join(tables)}")


def verify_connection():
    print("\n=== Verifying Connection ===\n")
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        db.execute(__import__('sqlalchemy').text("SELECT 1"))
        db.close()
        print("✅ Database connection successful!")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nMake sure PostgreSQL is running and .env is configured correctly.")
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Screendex DB Setup")
    parser.add_argument("--skip-db-create", action="store_true",
                        help="Skip database/user creation (if already exists)")
    args = parser.parse_args()

    if not args.skip_db_create:
        create_db()

    if verify_connection():
        create_tables()
        print("\n🚀 Ready to run: uvicorn main:app --reload --port 8000")
    else:
        print("\n💡 If DB/user already exist, run: python setup_db.py --skip-db-create")
        sys.exit(1)
