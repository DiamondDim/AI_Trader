import sys
from loguru import logger
from pathlib import Path

# Создаем папку logs, если её нет
Path("logs").mkdir(exist_ok=True)

# Настраиваем красивый вывод в консоль
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)
# Настраиваем запись в файл для отладки
logger.add(
    "logs/trader.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG"
)

class LoggingMixin:
    """Миксин для удобного логирования в классах."""
    @property
    def logger(self):
        return logger.bind(module=self.__class__.__name__)

    def log_debug(self, message: str):
        self.logger.debug(message)

    def log_info(self, message: str):
        self.logger.info(message)

    def log_warning(self, message: str):
        self.logger.warning(message)

    def log_error(self, message: str):
        self.logger.error(message)
