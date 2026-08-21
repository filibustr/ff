"""
Заглушка для обработчика рассылки.
"""

from telegram import Update
from telegram.ext import ContextTypes


async def broadcast_placeholder(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Заглушка для команды /broadcast.
    
    Args:
        update: Объект обновления
        context: Контекст бота
    """
    await update.message.reply_text(
        "📤 Рассылка доступна через меню бота.\n\n"
        "Используйте кнопки интерфейса для управления рассылкой."
    )
