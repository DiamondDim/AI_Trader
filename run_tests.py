"""Единый интерактивный launcher для тестовых runners проекта AI Trader."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "test_results"

TESTS = {
    "1": ("EMA Pullback", "run_ema_pullback_test.py"),
    "2": ("Fibonacci Pro", "run_fibonacci_pro_test.py"),
    "3": ("Intraday tests", "run_intraday_tests.py"),
    "4": ("Massive test", "run_massive_test.py"),
    "5": ("Massive test V2", "run_massive_test_v2.py"),
    "6": ("Interactive massive test", "run_massive_test_interactive.py"),
    "7": ("Optimization / top pairs", "optimize_top_pairs.py"),
}


def print_menu() -> None:
    print("\n" + "=" * 70)
    print("AI TRADER — TEST RUNNER")
    print("=" * 70)
    for key, (name, filename) in TESTS.items():
        print(f"{key}. {name:<28} [{filename}]")
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

    print(f"\n▶ Запуск: {filename}")
    print(f"📄 Результат: {output_file}")
    print("─" * 70)

    env = os.environ.copy()
    # Force UTF-8 for child Python processes so Unicode output works on Windows.
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        # One selected runner = one clean result file.
        # No launcher headers/footers are added: the file contains only
        # the actual stdout/stderr produced by the selected runner.
        with output_file.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [sys.executable, "-u", str(script)],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()

            return_code = process.wait()

        status = "✅ УСПЕШНО" if return_code == 0 else f"❌ ОШИБКА (код {return_code})"
        print(f"\n{status}")
        print(f"📄 Полный результат: {output_file}")
        return return_code

    except KeyboardInterrupt:
        print("\n\n⏹ Тест остановлен пользователем.")
        with output_file.open("a", encoding="utf-8") as log:
            log.write("\nТест остановлен пользователем.\n")
        return 130
    except Exception as exc:
        print(f"\n❌ Ошибка launcher: {exc}")
        with output_file.open("a", encoding="utf-8") as log:
            log.write(f"\nОшибка launcher: {exc}\n")
        return 1


def main() -> None:
    while True:
        print_menu()
        choice = input("Выберите тест: ").strip().lower()

        if choice == "q":
            print("Выход.")
            return

        test = TESTS.get(choice)
        if test is None:
            print("❌ Неверный выбор.")
            continue

        _, filename = test
        run_test(filename)
        input("\nНажмите Enter, чтобы вернуться в меню...")


if __name__ == "__main__":
    main()
