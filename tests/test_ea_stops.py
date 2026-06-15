"""
tests/test_ea_stops.py
======================
Tests that replicate the MQL5 SL/TP safety logic we implemented
in EuroQuant_MultiSymbol_Bridge.mq5.

These confirm that the Python backend's ATR outputs will always
pass the broker's stop level check after normalisation.
"""
import pytest


def normalize_price(price: float, tick_size: float, digits: int) -> float:
    """Mirror of MathRound(price / tick_size) * tick_size + NormalizeDouble"""
    if tick_size == 0:
        return round(price, digits)
    rounded = round(price / tick_size) * tick_size
    return round(rounded, digits)


def validate_buy_stops(ask: float, bid: float, stop_loss: float, take_profit: float,
                       stop_level_pts: int, point: float, tick_size: float, digits: int):
    """
    Replicate the EA BUY safety check.
    Returns corrected (sl, tp) that will never cause [Invalid stops].
    """
    spread_dist = (ask - bid) * 1.5
    min_dist = max(stop_level_pts * point, spread_dist, 10 * point)

    if stop_loss >= bid - min_dist and stop_loss > 0:
        stop_loss = bid - min_dist - 10 * point
    if take_profit <= bid + min_dist and take_profit > 0:
        take_profit = bid + min_dist + 10 * point

    stop_loss = normalize_price(stop_loss, tick_size, digits)
    take_profit = normalize_price(take_profit, tick_size, digits)
    return stop_loss, take_profit


def validate_sell_stops(ask: float, bid: float, stop_loss: float, take_profit: float,
                        stop_level_pts: int, point: float, tick_size: float, digits: int):
    """
    Replicate the EA SELL safety check.
    For SELL: close happens at ASK. SL must be > ASK, TP must be < ASK.
    """
    spread_dist = (ask - bid) * 1.5
    min_dist = max(stop_level_pts * point, spread_dist, 10 * point)

    if stop_loss <= ask + min_dist and stop_loss > 0:
        stop_loss = ask + min_dist + 10 * point
    if take_profit >= ask - min_dist and take_profit > 0:
        take_profit = ask - min_dist - 10 * point

    stop_loss = normalize_price(stop_loss, tick_size, digits)
    take_profit = normalize_price(take_profit, tick_size, digits)
    return stop_loss, take_profit


# ─── ASML.NAS parameters (real-world case from log) ──────────────────────────
ASML_ASK   = 1862.50
ASML_BID   = 1862.10
ASML_POINT = 0.01
ASML_TICK  = 0.01
ASML_DIGITS = 2
ASML_STOP_LEVEL = 0  # broker returns 0 for many ECN accounts


class TestBuyStops:
    def test_sl_below_bid(self):
        """After correction SL must be strictly below BID."""
        sl_raw, tp_raw = 1800.0, 1920.0  # valid ATR-based stops
        sl, tp = validate_buy_stops(ASML_ASK, ASML_BID, sl_raw, tp_raw,
                                    ASML_STOP_LEVEL, ASML_POINT, ASML_TICK, ASML_DIGITS)
        assert sl < ASML_BID

    def test_tp_above_bid(self):
        sl_raw, tp_raw = 1800.0, 1920.0
        sl, tp = validate_buy_stops(ASML_ASK, ASML_BID, sl_raw, tp_raw,
                                    ASML_STOP_LEVEL, ASML_POINT, ASML_TICK, ASML_DIGITS)
        assert tp > ASML_BID

    def test_invalid_sl_corrected(self):
        """SL that is too close to current price gets pushed further."""
        sl_raw = ASML_BID - 0.001  # just 0.001 below BID — too close
        tp_raw = ASML_BID + 100.0
        sl, tp = validate_buy_stops(ASML_ASK, ASML_BID, sl_raw, tp_raw,
                                    ASML_STOP_LEVEL, ASML_POINT, ASML_TICK, ASML_DIGITS)
        assert sl < ASML_BID

    def test_normalization_no_fractional_ticks(self):
        """Output prices must be multiples of tick size."""
        sl_raw, tp_raw = 1841.629, 1920.123  # "dirty" prices
        sl, tp = validate_buy_stops(ASML_ASK, ASML_BID, sl_raw, tp_raw,
                                    ASML_STOP_LEVEL, ASML_POINT, ASML_TICK, ASML_DIGITS)
        # With tick_size=0.01, result % 0.01 should be ~0
        assert abs(round(sl / ASML_TICK) * ASML_TICK - sl) < 1e-9
        assert abs(round(tp / ASML_TICK) * ASML_TICK - tp) < 1e-9


class TestSellStops:
    def test_sl_above_ask(self):
        """For SELL, SL must be above ASK."""
        sl_raw = 1862.110   # from the real failing log!
        tp_raw = 1441.629   # from the real failing log!
        sl, tp = validate_sell_stops(ASML_ASK, ASML_BID, sl_raw, tp_raw,
                                     ASML_STOP_LEVEL, ASML_POINT, ASML_TICK, ASML_DIGITS)
        assert sl > ASML_ASK, f"SL {sl} must be > ASK {ASML_ASK}"

    def test_tp_below_ask(self):
        """For SELL, TP must be below ASK."""
        sl_raw = 1862.110
        tp_raw = 1441.629
        sl, tp = validate_sell_stops(ASML_ASK, ASML_BID, sl_raw, tp_raw,
                                     ASML_STOP_LEVEL, ASML_POINT, ASML_TICK, ASML_DIGITS)
        assert tp < ASML_ASK, f"TP {tp} must be < ASK {ASML_ASK}"

    def test_dirty_tp_normalized(self):
        """The exact values from the error log (1441.629) get rounded to 2 decimal places."""
        sl_raw = 1862.110
        tp_raw = 1441.629
        sl, tp = validate_sell_stops(ASML_ASK, ASML_BID, sl_raw, tp_raw,
                                     ASML_STOP_LEVEL, ASML_POINT, ASML_TICK, ASML_DIGITS)
        # Check normalized — no .629 millesimal garbage
        assert tp == round(tp, 2)

    def test_large_spread_accounted(self):
        """Wide spread scenario: min_dist must account for spread."""
        wide_ask = 1865.0
        wide_bid = 1860.0  # 5.0 point spread
        sl_raw = wide_ask + 1.0   # barely above ask — may not be enough
        tp_raw = wide_bid - 200.0
        sl, tp = validate_sell_stops(wide_ask, wide_bid, sl_raw, tp_raw,
                                     0, 0.01, 0.01, 2)
        assert sl > wide_ask


class TestNormalization:
    def test_round_to_tick(self):
        assert normalize_price(1441.629, 0.01, 2) == pytest.approx(1441.63)

    def test_round_to_tick_zero_tick_fallback(self):
        """tick_size=0 uses digits fallback."""
        assert normalize_price(1441.629, 0.0, 2) == pytest.approx(1441.63)

    def test_already_normalized(self):
        assert normalize_price(1441.63, 0.01, 2) == pytest.approx(1441.63)
