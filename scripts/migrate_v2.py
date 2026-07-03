import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found in .env")
    exit(1)

engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        print("Starting migration...")
        
        # 1. Create users table if not exists, then ensure columns
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY
            )
        """))
        print("Checked/Created 'users' table.")

        users_columns = [
            ("username", "VARCHAR UNIQUE"),
            ("email", "VARCHAR UNIQUE"),
            ("hashed_password", "VARCHAR"),
            ("full_name", "VARCHAR"),
            ("is_active", "BOOLEAN DEFAULT TRUE"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]
        for col_name, col_type in users_columns:
            res = conn.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='{col_name}'")).fetchone()
            if not res:
                print(f"Adding column '{col_name}' to 'users' table...")
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))

        # 2. Add columns to images table
        # We use a helper to check if columns exist before adding
        columns_to_add = [
            ("user_id", "INTEGER REFERENCES users(id)"),
            ("category", "VARCHAR"),
            ("category_conf", "FLOAT DEFAULT 0.0"),
            ("file_hash", "VARCHAR"),
            ("phash", "VARCHAR"),
            ("is_duplicate", "BOOLEAN DEFAULT FALSE"),
            ("original_id", "INTEGER REFERENCES images(id)")
        ]

        for col_name, col_type in columns_to_add:
            # Check if column exists
            res = conn.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='images' AND column_name='{col_name}'
            """)).fetchone()
            
            if not res:
                print(f"Adding column '{col_name}' to 'images' table...")
                conn.execute(text(f"ALTER TABLE images ADD COLUMN {col_name} {col_type}"))
            else:
                print(f"Column '{col_name}' already exists in 'images'.")

        # 3. Create image_search_index table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS image_search_index (
                id SERIAL PRIMARY KEY,
                image_id INTEGER REFERENCES images(id) ON DELETE CASCADE,
                index_key TEXT,
                word_count INTEGER,
                is_stale BOOLEAN DEFAULT FALSE,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("Checked/Created 'image_search_index' table.")
        
        conn.commit()
        print("Migration completed successfully!")

if __name__ == "__main__":
    migrate()
