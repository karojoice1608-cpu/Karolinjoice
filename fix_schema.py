"""Add missing columns (subject, subject_conf) to images table."""
import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text, inspect

engine = create_engine(os.environ['DATABASE_URL'])

with engine.connect() as conn:
    print('Adding missing columns to images table...')

    try:
        conn.execute(text('ALTER TABLE images ADD COLUMN subject VARCHAR(255)'))
        conn.commit()
        print('  OK: added "subject" column')
    except Exception as e:
        conn.rollback()
        print(f'  "subject" already exists or error: {e}')

    try:
        conn.execute(text('ALTER TABLE images ADD COLUMN subject_conf FLOAT DEFAULT 0.0'))
        conn.commit()
        print('  OK: added "subject_conf" column')
    except Exception as e:
        conn.rollback()
        print(f'  "subject_conf" already exists or error: {e}')

    # Verify final columns
    insp = inspect(engine)
    cols = [c['name'] for c in insp.get_columns('images')]
    print('\nFinal columns in images table:')
    for c in cols:
        print(f'  {c}')

    missing_from_orm = [c for c in ['subject', 'subject_conf'] if c not in cols]
    if missing_from_orm:
        print('\nSTILL MISSING:', missing_from_orm)
    else:
        print('\nAll required columns present!')
