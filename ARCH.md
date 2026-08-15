# Структура проекта

---

``` bash
AI_Trader_Unified/
├── ARCH.md                # Архитектура и описание проекта (твой любимый формат!)
├── config/                # Настройки (settings.yaml или .env для MT5, риск-менеджмента, DEMO_MODE)
├── core/                  # Ядро (берем лучшее из pattern_recognition_engine)
│   ├── pattern_detector.py # Распознавание паттернов
│   ├── ml_models.py        # ML-классификация
│   └── backtesting.py      # Движок тестирования
├── broker/                # Исполнение ордеров (берем из ai-trader-mt5_0.1.1)
│   └── mt5_connector.py    # Подключение и управление ордерами в MT5
├── gui/                   # Графический интерфейс (из pattern_recognition_engine)
│   └── main_window.py      # Основное окно управления
├── utils/                 # Утилиты
│   ├── logger.py           # Надежное логирование (критично для демо-теста!)
│   └── helpers.py          # Вспомогательные функции
├── tests/                 # Тесты (для стабильности, как ты делаешь в Skypro)
├── main.py                # Точка входа (запуск GUI и основных потоков)
└── requirements.txt       # Актуальные зависимости
```
