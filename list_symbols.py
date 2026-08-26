# list_symbols.py
"""
Интерактивный скрипт для выбора валютных пар и запуска тестирования.
"""
import MetaTrader5 as mt5
import config
import sys
import subprocess

def get_available_symbols():
    """Получает список доступных форекс-пар из MT5."""
    if not mt5.initialize():
        print(f"❌ Ошибка инициализации MT5: {mt5.last_error()}")
        return []
    
    if not mt5.login(config.MT5_LOGIN, config.MT5_PASSWORD, config.MT5_SERVER):
        print(f"❌ Ошибка логина: {mt5.last_error()}")
        mt5.shutdown()
        return []
    
    print("✅ Подключение успешно!\n")
    
    all_symbols = mt5.symbols_get()
    
    # Фильтруем только форекс-пары
    major_currencies = ['EUR', 'USD', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD']
    forex_pairs = []
    
    for symbol in all_symbols:
        name = symbol.name
        if any(curr in name for curr in major_currencies):
            if not any(exclude in name for exclude in ['XAU', 'XAG', 'BTC', 'ETH', 'LTC']):
                forex_pairs.append({
                    'name': name,
                    'description': symbol.description,
                    'spread': symbol.spread,
                    'digits': symbol.digits,
                    'visible': symbol.visible
                })
    
    mt5.shutdown()
    return forex_pairs

def display_symbols(symbols):
    """Отображает нумерованный список символов."""
    print(f"📊 Найдено {len(symbols)} основных валютных пар:\n")
    print("="*70)
    print(f"{'№':<4} {'Символ':<15} {'Описание':<30} {'Спред':<10}")
    print("="*70)
    
    for i, pair in enumerate(symbols, 1):
        print(f"{i:<4} {pair['name']:<15} {pair['description']:<30} {pair['spread']:<10}")
    
    print("="*70)

def parse_selection(input_str, total_symbols):
    """
    Парсит ввод пользователя и возвращает список выбранных индексов.
    Поддерживает:
    - Одиночные номера: "1"
    - Несколько номеров через запятую: "1,3,5"
    - Диапазоны: "1-5"
    - Комбинации: "1,3,5-8"
    """
    selected_indices = []
    
    # Разбиваем по запятой
    parts = input_str.split(',')
    
    for part in parts:
        part = part.strip()
        
        # Проверяем диапазон
        if '-' in part:
            try:
                start, end = part.split('-')
                start = int(start.strip())
                end = int(end.strip())
                
                if 1 <= start <= total_symbols and 1 <= end <= total_symbols:
                    for i in range(start, end + 1):
                        if i not in selected_indices:
                            selected_indices.append(i)
                else:
                    print(f"️ Диапазон {start}-{end} выходит за пределы списка")
            except ValueError:
                print(f"⚠️ Неверный формат диапазона: {part}")
        else:
            # Одиночный номер
            try:
                num = int(part)
                if 1 <= num <= total_symbols:
                    if num not in selected_indices:
                        selected_indices.append(num)
                else:
                    print(f"⚠️ Номер {num} выходит за пределы списка (1-{total_symbols})")
            except ValueError:
                print(f"️ Неверный номер: {part}")
    
    return sorted(selected_indices)

def select_symbols(symbols):
    """Интерактивный выбор символов."""
    while True:
        print("\n🎯 Выберите одну или несколько пар для тестирования:")
        print("   Введите номера через запятую (например: 1,3,5)")
        print("   Или диапазон (например: 1-5)")
        print("   Или комбинацию (например: 1,3,5-8)")
        print("   Введите 'all' для выбора всех пар")
        print("   Введите 'q' для выхода\n")
        
        user_input = input("Ваш выбор: ").strip().lower()
        
        if user_input == 'q':
            print(" Выход из программы.")
            return []
        
        if user_input == 'all':
            print(f"✅ Выбраны все {len(symbols)} пар")
            return list(range(1, len(symbols) + 1))
        
        selected_indices = parse_selection(user_input, len(symbols))
        
        if selected_indices:
            print(f"\n✅ Выбрано {len(selected_indices)} пар:")
            for idx in selected_indices:
                print(f"   {idx}. {symbols[idx-1]['name']} - {symbols[idx-1]['description']}")
            
            confirm = input("\nПодтвердить выбор? (y/n): ").strip().lower()
            if confirm == 'y':
                return selected_indices
            else:
                print("❌ Выбор отменен. Попробуйте снова.\n")
        else:
            print("❌ Не выбрано ни одной пары. Попробуйте снова.\n")


def run_tests(selected_symbols):
    """Запускает тестирование для выбранных символов."""
    import os
    print(f"\n🚀 Запускаем тестирование для {len(selected_symbols)} пар...\n")

    # Копируем переменные окружения и включаем UTF-8 режим для Python
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'

    results = []

    for symbol in selected_symbols:
        print(f"\n{'=' * 70}")
        print(f"ТЕСТИРОВАНИЕ: {symbol}")
        print(f"{'=' * 70}")

        # Запускаем test_patterns.py с аргументом символа и UTF-8 окружением
        result = subprocess.run(
            [sys.executable, 'test_patterns.py', symbol],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env
        )

        print(result.stdout)

        if result.stderr:
            print(f"️ Ошибки: {result.stderr}")

        results.append({
            'symbol': symbol,
            'output': result.stdout,
            'returncode': result.returncode
        })

    # Сохраняем результаты в файл
    with open('test_results_selected_symbols.txt', 'w', encoding='utf-8') as f:
        f.write("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ВЫБРАННЫХ СИМВОЛОВ\n")
        f.write("=" * 70 + "\n\n")
        for res in results:
            f.write(f"\n{'=' * 70}\n")
            f.write(f"СИМВОЛ: {res['symbol']}\n")
            f.write(f"{'=' * 70}\n")
            f.write(res['output'])
            f.write("\n")

    print(f"\n✅ Все результаты сохранены в 'test_results_selected_symbols.txt'")

def main():
    print("🔍 Подключаемся к MT5 для получения списка символов...\n")
    
    symbols = get_available_symbols()
    
    if not symbols:
        print("❌ Не удалось получить список символов.")
        return
    
    # Отображаем список
    display_symbols(symbols)
    
    # Сохраняем список в файл
    with open('available_symbols.txt', 'w', encoding='utf-8') as f:
        f.write("Доступные валютные пары для торговли:\n\n")
        for i, pair in enumerate(symbols, 1):
            f.write(f"{i}. {pair['name']} - {pair['description']} (спред: {pair['spread']})\n")
    
    print(f"\n💾 Список сохранен в файл 'available_symbols.txt'")
    
    # Интерактивный выбор
    selected_indices = select_symbols(symbols)
    
    if not selected_indices:
        return
    
    # Извлекаем имена выбранных символов
    selected_symbols = [symbols[idx-1]['name'] for idx in selected_indices]
    
    # Запускаем тестирование
    run_tests(selected_symbols)

if __name__ == "__main__":
    main()
