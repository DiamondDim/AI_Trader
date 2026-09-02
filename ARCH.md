# AI Trader — архитектура

## Назначение
Проект — Python/MetaTrader 5 платформа для разработки, тестирования и последующего исполнения алгоритмических стратегий.

## Текущий контур

```text
MT5
 │
 ▼
broker/mt5_connector.py
 │
 ▼
core/data_provider.py ──► core/data_cache.py ──► cache/ (локально, не в Git)
 │
 ▼
core/indicators.py
 │
 ├── strategy_intraday/ema_pullback.py
 ├── strategy_intraday/fibonacci_pro.py        # legacy
 ├── strategy_intraday/fibonacci_pro_v2.py     # текущая структурная V2
 └── strategy_swing/swing.py                    # восстановлена из dev_010
 │
 ▼
core/backtesting.py
 │
 ▼
core/risk.py
```

## Принципы

1. **Сохранять контракт файлов.** `run_tests.py` остаётся единой точкой запуска тестов, а runners используют общий backtester.
2. **Одна реализация индикаторов.** Стратегии используют `core.indicators.Indicators`; локальные fallback-расчёты допустимы только для совместимости старых импортов.
3. **Cache-first данные.** Повторный тест должен брать OHLCV из локального кеша и обращаться к MT5 только при отсутствии/протухании данных или при явном refresh.
4. **Стратегии не зависят от хранения данных.** Они получают DataFrame и возвращают список сигналов.
5. **Fibonacci Pro V2 сохраняется как отдельная стратегия.** Её structural logic, diagnostics и текущие параметры не переписываются без отдельного этапа валидации результатов.
6. **Swing использует общий тестовый контур.** Исходная ветка `dev_010` содержала рабочую спецификацию в `strategy_swing/test_swing.py`, но не имела standalone engine; `strategy_swing/swing.py` является её восстановленной реализацией.
7. **История MT5 не хранится в Git.** Локальные `.pkl` файлы находятся в `cache/` и игнорируются.
8. **Сначала инфраструктура, потом оптимизация.** Изменения в общей экономике сделок, risk и backtester требуют отдельной проверки, чтобы не смешивать рефакторинг с изменением торговой логики.

## Запуск тестов

Главная точка входа:

```bash
python run_tests.py
```

Доступны отдельные тесты EMA, legacy Fibonacci, Fibonacci Pro V2, Swing, intraday и массовые runners.

## Стратегии

### Fibonacci Pro V2
Structure-first модель:
- confirmed pivots;
- HH/HL и LH/LL;
- EMA50/EMA200 trend;
- EMA slope;
- ADX/ATR regime;
- Fibonacci retracement;
- candle confirmation;
- stochastic filter;
- cooldown и защита от повторного structural swing;
- diagnostic rejection funnel.

### Swing
Сохранена логика `dev_010`:
- EMA50;
- ATR14;
- Stochastic 14/3/3;
- ADX > 20;
- BullishEngulfing, BearishEngulfing, Doji, Hammer;
- трендовый фильтр;
- stochastic-зоны;
- торговое окно 10:00–23:00 по принятой в проекте шкале времени.

## Неизменяемые ограничения

Не переносить бинарный MT5 cache из экспериментальных веток в основной Git history. Не менять рабочую V2 только ради «улучшения» метрик до появления отдельного сравнительного теста.
