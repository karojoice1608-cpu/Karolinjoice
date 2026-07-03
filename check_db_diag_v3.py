import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def check():
    with engine.connect() as conn:
        print(f"Connecting to: {DATABASE_URL}")
        
        # Check all schemas
        res = conn.execute(text("SELECT schema_name FROM information_schema.schemata"))
        schemas = [r[0] for r in res]
        print(f"Schemas: {schemas}")
        
        # Check all 'users' tables in all schemas
        res = conn.execute(text("SELECT table_schema, table_name FROM information_schema.tables WHERE table_name = 'users'"))
        found_tables = res.fetchall()
        print(f"Found 'users' tables: {found_tables}")
        
        for schema, table in found_tables:
            res = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.{table}"))
            count = res.scalar()
            print(f"Count in {schema}.{table}: {count}")
            if count > 0:
                res = conn.execute(text(f"SELECT * FROM {schema}.{table}"))
                print(f"Data in {schema}.{table}: {res.fetchall()}")

if __name__ == "__main__":
    check()
