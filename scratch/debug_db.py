import psycopg2
from psycopg2.extras import RealDictCursor

try:
    conn = psycopg2.connect("postgresql://euroquant_user:euroquant_password@localhost:5432/euroquant_db")
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("--- AUDIT LOG COUNT ---")
    cur.execute("SELECT COUNT(*) FROM audit_log")
    print(cur.fetchone())
    
    print("--- AUDIT LOG ENTRIES ---")
    cur.execute("SELECT * FROM audit_log LIMIT 5")
    for row in cur.fetchall():
        print(row)
        
    print("--- ML METRICS COUNT ---")
    cur.execute("SELECT COUNT(*) FROM ml_model_metrics")
    print(cur.fetchone())
    
    print("--- ML METRICS ENTRIES ---")
    cur.execute("SELECT ticker, last_trained, accuracy, precision FROM ml_model_metrics")
    for row in cur.fetchall():
        print(row)
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error connecting: {e}")
