import pandas as pd

from core.indicators import Indicators
from core.risk import RiskCalculator
from core.backtesting import Backtester


class FakeConnector:
    def __init__(self, symbol_info):
        self.symbol_info = symbol_info

    def get_symbol_info(self, symbol):
        return self.symbol_info


def make_ohlc(rows=80):
    index = pd.date_range("2026-01-01", periods=rows, freq="h")
    close = pd.Series([100 + i * 0.05 for i in range(rows)], index=index)
    return pd.DataFrame({
        "open": close - 0.02,
        "high": close + 0.10,
        "low": close - 0.10,
        "close": close,
        "tick_volume": 1000,
        "spread": 10,
        "real_volume": 1000,
    }, index=index)


def test_standard_indicators_and_compatibility_alias():
    df = make_ohlc()
    Indicators().add_all(df)
    for column in ("ema_50", "ema_200", "atr_14", "stoch_k", "stoch_d", "adx_14", "adx"):
        assert column in df.columns
    pd.testing.assert_series_equal(df["adx_14"], df["adx"], check_names=False)


def test_risk_calculator_uses_tick_economics():
    info = {
        "point": 0.0001,
        "trade_tick_size": 0.00001,
        "trade_tick_value": 1.0,
        "volume_min": 0.01,
        "volume_max": 10.0,
        "volume_step": 0.01,
    }
    lot = RiskCalculator.lot_size(10000, 0.01, 1.1000, 1.0900, info)
    assert lot is not None
    assert lot > 0


def test_backtester_can_be_reused_without_state_leak():
    df = make_ohlc()
    Indicators().add_all(df)
    info = {
        "name": "TESTUSD",
        "point": 0.0001,
        "digits": 5,
        "trade_contract_size": 100000,
        "trade_tick_size": 0.0001,
        "trade_tick_value": 10.0,
        "spread": 2,
        "volume_min": 0.01,
        "volume_max": 10.0,
        "volume_step": 0.01,
    }
    connector = FakeConnector(info)
    bt = Backtester(initial_balance=10000, risk_per_trade=0.01)
    signals = [{"index": 10, "time": df.index[10], "type": "bullish", "pattern_name": "test"}]

    first = bt.run(df, connector, signals, "TESTUSD")
    second = bt.run(df, connector, signals, "TESTUSD")

    assert first["total_trades"] == second["total_trades"]
    assert first["final_balance"] == second["final_balance"]
    assert len(bt.trades) == first["total_trades"]
