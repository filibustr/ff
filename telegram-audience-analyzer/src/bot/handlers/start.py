"""
Обработчик команды /start.
Показывает главное меню бота.
"""

from telegram import Update
from telegram.ext import ContextTypes
from src.database.db_manager import DatabaseManager
from src.ui.menus import main_menu
from src.monitoring.logger import get_logger

logger = get_logger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /start.
    
    Args:
        update: Объект обновления
        context: Контекст бота
    """
    user_id = update.effective_user.id
    db: DatabaseManager = context.bot_data.get('db')
    
    logger.info("Start command", user_id=user_id)
    
    # Создаем пользователя если не существует
    if db:
        db.create_user(user_id)
    
    # Проверяем авторизацию
    auth = db.is_authorized(user_id) if db else False
    
    text = (
        "🤖 Добро пожаловать в Telegram Audience Analyzer!\n\n"
        "Этот бот поможет вам:\n"
        "• Анализировать каналы и группы\n"
        "• Находить активную целевую аудиторию\n"
        "• Сегментировать пользователей по интересам\n"
        "• Отправлять персонализированные сообщения\n\n"
    )
    
    if auth:
        text += "Ваш аккаунт уже подключен. Выберите действие:"
    else:
        text += "Для начала работы подключите ваш Telegram аккаунт.\n\n"
        text += "Нажмите «Подключить аккаунт» или отправьте /login"
    
    await update.message.reply_text(
        text,
        reply_markup=main_menu(auth=auth)
    )
