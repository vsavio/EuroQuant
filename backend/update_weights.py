import os
from sqlalchemy import create_engine, text
from portfolio_opt import get_optimized_portfolio_weights

print("Calculating portfolio weights... This may take a minute depending on historical data.")
try:
    weights_dict = get_optimized_portfolio_weights()
    print("Optimization finished. Saving to database...")

    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://euroquant_user:euroquant_password@db:5432/euroquant_db")
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM portfolio_weights"))
        
        for ticker, weight in weights_dict.items():
            conn.execute(
                text("INSERT INTO portfolio_weights (ticker, weight, method) VALUES (:t, :w, 'markowitz_max_sharpe')"),
                {"t": ticker, "w": float(weight)}
            )
                
        conn.commit()
    print("Successfully saved weights to database.")
except Exception as e:
    print(f"Error: {e}")
