import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://euroquant_user:euroquant_password@localhost:5432/euroquant_db")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key_value VARCHAR(64) UNIQUE NOT NULL,
            label VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            hourly_limit INT DEFAULT 0,
            daily_limit INT DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS api_key_usage (
            usage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key_value VARCHAR(64) REFERENCES api_keys(key_value) ON DELETE CASCADE,
            endpoint VARCHAR(255),
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_api_key_usage_key_time 
        ON api_key_usage(key_value, timestamp)
    """))
    conn.commit()
    print("Table api_keys created successfully.")
