import pandas as pd

from pattern_recognition.candlestick import detect_candlesticks
from pattern_recognition.detector import PatternRecognitionEngine
from pattern_recognition.mt5_commands import export_mt5_commands


def test_candlestick_engulfing_and_doji():
    idx = pd.date_range("2026-01-01", periods=4, freq="h")
    df = pd.DataFrame({
        "open": [100, 102, 98, 101],
        "high": [103, 103, 104, 102],
        "low": [99, 97, 97, 100],
        "close": [102, 98, 103, 101],
    }, index=idx)
    found = {d.name for d in detect_candlesticks(df)}
    assert "Bearish Engulfing" in found
    assert "Bullish Engulfing" in found


def test_engine_empty_dataframe():
    assert PatternRecognitionEngine().scan(pd.DataFrame()).__class__ is list


def test_mt5_command_export(tmp_path):
    idx = pd.date_range("2026-01-01", periods=2, freq="h")
    df = pd.DataFrame({"open":[100,98],"high":[101,103],"low":[97,97],"close":[98,102]}, index=idx)
    detection = detect_candlesticks(df)[-1]
    path = export_mt5_commands([detection], tmp_path / "patterns.txt")
    text = path.read_text(encoding="utf-8")
    assert "LINE|" in text
