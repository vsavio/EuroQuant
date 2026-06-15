"""
EuroQuant Backtest Engine
=========================
Computes historical performance of past signals stored in recommendation_history
against actual subsequent price movements. Results (win rate, Sharpe, max drawdown)
are persisted in the backtest_results table for dashboard display.
"""
import math
import json
from datetime import datetime, timezone
from sqlalchemy import text
from database import SessionLocal


def run_backtest():
    """
    For each ticker:
    1. Load all historical signals from recommendation_history.
    2. Look up the actual price at signal date and 5 days later.
    3. Compute return per trade.
    4. Aggregate: Win Rate, Avg Return, Sharpe Ratio, Max Drawdown, Total Trades.
    5. Persist to backtest_results table.
    """
    db = SessionLocal()
    try:
        # Ensure the results table exists
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                ticker          VARCHAR(20) PRIMARY KEY,
                total_trades    INTEGER     DEFAULT 0,
                win_rate        NUMERIC(6,4) DEFAULT 0,
                avg_return_pct  NUMERIC(8,4) DEFAULT 0,
                sharpe_ratio    NUMERIC(8,4) DEFAULT 0,
                max_drawdown_pct NUMERIC(8,4) DEFAULT 0,
                last_computed   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        db.commit()

        tickers = [r[0] for r in db.execute(
            text("SELECT DISTINCT ticker FROM recommendation_history")
        ).fetchall()]

        print(f"[Backtest] Evaluating {len(tickers)} tickers...")

        for ticker in tickers:
            # Load signals
            signals = db.execute(text("""
                SELECT rh.timestamp, rh.signal, sp_entry.close AS entry_price
                FROM recommendation_history rh
                JOIN LATERAL (
                    SELECT close FROM stock_prices
                    WHERE ticker = rh.ticker
                      AND timestamp >= rh.timestamp
                    ORDER BY timestamp ASC
                    LIMIT 1
                ) sp_entry ON TRUE
                WHERE rh.ticker = :ticker
                  AND rh.signal IN ('BUY', 'SELL')
                ORDER BY rh.timestamp ASC
            """), {"ticker": ticker}).fetchall()

            if len(signals) < 5:
                continue

            returns = []
            for sig_ts, sig_action, entry_price in signals:
                if entry_price is None or float(entry_price) == 0:
                    continue

                # Find price 5 days later
                exit_row = db.execute(text("""
                    SELECT close FROM stock_prices
                    WHERE ticker = :ticker
                      AND timestamp >= :ts + INTERVAL '5 days'
                    ORDER BY timestamp ASC
                    LIMIT 1
                """), {"ticker": ticker, "ts": sig_ts}).fetchone()

                if not exit_row or exit_row[0] is None:
                    continue

                entry = float(entry_price)
                exit_p = float(exit_row[0])
                raw_return = (exit_p - entry) / entry  # long return
                if sig_action == "SELL":
                    raw_return = -raw_return  # short position flips sign
                returns.append(raw_return)

            if not returns:
                continue

            total_trades = len(returns)
            wins = sum(1 for r in returns if r > 0)
            win_rate = wins / total_trades
            avg_return = sum(returns) / total_trades * 100  # in percent

            # Sharpe Ratio (annualized, assuming 252 trading days, 5-day holding)
            periods_per_year = 252 / 5
            mean_r = sum(returns) / len(returns)
            variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
            std_r = math.sqrt(variance) if variance > 0 else 1e-9
            sharpe = (mean_r / std_r) * math.sqrt(periods_per_year)

            # Max Drawdown (peak-to-trough on cumulative equity curve)
            cumulative = 1.0
            peak = 1.0
            max_dd = 0.0
            for r in returns:
                cumulative *= (1 + r)
                if cumulative > peak:
                    peak = cumulative
                dd = (peak - cumulative) / peak
                if dd > max_dd:
                    max_dd = dd

            db.execute(text("""
                INSERT INTO backtest_results
                    (ticker, total_trades, win_rate, avg_return_pct, sharpe_ratio, max_drawdown_pct, last_computed)
                VALUES
                    (:ticker, :trades, :wr, :avg_ret, :sharpe, :max_dd, NOW())
                ON CONFLICT (ticker) DO UPDATE SET
                    total_trades     = EXCLUDED.total_trades,
                    win_rate         = EXCLUDED.win_rate,
                    avg_return_pct   = EXCLUDED.avg_return_pct,
                    sharpe_ratio     = EXCLUDED.sharpe_ratio,
                    max_drawdown_pct = EXCLUDED.max_drawdown_pct,
                    last_computed    = NOW()
            """), {
                "ticker": ticker,
                "trades": total_trades,
                "wr": round(win_rate, 4),
                "avg_ret": round(avg_return, 4),
                "sharpe": round(sharpe, 4),
                "max_dd": round(max_dd * 100, 4),
            })

            print(
                f"[Backtest] {ticker}: {total_trades} trades | "
                f"Win Rate: {win_rate*100:.1f}% | Sharpe: {sharpe:.2f} | "
                f"Avg Return: {avg_return:.2f}% | Max Drawdown: {max_dd*100:.2f}%"
            )

        db.commit()
        print("[Backtest] Completed.")

    except Exception as e:
        print(f"[Backtest] Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    run_backtest()
