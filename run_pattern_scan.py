"""Interactive or CLI pattern scanner with MT5/JSON export."""

import argparse
import os
from pathlib import Path

import config
from broker.mt5_connector import get_mt5_connector
from pattern_recognition.detector import PatternRecognitionEngine
from pattern_recognition.export import export_detections
from pattern_recognition.mt5_commands import export_mt5_commands


def default_common_files_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "MetaQuotes" / "Terminal" / "Common" / "Files"
    return Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "Common" / "Files"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default=None)
    p.add_argument("--timeframe", default=None)
    p.add_argument("--bars", type=int, default=None)
    p.add_argument("--output", type=str, default=None)
    p.add_argument("--min-confidence", type=float, default=0.60)
    args = p.parse_args()

    symbol = args.symbol or input(f"Символ [{config.SYMBOL}]: ").strip() or config.SYMBOL
    timeframe = args.timeframe or input(f"Таймфрейм [{config.TIMEFRAME}]: ").strip().upper() or config.TIMEFRAME
    bars = args.bars or int(input("Количество баров [1000]: ").strip() or "1000")
    output_path = Path(args.output) if args.output else default_common_files_dir() / "AI_Trader_patterns.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    connector = get_mt5_connector()
    if not connector.connect(interactive=True):
        print("❌ MT5 connection failed"); return 1
    try:
        df = connector.get_rates(symbol, timeframe, bars)
        if df.empty:
            print("❌ No market data"); return 1
        detections = PatternRecognitionEngine(min_confidence=args.min_confidence).scan(df)
        export_mt5_commands(detections, output_path)
        json_path = Path(str(output_path) + ".json")
        export_detections(detections, str(json_path))
        print(f"\n✅ Сканирование завершено: баров={len(df)}, паттернов={len(detections)}")
        print(f"💾 MT5: {output_path}\n📄 JSON: {json_path}")
        for d in detections:
            print(f"  {d.category:13} {d.name:28} {d.direction:7} conf={d.confidence:.2f} bars={d.start_index}:{d.end_index}")
        return 0
    finally:
        connector.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
