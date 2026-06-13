import numpy as np
import pandas as pd
from sqlalchemy import text
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

# Minimum confidence to trust the model — below this threshold return neutral 0.50
CONFIDENCE_THRESHOLD = 0.55
# Minimum rows required to train a meaningful model
MIN_ROWS_REQUIRED = 40


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineers a rich feature set from raw OHLCV + technical indicators.
    Features avoid any lookahead bias — all computed from past data only.
    """
    # ─── Core technicals ──────────────────────────────────────────────────────
    df["macd_spread"] = df["macd"] - df["macd_signal"]
    df["price_to_sma20"] = (df["close"] - df["sma_20"]) / df["sma_20"].replace(0, np.nan)
    df["price_to_sma50"] = (df["close"] - df["sma_50"]) / df["sma_50"].replace(0, np.nan)
    df["price_to_sma200"] = (df["close"] - df["sma_200"]) / df["sma_200"].replace(0, np.nan)
    df["atr_pct"] = df["atr"] / df["close"].replace(0, np.nan)

    # ─── Momentum (past N-day returns) ────────────────────────────────────────
    df["momentum_5d"] = df["close"].pct_change(5)
    df["momentum_10d"] = df["close"].pct_change(10)
    df["momentum_20d"] = df["close"].pct_change(20)

    # ─── Volatility proxy ─────────────────────────────────────────────────────
    df["rolling_std_10d"] = df["close"].pct_change().rolling(10).std()

    # ─── Volume ratio (current vs 20d average) ────────────────────────────────
    if "volume" in df.columns:
        avg_vol = df["volume"].rolling(20).mean().replace(0, np.nan)
        df["volume_ratio"] = df["volume"] / avg_vol
    else:
        df["volume_ratio"] = 1.0

    # ─── Bollinger Band position (0 = lower band, 1 = upper band) ─────────────
    rolling_mean = df["close"].rolling(20).mean()
    rolling_std = df["close"].rolling(20).std()
    upper_band = rolling_mean + 2 * rolling_std
    lower_band = rolling_mean - 2 * rolling_std
    band_width = (upper_band - lower_band).replace(0, np.nan)
    df["bb_position"] = (df["close"] - lower_band) / band_width

    # ─── Price velocity (1st derivative of price trend) ───────────────────────
    df["price_velocity"] = df["close"].diff(3) / df["close"].shift(3).replace(0, np.nan)

    # ─── SMA crossover signals ───────────────────────────────────────────────
    df["sma20_above_sma50"] = (df["sma_20"] > df["sma_50"]).astype(float)
    df["sma50_above_sma200"] = (df["sma_50"] > df["sma_200"]).astype(float)

    return df


def train_and_predict_direction(ticker: str, db) -> float:
    """
    Loads historical prices/technicals, trains a GradientBoostingClassifier
    using walk-forward temporal split, and returns the probability of the
    next close being higher than the current close.

    Returns 0.50 (neutral) if:
    - Not enough data
    - Model confidence is below CONFIDENCE_THRESHOLD
    - Any NaN in the final prediction features
    """
    query = text("""
        SELECT timestamp, close, open, high, low, volume,
               rsi, macd, macd_signal, sma_20, sma_50, sma_200, adx, atr
        FROM stock_prices
        WHERE ticker = :ticker AND close IS NOT NULL
        ORDER BY timestamp ASC
    """)
    rows = db.execute(query, {"ticker": ticker}).fetchall()

    if len(rows) < MIN_ROWS_REQUIRED:
        return 0.50

    df = pd.DataFrame(rows, columns=[
        "timestamp", "close", "open", "high", "low", "volume",
        "rsi", "macd", "macd_signal", "sma_20", "sma_50", "sma_200", "adx", "atr"
    ])

    # Cast all numeric columns from Decimal/object to float
    numeric_cols = ["close", "open", "high", "low", "volume",
                    "rsi", "macd", "macd_signal", "sma_20", "sma_50", "sma_200", "adx", "atr"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.ffill().bfill()

    # Build feature set
    df = _build_features(df)

    feature_cols = [
        "rsi", "macd_spread", "price_to_sma20", "price_to_sma50", "price_to_sma200",
        "adx", "atr_pct", "momentum_5d", "momentum_10d", "momentum_20d",
        "rolling_std_10d", "volume_ratio", "bb_position", "price_velocity",
        "sma20_above_sma50", "sma50_above_sma200"
    ]

    # Explicitly cast all feature columns to float64 to prevent object-type arrays in numpy/sklearn
    for col in feature_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)

    # Target: 1 if close tomorrow > close today
    df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)

    # Drop NaN rows (caused by rolling windows and shifts)
    df_clean = df.dropna(subset=feature_cols + ["target"])

    # Walk-Forward split: train on first 80%, test on last 20%
    split_idx = int(len(df_clean) * 0.80)
    train_data = df_clean.iloc[:split_idx]
    test_data = df_clean.iloc[split_idx:]
    # The last row of df (most recent, no future target) is for prediction
    pred_row = df.iloc[-1]

    if len(train_data) < 20:
        return 0.50

    X_train = train_data[feature_cols].values
    y_train = train_data["target"].values

    # Handle any remaining NaN in training features
    if np.isnan(X_train).any():
        X_train = np.nan_to_num(X_train, nan=0.0)

    # Scale features (GBM benefits from scaled inputs for numerical stability)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    # Train GradientBoostingClassifier
    model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_leaf=5,
        random_state=42
    )
    model.fit(X_train_scaled, y_train)

    # Evaluate validation metrics on test split
    acc, prec, rec, f1 = 0.5, 0.5, 0.5, 0.5
    X_test = test_data[feature_cols].values
    y_test = test_data["target"].values
    if len(X_test) > 0:
        if np.isnan(X_test).any():
            X_test = np.nan_to_num(X_test, nan=0.0)
        X_test_scaled = scaler.transform(X_test)
        y_pred = model.predict(X_test_scaled)
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        acc = float(accuracy_score(y_test, y_pred))
        prec = float(precision_score(y_test, y_pred, zero_division=0))
        rec = float(recall_score(y_test, y_pred, zero_division=0))
        f1 = float(f1_score(y_test, y_pred, zero_division=0))

    # Persist metrics to the database
    import json
    db.execute(text("""
        INSERT INTO ml_model_metrics (ticker, last_trained, accuracy, precision, recall, f1_score, total_samples, features_used)
        VALUES (:ticker, NOW(), :acc, :prec, :rec, :f1, :total_samples, :features)
        ON CONFLICT (ticker) DO UPDATE SET
            last_trained = EXCLUDED.last_trained,
            accuracy = EXCLUDED.accuracy,
            precision = EXCLUDED.precision,
            recall = EXCLUDED.recall,
            f1_score = EXCLUDED.f1_score,
            total_samples = EXCLUDED.total_samples,
            features_used = EXCLUDED.features_used
    """), {
        "ticker": ticker,
        "acc": acc,
        "prec": prec,
        "rec": rec,
        "f1": f1,
        "total_samples": len(df_clean),
        "features": json.dumps(feature_cols)
    })

    # Predict for the latest data point
    last_features = pred_row[feature_cols].values.reshape(1, -1)

    if np.isnan(last_features).any():
        return 0.50

    last_features_scaled = scaler.transform(last_features)
    proba = model.predict_proba(last_features_scaled)[0][1]

    # Apply confidence threshold — return neutral if model is uncertain
    if proba < CONFIDENCE_THRESHOLD and proba > (1.0 - CONFIDENCE_THRESHOLD):
        return 0.50

    return float(proba)
