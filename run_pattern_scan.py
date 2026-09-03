import argparse
from pathlib import Path
from broker.mt5_connector import get_mt5_connector
from pattern_recognition.detector import PatternRecognitionEngine
from pattern_recognition.export import export_detections
from pattern_recognition.mt5_commands import export_mt5_commands

# ============================================================================
# КОНФИГУРАЦИЯ ПУТИ
# ============================================================================
# Папка Common\Files доступна всем терминалам MT5 на компьютере.
# Именно здесь советник PatternChartBridge.mq5 ищет файл с командами.
OUTPUT_DIR = Path(r"C:\Users\Dmitriy\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
DEFAULT_OUTPUT_FILE = "AI_Trader_patterns.txt"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--timeframe", default="H1")
    p.add_argument("--bars", type=int, default=1000)
    # Делаем output необязательным. Если не указан, берется дефолтный путь.
    p.add_argument("--output", type=str, default=None)
    p.add_argument("--min-confidence", type=float, default=0.60)

    args = p.parse_args()

    # Гарантируем существование целевой директории
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Формируем итоговый путь
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = OUTPUT_DIR / DEFAULT_OUTPUT_FILE

    connector = get_mt5_connector()
    if not connector.connected and not connector.connect():
        raise SystemExit("MT5 connection failed")

    df = connector.get_rates(args.symbol, args.timeframe, args.bars)
    if df.empty:
        raise SystemExit("No market data")

    engine = PatternRecognitionEngine(min_confidence=args.min_confidence)
    detections = engine.scan(df)

    # Экспорт команд для графика MT5
    export_mt5_commands(detections, output_path)

    # Экспорт JSON для анализа (сохраняется рядом с txt файлом)
    json_path = str(output_path) + ".json"
    export_detections(detections, json_path)

    print(f"\n✅ Сканирование завершено!")
    print(f"📊 Баров проанализировано: {len(df)}")
    print(f"🎯 Паттернов найдено: {len(detections)}")
    print(f"💾 Команды для MT5: {output_path}")
    print(f" Детальный отчет (JSON): {json_path}")

    print("\nНайденные паттерны:")
    for d in detections:
        print(f"  {d.category:13} {d.name:28} {d.direction:7} conf={d.confidence:.2f} bars={d.start_index}:{d.end_index}")

if __name__ == "__main__":
    main()
