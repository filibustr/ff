"""
Обработчики авторизации через ConversationHandler.
Запрашивают номер телефона и код подтверждения.
"""

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from database.db_manager import DatabaseManager
from auth.telegram_auth import request_code, sign_in
from ui.menus import main_menu, back_keyboard
from monitoring.logger import get_logger

logger = get_logger(__name__)

# Состояния для ConversationHandler
WAITING_FOR_PHONE = 1
WAITING_FOR_CODE = 2

# Хранилище клиентов по user_id
_auth_clients = {}


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Запрашивает номер телефона у пользователя.
    
    Args:
        update: Объект обновления
        context: Контекст бота
    
    Returns:
        Состояние WAITING_FOR_PHONE
    """
    user_id = update.effective_user.id
    logger.info("Login started", user_id=user_id)
    
    await update.message.reply_text(
        "🔐 Подключение Telegram аккаунта\n\n"
        "Отправьте ваш номер телефона в международном формате.\n"
        "Пример: +79991234567\n\n"
        "Или нажмите /cancel для отмены.",
        reply_markup=back_keyboard()
    )
    
    return WAITING_FOR_PHONE


async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Получает номер телефона и запрашивает код.
    
    Args:
        update: Объект обновления
        context: Контекст бота
    
    Returns:
        Состояние WAITING_FOR_CODE или CANCEL
    """
    user_id = update.effective_user.id
    phone = update.message.text.strip()
    
    # Простая валидация
    if not phone.startswith('+') or len(phone) < 10:
        await update.message.reply_text(
            "❌ Неверный формат номера.\n\n"
            "Номер должен начинаться с + и содержать код страны.\n"
            "Пример: +79991234567\n\n"
            "Попробуйте еще раз или /cancel для отмены."
        )
        return WAITING_FOR_PHONE
    
    logger.info("Phone received", user_id=user_id, phone=phone)
    
    try:
        # Запрашиваем код
        client = await request_code(phone)
        _auth_clients[user_id] = {'client': client, 'phone': phone}
        
        await update.message.reply_text(
            f"✅ Код отправлен на {phone}\n\n"
            "Проверьте Telegram и отправьте код подтверждения.\n\n"
            "Или /cancel для отмены."
        )
        
        return WAITING_FOR_CODE
        
    except Exception as e:
        logger.error("Failed to request code", user_id=user_id, error=str(e))
        await update.message.reply_text(
            f"❌ Ошибка при запросе кода: {str(e)}\n\n"
            "Попробуйте еще раз или /cancel."
        )
        return ConversationHandler.END


async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Получает код подтверждения и завершает авторизацию.
    
    Args:
        update: Объект обновления
        context: Контекст бота
    
    Returns:
        ConversationHandler.END
    """
    user_id = update.effective_user.id
    code = update.message.text.strip()
    db: DatabaseManager = context.bot_data.get('db')
    
    logger.info("Code received", user_id=user_id)
    
    # Проверяем есть ли клиент
    auth_data = _auth_clients.get(user_id)
    if not auth_data:
        await update.message.reply_text(
            "❌ Сессия истекла. Начните заново с /login"
        )
        return ConversationHandler.END
    
    client = auth_data['client']
    phone = auth_data['phone']
    
    try:
        # Выполняем вход
        session_string = await sign_in(client, phone, code)
        
        # Сохраняем сессию в БД
        if db:
            db.update_session(user_id, session_string)
        
        # Очищаем кэш
        del _auth_clients[user_id]
        
        logger.info("Authorization completed", user_id=user_id)
        
        await update.message.reply_text(
            "✅ Аккаунт успешно подключен!\n\n"
            "Теперь вы можете использовать все функции бота.",
            reply_markup=main_menu(auth=True)
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error("Sign in failed", user_id=user_id, error=str(e))
        await update.message.reply_text(
            f"❌ Ошибка авторизации: {str(e)}\n\n"
            "Проверьте код и попробуйте /login еще раз."
        )
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отменяет авторизацию.
    
    Args:
        update: Объект обновления
        context: Контекст бота
    
    Returns:
        ConversationHandler.END
    """
    user_id = update.effective_user.id
    logger.info("Login cancelled", user_id=user_id)
    
    # Очищаем кэш если есть
    if user_id in _auth_clients:
        client = _auth_clients[user_id]['client']
        try:
            await client.disconnect()
        except:
            pass
        del _auth_clients[user_id]
    
    await update.message.reply_text(
        "❌ Авторизация отменена.\n\n"
        "Используйте /login для начала или выберите действие в меню.",
        reply_markup=main_menu(auth=context.bot_data.get('db', {}).is_authorized(user_id) if context.bot_data.get('db') else False)
    )
    
    return ConversationHandler.END


def auth_conversation_handler() -> ConversationHandler:
    """
    Создает ConversationHandler для авторизации.
    
    Returns:
        ConversationHandler для процесса авторизации
    """
    return ConversationHandler(
        entry_points=[CommandHandler('login', get_phone)],
        states={
            WAITING_FOR_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)
            ],
            WAITING_FOR_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
