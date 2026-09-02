"""Единый интерактивный launcher тестового контура AI Trader."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "test_results"
TESTS = {
    "1": ("EMA Pullback", "run_ema_pullback_test.py"),
    "2": ("Fibonacci Pro (legacy)", "run_fibonacci_pro_test.py"),
    "3": ("Fibonacci Pro V2", "run_fibonacci_pro_v2_test.py"),
    "4": ("Swing", "run_swing_test.py"),
    "5": ("Intraday tests", "run_intraday_tests.py"),
    "6": ("Massive test", "run_massive_test.py"),
    "7": ("Massive test V2", "run_massive_test_v2.py"),
    "8": ("Interactive massive test", "run_massive_test_interactive.py"),
    "9": ("Optimization / top pairs", "optimize_top_pairs.py"),
}


def print_menu() -> None:
    print("\n" + "=" * 70)
    print("AI TRADER — TEST RUNNER")
    print("=" * 70)
    for key, (name, filename) in TESTS.items():
        print(f"{key}. {name:<30} [{filename}]")
    print("q. Выход")
    print("=" * 70)


def result_path(filename: str) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR / f"{Path(filename).stem}.txt"


def run_test(filename: str) -> int:
    script = ROOT / filename
    output_file = result_path(filename)
    if not script.is_file():
        message = f"ОШИБКА: runner не найден: {script}\n"
        output_file.write_text(message, encoding="utf-8")
        print(message, end="")
        return 2
    print(f"\n▶ Запуск: {filename}\n📄 Результат: {output_file}\n" + "─" * 70)
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
    try:
        with output_file.open("w", encoding="utf-8") as log:
            process = subprocess.Popen([sys.executable, "-u", str(script)], cwd=ROOT, env=env,
                                       stdin=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace", bufsize=1)
            assert process.stdout is not None
            while True:
                char = process.stdout.read(1)
                if char == "": break
                print(char, end="", flush=True); log.write(char); log.flush()
            return_code = process.wait()
        status = "✅ УСПЕШНО" if return_code == 0 else f"❌ ОШИБКА (код {return_code})"
        print(f"\n{status}\n📄 Полный результат: {output_file}")
        return return_code
    except KeyboardInterrupt:
        print("\n\n⏹ Тест остановлен пользователем.")
        with output_file.open("a", encoding="utf-8") as log: log.write("\nТест остановлен пользователем.\n")
        return 130
    except Exception as exc:
        print(f"\n❌ Ошибка launcher: {exc}")
        with output_file.open("a", encoding="utf-8") as log: log.write(f"\nОшибка launcher: {exc}\n")
        return 1


def main() -> None:
    while True:
        print_menu(); choice = input("Выберите тест: ").strip().lower()
        if choice == "q": print("Выход."); return
        if choice not in TESTS: print("❌ Неверный выбор."); continue
        run_test(TESTS[choice][1]); input("\nНажмите Enter, чтобы вернуться в меню...")


if __name__ == "__main__":
    main()
