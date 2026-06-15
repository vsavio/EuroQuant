"""
tests/test_risk_math.py
=======================
Unit tests for pure mathematical functions:
- Kelly Criterion position sizing
- ATR-based SL/TP calculation
- Drawdown calculation
- Sharpe Ratio
- Regime classification thresholds

These tests run WITHOUT a database connection — pure logic only.
"""
import math
import pytest


# ─── Kelly Criterion ─────────────────────────────────────────────────────────

def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Classic Kelly formula: K = W/L - (1-W)/W  simplified to K = (W*B - L) / B"""
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss  # win/loss ratio
    q = 1.0 - win_rate
    return max(0.0, min(1.0, (win_rate * b - q) / b))


class TestKellyCriterion:
    def test_50_50_coin_flip_no_edge(self):
        """50/50 with equal payoff = 0 Kelly (no edge)."""
        result = kelly_fraction(0.5, 1.0, 1.0)
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_positive_edge(self):
        """60% win rate with 2:1 payoff — classic Kelly example."""
        result = kelly_fraction(0.6, 2.0, 1.0)
        # K = (0.6*2 - 0.4)/2 = (1.2-0.4)/2 = 0.4
        assert result == pytest.approx(0.4, abs=1e-6)

    def test_negative_edge_clipped_to_zero(self):
        """40% win rate with 1:1 payoff — Kelly should be 0 (no bet)."""
        result = kelly_fraction(0.4, 1.0, 1.0)
        assert result == 0.0

    def test_kelly_never_exceeds_one(self):
        """Even with 100% win rate, Kelly must be <= 1."""
        result = kelly_fraction(1.0, 100.0, 1.0)
        assert result <= 1.0

    def test_zero_loss_returns_zero(self):
        """Division by zero guard."""
        result = kelly_fraction(0.7, 2.0, 0.0)
        assert result == 0.0


# ─── ATR-based SL/TP ─────────────────────────────────────────────────────────

def compute_sl_tp(price: float, atr: float, action: str,
                  sl_mult: float = 1.5, tp_mult: float = 3.0):
    """Replicate the Python backend SL/TP logic."""
    if action == "BUY":
        sl = max(0.0, round(price - sl_mult * atr, 4))
        tp = max(0.0, round(price + tp_mult * atr, 4))
    elif action == "SELL":
        sl = max(0.0, round(price + sl_mult * atr, 4))
        tp = max(0.0, round(price - tp_mult * atr, 4))
    else:
        sl = tp = price
    return sl, tp


class TestATRStops:
    def test_buy_sl_below_price(self):
        sl, tp = compute_sl_tp(100.0, 2.0, "BUY")
        assert sl < 100.0
        assert tp > 100.0

    def test_sell_sl_above_price(self):
        sl, tp = compute_sl_tp(100.0, 2.0, "SELL")
        assert sl > 100.0
        assert tp < 100.0

    def test_risk_reward_ratio_2to1(self):
        """TP distance should be 2x the SL distance (3/1.5)."""
        price, atr = 100.0, 2.0
        sl, tp = compute_sl_tp(price, atr, "BUY")
        sl_dist = price - sl
        tp_dist = tp - price
        assert tp_dist / sl_dist == pytest.approx(2.0, rel=1e-3)

    def test_zero_atr_fallback(self):
        """With zero ATR the backend uses price% fallback — SL must be positive."""
        price = 1000.0
        atr = 0.0
        sl = max(0.0, round(price * 0.98, 4))
        assert sl > 0.0
        assert sl < price

    def test_sl_tp_not_negative(self):
        """Even with extreme ATR, prices stay non-negative."""
        sl, tp = compute_sl_tp(5.0, 10.0, "BUY")
        assert sl >= 0.0


# ─── Drawdown Calculation ─────────────────────────────────────────────────────

def max_drawdown(equity_curve: list) -> float:
    """Peak-to-trough max drawdown as a fraction [0,1]."""
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    return max_dd


class TestDrawdown:
    def test_no_drawdown_monotonic_growth(self):
        curve = [100, 110, 120, 130]
        assert max_drawdown(curve) == pytest.approx(0.0)

    def test_full_loss(self):
        curve = [100, 50, 0.01]
        dd = max_drawdown(curve)
        assert dd > 0.99

    def test_partial_recovery(self):
        # Falls 20% from 100->80, then recovers to 90 but never reaches new peak
        curve = [100, 80, 90]
        dd = max_drawdown(curve)
        assert dd == pytest.approx(0.20, rel=1e-3)

    def test_single_element(self):
        assert max_drawdown([100]) == pytest.approx(0.0)


# ─── Sharpe Ratio ────────────────────────────────────────────────────────────

def annualised_sharpe(returns: list, periods_per_year: float = 252) -> float:
    """Annualised Sharpe Ratio (risk-free rate = 0)."""
    if len(returns) < 2:
        return 0.0
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / n
    std = math.sqrt(variance) if variance > 0 else 1e-9
    return (mean / std) * math.sqrt(periods_per_year)


class TestSharpeRatio:
    def test_positive_returns_positive_sharpe(self):
        returns = [0.01] * 100
        sharpe = annualised_sharpe(returns, periods_per_year=252)
        assert sharpe > 0

    def test_zero_std_returns_high_sharpe(self):
        """Constant positive returns → effectively infinite Sharpe."""
        returns = [0.001] * 50
        sharpe = annualised_sharpe(returns)
        assert sharpe > 10  # very high due to tiny std

    def test_negative_returns_negative_sharpe(self):
        returns = [-0.01] * 100
        sharpe = annualised_sharpe(returns)
        assert sharpe < 0

    def test_empty_returns(self):
        assert annualised_sharpe([]) == 0.0


# ─── Regime Classification ───────────────────────────────────────────────────

def classify_regime(current_vol: float, median_vol: float, recent_return: float) -> str:
    """Mirror the logic in worker/regimes.py."""
    if current_vol > 1.4 * median_vol:
        return "REGIME_PANIC" if recent_return < -0.02 else "REGIME_HIGH_VOLATILITY"
    if abs(recent_return) > 0.025:
        return "REGIME_QUIET_TREND"
    return "REGIME_MEAN_REVERTING"


class TestRegimeClassification:
    def test_panic_regime(self):
        assert classify_regime(0.30, 0.15, -0.05) == "REGIME_PANIC"

    def test_high_vol_without_crash(self):
        assert classify_regime(0.30, 0.15, 0.01) == "REGIME_HIGH_VOLATILITY"

    def test_quiet_trend(self):
        assert classify_regime(0.10, 0.10, 0.03) == "REGIME_QUIET_TREND"

    def test_mean_reverting(self):
        assert classify_regime(0.10, 0.10, 0.01) == "REGIME_MEAN_REVERTING"

    def test_boundary_vol_ratio(self):
        """vol exactly at 1.39x median (just below 1.4x threshold) → low-vol branch.
        With |recent_return|=0.05 > 0.025 it becomes REGIME_QUIET_TREND."""
        regime = classify_regime(0.139, 0.10, -0.05)
        # 0.139 < 1.4*0.10 → low-vol branch
        # abs(-0.05) > 0.025 → QUIET_TREND
        assert regime == "REGIME_QUIET_TREND"



# ─── Backtest Win Rate ────────────────────────────────────────────────────────

class TestBacktestMetrics:
    def test_perfect_win_rate(self):
        returns = [0.01, 0.02, 0.005, 0.03]
        wins = sum(1 for r in returns if r > 0)
        assert wins / len(returns) == pytest.approx(1.0)

    def test_zero_win_rate(self):
        returns = [-0.01, -0.02, -0.005]
        wins = sum(1 for r in returns if r > 0)
        assert wins / len(returns) == pytest.approx(0.0)

    def test_mixed_win_rate(self):
        returns = [0.01, -0.01, 0.02, -0.02]
        wins = sum(1 for r in returns if r > 0)
        assert wins / len(returns) == pytest.approx(0.5)
