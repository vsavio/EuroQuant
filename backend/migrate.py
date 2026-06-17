import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://euroquant_user:euroquant_password@localhost:5432/euroquant_db")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE api_keys ADD COLUMN hourly_limit INT DEFAULT 0"))
        print("Added hourly_limit")
    except Exception as e:
        print("hourly_limit may already exist")
        
    try:
        conn.execute(text("ALTER TABLE api_keys ADD COLUMN daily_limit INT DEFAULT 0"))
        print("Added daily_limit")
    except Exception as e:
        print("daily_limit may already exist")
        
    conn.commit()

import create_table # This will create the new tables
