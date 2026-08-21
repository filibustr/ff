"""
Основной модуль бота.
Инициализация приложения, регистрация обработчиков.
"""

import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from dotenv import load_dotenv

from ..database.db_manager import DatabaseManager
from ..ui.handlers import button_callback
from .handlers.start import start_handler
from .handlers.auth_handlers import auth_conversation_handler
from .handlers.analyze import channels_message_handler
from ..monitoring.logger import setup_logger, get_logger

load_dotenv()

logger = get_logger(__name__)


def create_application() -> Application:
    """
    Создает и настраивает приложение python-telegram-bot.
    
    Returns:
        Настроенное Application
    """
    # Настраиваем логгер
    setup_logger()
    
    # Получаем токен бота
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
    
    # Создаем приложение
    application = (
        Application.builder()
        .token(token)
        .build()
    )
    
    # Инициализируем БД и сохраняем в bot_data
    db = DatabaseManager()
    application.bot_data['db'] = db
    
    logger.info("Application created", db_path=db.db_path)
    
    return application


def register_handlers(application: Application) -> None:
    """
    Регистрирует все обработчики команд и callback.
    
    Args:
        application: Приложение для регистрации
    """
    # Команды
    application.add_handler(CommandHandler('start', start_handler))
    
    # ConversationHandler для авторизации
    application.add_handler(auth_conversation_handler())
    
    # Обработчик сообщений (для добавления каналов)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, channels_message_handler)
    )
    
    # Callback query от Inline кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("Handlers registered")


async def post_init(application: Application) -> None:
    """
    Выполняется после инициализации бота.
    
    Args:
        application: Приложение
    """
    logger.info("Bot initialized", username=application.bot.username)


async def post_shutdown(application: Application) -> None:
    """
    Выполняется после завершения работы бота.
    
    Args:
        application: Приложение
    """
    from ..telegram_client.client import disconnect_all_clients
    await disconnect_all_clients()
    logger.info("Bot shutdown complete")


def main() -> None:
    """
    Запускает бота.
    """
    logger.info("Starting bot...")
    
    # Создаем приложение
    application = create_application()
    
    # Регистрируем обработчики
    register_handlers(application)
    
    # Устанавливаем хуки жизненного цикла
    application.post_init = post_init
    application.post_shutdown = post_shutdown
    
    # Запускаем поллинг
    logger.info("Bot started successfully")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
