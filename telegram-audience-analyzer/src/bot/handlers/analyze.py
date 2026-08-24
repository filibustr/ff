"""
Обработчик для добавления каналов.
Принимает текст с username каналов и сохраняет в БД.
"""

from telegram import Update
from telegram.ext import ContextTypes
from src.database.db_manager import DatabaseManager
from src.ui.menus import analyze_menu, back_keyboard
from src.monitoring.logger import get_logger

logger = get_logger(__name__)


async def channels_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Обрабатывает сообщение с username каналов.
    
    Args:
        update: Объект обновления
        context: Контекст бота
    """
    user_id = update.effective_user.id
    db: DatabaseManager = context.bot_data.get('db')
    
    # Проверяем ждем ли мы каналы
    if not context.user_data.get('waiting_for_channels'):
        return
    
    text = update.message.text.strip()
    logger.info("Channels received", user_id=user_id, channels_text=text)
    
    if not db:
        await update.message.reply_text("❌ Ошибка базы данных")
        context.user_data['waiting_for_channels'] = False
        return
    
    # Парсим username (разделители: пробел, запятая, новая строка)
    separators = [' ', ',', '\n', ';']
    usernames = [text]
    for sep in separators:
        new_usernames = []
        for u in usernames:
            new_usernames.extend(u.split(sep))
        usernames = new_usernames
    
    # Очищаем и нормализуем
    usernames = [
        u.strip().lstrip('@')
        for u in usernames
        if u.strip() and len(u.strip()) > 3
    ]
    
    if not usernames:
        await update.message.reply_text(
            "❌ Не найдено ни одного username.\n\n"
            "Отправьте username каналов через пробел:\n"
            "Пример: durov telegram pavel_durov",
            reply_markup=back_keyboard()
        )
        context.user_data['waiting_for_channels'] = False
        return
    
    # Сохраняем каналы
    added = 0
    already_exists = 0
    
    for username in usernames:
        if db.add_channel(user_id, username):
            added += 1
        else:
            already_exists += 1
    
    # Формируем ответ
    response = f"✅ Каналы обработаны:\n\n"
    response += f"Добавлено: {added}\n"
    if already_exists > 0:
        response += f"Уже существовало: {already_exists}\n"
    
    response += f"\nВсего каналов: {len(db.get_channels(user_id))}\n\n"
    response += "Добавить еще или используйте меню."
    
    await update.message.reply_text(
        response,
        reply_markup=analyze_menu()
    )
    
    # Сбрасываем флаг ожидания
    context.user_data['waiting_for_channels'] = False
