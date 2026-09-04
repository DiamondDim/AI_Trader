# Pattern Recognition MT5 (experimental)

Изолированный исследовательский модуль. Ветка создана от `Dev_0_1_2`; существующие торговые стратегии не изменяются.

## Что реализовано

- свечные: Doji, Hammer, Shooting Star, Bullish/Bearish Engulfing, Morning/Evening Star;
- графические: Double Top/Bottom, Head & Shoulders, Inverse Head & Shoulders;
- гармонические: Gartley, Bat, Butterfly, Crab;
- продолжение: conservative Flag/Pennant detector;
- единая модель `PatternDetection`;
- подтвержденные swing points (`span=3`) без использования будущих баров после момента подтверждения;
- экспорт JSON для исследований;
- экспорт команд для MT5;
- `PatternChartBridge.mq5` — EA, который читает команды из `FILE_COMMON` и рисует линии паттернов на графике.

## Быстрый запуск

```text
python run_pattern_scan.py --symbol EURUSD --timeframe H1 --bars 1000 --output C:/Users/<USER>/AppData/Roaming/MetaQuotes/Terminal/Common/Files/AI_Trader_patterns.txt
```

После этого скомпилировать `pattern_recognition/PatternChartBridge.mq5` в MetaEditor, установить EA на нужный график и оставить `CommandFile=AI_Trader_patterns.txt`.

## Архитектурное правило

Распознавание не открывает сделки и не меняет Fibonacci Pro V2/Swing. Этот модуль пока является визуальным исследовательским слоем. Торговая интеграция будет отдельным этапом после проверки качества детекторов.
