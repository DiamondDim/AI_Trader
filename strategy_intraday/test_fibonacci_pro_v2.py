import numpy as np
import pandas as pd

from strategy_intraday.fibonacci_pro_v2 import (
    _calculate_fibonacci_levels,
    _find_structure,
    analyze_fibonacci_pro_signals,
    generate_fibonacci_pro_signals,
)


def _ohlc(values):
    index = pd.date_range("2026-01-05 10:00", periods=len(values), freq="h")
    close = pd.Series(values, index=index, dtype=float)
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close),
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
        },
        index=index,
    )


def test_fibonacci_levels_are_symmetric():
    levels = _calculate_fibonacci_levels(110.0, 100.0)
    assert levels["0.382"] == 103.82
    assert levels["0.5"] == 105.0
    assert levels["0.618"] == 106.18


def test_long_structure_requires_higher_low_and_higher_high():
    good = [(0, "L", 100.0), (1, "H", 108.0), (2, "L", 103.0), (3, "H", 110.0)]
    bad = [(0, "L", 100.0), (1, "H", 108.0), (2, "L", 99.0), (3, "H", 110.0)]
    assert _find_structure(good, "bullish") == (110.0, 103.0, 3, 2)
    assert _find_structure(bad, "bullish") is None


def test_short_structure_requires_lower_high_and_lower_low():
    good = [(0, "H", 110.0), (1, "L", 102.0), (2, "H", 107.0), (3, "L", 99.0)]
    bad = [(0, "H", 110.0), (1, "L", 102.0), (2, "H", 112.0), (3, "L", 99.0)]
    assert _find_structure(good, "bearish") == (107.0, 99.0, 2, 3)
    assert _find_structure(bad, "bearish") is None


def test_generator_handles_plain_ohlc_and_returns_diagnostics():
    rng = np.random.default_rng(7)
    returns = rng.normal(0.0, 0.25, 320)
    values = 100 + np.cumsum(returns)
    df = _ohlc(values)
    signals, diagnostics = analyze_fibonacci_pro_signals(df)

    assert isinstance(signals, list)
    assert diagnostics["bars_input"] == len(df)
    assert diagnostics["bars_evaluated"] > 0
    assert diagnostics["final_signals"] == len(signals)
    assert diagnostics["long_signals"] + diagnostics["short_signals"] == len(signals)


def test_optional_diagnostics_does_not_change_public_signal_api():
    df = _ohlc(np.linspace(100, 110, 160))
    diagnostics = {}
    signals = generate_fibonacci_pro_signals(df, diagnostics=diagnostics)
    assert isinstance(signals, list)
    assert diagnostics["bars_input"] == 160
    assert diagnostics["final_signals"] == len(signals)
