"""
Настройка структурированного логирования с использованием structlog.
Логи записываются в JSON формате в файл и консоль.
"""

import logging
import sys
import os
from pathlib import Path
import structlog
from structlog.types import Processor


def setup_logger(log_dir: str = "/data/logs") -> None:
    """
    Инициализирует структурированный логгер.
    
    Args:
        log_dir: Директория для хранения логов (по умолчанию /data/logs)
    """
    # Создаем директорию для логов, если она не существует
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Настраиваем базовый логгер
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
    
    # Добавляем файловый хендлер
    file_handler = logging.FileHandler(log_path / "bot.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    
    # Конфигурируем structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Получаем стандартный логгер и добавляем обработчики
    std_logger = logging.getLogger()
    std_logger.addHandler(file_handler)
    std_logger.setLevel(logging.DEBUG)


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """
    Возвращает инстанс логгера с указанным именем.
    
    Args:
        name: Имя логгера (обычно __name__ модуля)
    
    Returns:
        BoundLogger instance от structlog
    """
    return structlog.get_logger(name)
