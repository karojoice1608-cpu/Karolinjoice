import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

DB_NAME = "screendex_db"
DB_USER = "screendex_user"
DB_PASS = "screendex_pass"
DB_HOST = "localhost"
DB_PORT = "5432"

def check_and_create_db():
    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            dbname='postgres',
            user='postgres',
            host=DB_HOST,
            port=DB_PORT
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # Check if user exists
        cur.execute(f"SELECT 1 FROM pg_roles WHERE rolname='{DB_USER}';")
        if not cur.fetchone():
            print(f"Creating user {DB_USER}...")
            cur.execute(f"CREATE USER {DB_USER} WITH PASSWORD '{DB_PASS}';")
        
        # Check if database exists
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}';")
        if not cur.fetchone():
            print(f"Creating database {DB_NAME}...")
            cur.execute(f"CREATE DATABASE {DB_NAME} OWNER {DB_USER};")
        
        cur.close()
        conn.close()
        print("Database and user verification complete.")
        return True
    except Exception as e:
        print(f"Error verifying database: {e}")
        return False

if __name__ == "__main__":
    check_and_create_db()
