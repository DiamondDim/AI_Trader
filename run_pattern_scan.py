"""Scan MT5 history for patterns and export chart commands.

Usage:
  python run_pattern_scan.py --symbol EURUSD --timeframe H1 --bars 1000 \
      --output C:/path/to/terminal/MQL5/Files/AI_Trader_patterns.txt
"""
import argparse

from broker.mt5_connector import get_mt5_connector
from pattern_recognition.detector import PatternRecognitionEngine
from pattern_recognition.export import export_detections
from pattern_recognition.mt5_commands import export_mt5_commands


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--timeframe", default="H1")
    p.add_argument("--bars", type=int, default=1000)
    p.add_argument("--output", required=True)
    p.add_argument("--min-confidence", type=float, default=0.70)
    args = p.parse_args()

    connector = get_mt5_connector()
    if not connector.connected and not connector.connect():
        raise SystemExit("MT5 connection failed")
    df = connector.get_rates(args.symbol, args.timeframe, args.bars)
    if df.empty:
        raise SystemExit("No market data")

    engine = PatternRecognitionEngine(min_confidence=args.min_confidence)
    detections = engine.scan(df)
    export_mt5_commands(detections, args.output)
    export_detections(detections, str(args.output) + ".json")

    print(f"Bars: {len(df)}")
    print(f"Patterns: {len(detections)}")
    for d in detections:
        print(f"  {d.category:13} {d.name:28} {d.direction:7} conf={d.confidence:.2f} bars={d.start_index}:{d.end_index}")


if __name__ == "__main__":
    main()
