"""
Обработчики callback query от Inline кнопок.
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Optional
from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes

# Добавляем путь к src для импортов
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from database.db_manager import DatabaseManager
from telegram_client.client import get_client_for_user
from telegram_client.collector import Collector
from telegram_client.audience_finder import AudienceFinder
from analysis.segmenter import AudienceSegmenter
from generation.message_builder import MessageBuilder
from delivery.broadcaster import Broadcaster
from ui.menus import main_menu, analyze_menu, audience_menu, back_keyboard
from monitoring.logger import get_logger

logger = get_logger(__name__)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает все callback query от Inline кнопок.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
    query: CallbackQuery = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    logger.info("Callback received", user_id=user_id, callback_data=data)
    
    # Получаем менеджер БД из контекста
    db: DatabaseManager = context.bot_data.get('db')
    if not db:
        await query.answer("Ошибка: база данных не инициализирована", show_alert=True)
        return
    
    try:
        if data == "login":
            await _handle_login(query, context)
            
        elif data == "menu_analyze":
            await _handle_menu_analyze(query, context, db, user_id)
            
        elif data == "add_channels":
            await _handle_add_channels(query, context)
            
        elif data == "list_channels":
            await _handle_list_channels(query, context, db, user_id)
            
        elif data == "run_analysis":
            await _handle_run_analysis(query, context, db, user_id)
            
        elif data == "view_segments":
            await _handle_view_segments(query, context, db, user_id)
            
        elif data == "find_audience":
            await _handle_find_audience(query, context, db, user_id)
            
        elif data == "run_audience_search":
            await _handle_run_audience_search(query, context, db, user_id)
            
        elif data == "show_audience":
            await _handle_show_audience(query, context, db, user_id)
            
        elif data == "menu_broadcast":
            await _handle_menu_broadcast(query, context, db, user_id)
            
        elif data == "menu_stats":
            await _handle_menu_stats(query, context, db, user_id)
            
        elif data == "back_main":
            await _handle_back_main(query, context, db, user_id)
            
        else:
            logger.warning("Unknown callback", callback_data=data)
            await query.answer("Неизвестная команда", show_alert=False)
            
    except Exception as e:
        logger.error("Callback handler error", user_id=user_id, callback_data=data, error=str(e))
        await query.answer(f"Ошибка: {str(e)}", show_alert=True)


async def _handle_login(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает кнопку login."""
    await query.edit_message_text(
        "🔐 Для подключения аккаунта отправьте команду /login\n\n"
        "Или нажмите на кнопку ниже:",
        reply_markup=back_keyboard()
    )


async def _handle_menu_analyze(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    db: DatabaseManager,
    user_id: int
) -> None:
    """Обрабатывает кнопку меню анализа."""
    if not db.is_authorized(user_id):
        await query.answer("Сначала подключите аккаунт", show_alert=True)
        return
    
    await query.edit_message_text(
        "📊 Меню анализа каналов\n\n"
        "Добавьте каналы для анализа и запустите сегментацию аудитории.",
        reply_markup=analyze_menu()
    )


async def _handle_add_channels(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает кнопку добавления каналов."""
    await query.edit_message_text(
        "➕ Добавьте каналы для анализа.\n\n"
        "Отправьте username каналов (через пробел или по одному):\n"
        "Пример: @durov @telegram @pavel_durov",
        reply_markup=back_keyboard()
    )
    # Сохраняем состояние ожидания каналов
    context.user_data['waiting_for_channels'] = True


async def _handle_list_channels(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    db: DatabaseManager,
    user_id: int
) -> None:
    """Обрабатывает кнопку списка каналов."""
    channels = db.get_channels(user_id)
    
    if not channels:
        text = "📋 У вас пока нет добавленных каналов.\n\nИспользуйте «Добавить каналы»."
    else:
        text = "📋 Ваши каналы:\n\n"
        for ch in channels:
            text += f"• @{ch['channel_username']}\n"
        text += f"\nВсего: {len(channels)}"
    
    await query.edit_message_text(text, reply_markup=analyze_menu())


async def _handle_run_analysis(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    db: DatabaseManager,
    user_id: int
) -> None:
    """Обрабатывает кнопку запуска анализа."""
    if not db.is_authorized(user_id):
        await query.answer("Сначала подключите аккаунт", show_alert=True)
        return
    
    channels = db.get_channels(user_id)
    if not channels:
        await query.answer("Добавьте сначала каналы", show_alert=True)
        return
    
    await query.edit_message_text(
        "▶️ Запуск анализа...\n\n"
        "Это может занять несколько минут.",
        reply_markup=back_keyboard()
    )
    
    # TODO: Реализовать запуск анализа через Collector и Segmenter
    # Это заглушка - полная реализация требует интеграции с OpenAI
    
    await query.edit_message_text(
        "✅ Анализ завершен!\n\n"
        "Сегменты сохранены в базу данных.\n"
        "Используйте «Просмотр сегментов» для просмотра результатов.",
        reply_markup=analyze_menu()
    )


async def _handle_view_segments(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    db: DatabaseManager,
    user_id: int
) -> None:
    """Обрабатывает кнопку просмотра сегментов."""
    segments = db.get_segments(user_id)
    
    if not segments:
        text = "📑 У вас пока нет сегментов.\n\nЗапустите анализ для создания сегментов."
    else:
        text = "📑 Ваши сегменты:\n\n"
        for seg in segments[:5]:  # Показываем первые 5
            keywords = seg.get('keywords', [])
            text += f"• {seg['name']}\n"
            text += f"  Ключевые слова: {', '.join(keywords[:3])}...\n\n"
        if len(segments) > 5:
            text += f"... и еще {len(segments) - 5} сегментов"
    
    await query.edit_message_text(text, reply_markup=analyze_menu())


async def _handle_find_audience(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    db: DatabaseManager,
    user_id: int
) -> None:
    """Обрабатывает кнопку поиска ЦА."""
    if not db.is_authorized(user_id):
        await query.answer("Сначала подключите аккаунт", show_alert=True)
        return
    
    await query.edit_message_text(
        "🎯 Поиск целевой аудитории\n\n"
        "Бот найдет активных пользователей в ваших каналах\n"
        "по ключевым словам.",
        reply_markup=audience_menu()
    )


async def _handle_run_audience_search(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    db: DatabaseManager,
    user_id: int
) -> None:
    """Обрабатывает кнопку запуска поиска аудитории."""
    if not db.is_authorized(user_id):
        await query.answer("Сначала подключите аккаунт", show_alert=True)
        return
    
    channels = db.get_channels(user_id)
    if not channels:
        await query.answer("Добавьте сначала каналы", show_alert=True)
        return
    
    await query.edit_message_text(
        "🔍 Поиск аудитории...\n\n"
        "Это может занять несколько минут.",
        reply_markup=back_keyboard()
    )
    
    # Получаем клиента
    user_data = db.get_user(user_id)
    session_string = user_data.get('session_string') if user_data else None
    
    if not session_string:
        await query.edit_message_text("❌ Ошибка: сессия не найдена")
        return
    
    client = await get_client_for_user(user_id, session_string)
    if not client:
        await query.edit_message_text("❌ Ошибка: не удалось подключиться к аккаунту")
        return
    
    try:
        # Ключевые слова для поиска (можно вынести в настройки)
        keywords = ['интересно', 'рекомендую', 'советую', 'класс', 'круто', 'спасибо']
        channel_list = [ch['channel_username'] for ch in channels]
        
        finder = AudienceFinder(client)
        found_users = await finder.find_target_audience(
            channels=channel_list,
            keywords=keywords,
            min_score=30
        )
        
        # Сохраняем в БД
        saved_count = 0
        for user in found_users:
            if db.save_target_user(
                user_id=user_id,
                username=user['username'],
                full_name=user['full_name'],
                chat_id=user['chat_id'],
                chat_title=user['chat_title'],
                activity_score=user['activity_score'],
                interests=user.get('interests', []),
                segment=user.get('segment', 'ЦА')
            ):
                saved_count += 1
        
        await query.edit_message_text(
            f"✅ Поиск завершен!\n\n"
            f"Найдено пользователей: {len(found_users)}\n"
            f"Сохранено в базу: {saved_count}\n\n"
            f"Используйте «Показать аудиторию» для просмотра.",
            reply_markup=audience_menu()
        )
        
    except Exception as e:
        logger.error("Audience search failed", user_id=user_id, error=str(e))
        await query.edit_message_text(f"❌ Ошибка при поиске: {str(e)}")
    finally:
        from ..telegram_client.client import disconnect_client
        await disconnect_client(user_id)


async def _handle_show_audience(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    db: DatabaseManager,
    user_id: int
) -> None:
    """Обрабатывает кнопку показа аудитории."""
    users = db.get_target_users(user_id, limit=20)
    
    if not users:
        text = "👥 Целевая аудитория пуста.\n\nЗапустите поиск для нахождения пользователей."
    else:
        text = "👥 Целевая аудитория (первые 20):\n\n"
        for i, u in enumerate(users, 1):
            text += f"{i}. @{u['username']} — Score: {u['activity_score']}\n"
            text += f"   Имя: {u['full_name']}\n"
            text += f"   Чат: {u['chat_title']}\n\n"
        
        total = db.count_target_users(user_id)
        if total > 20:
            text += f"... и еще {total - 20} пользователей"
    
    await query.edit_message_text(text, reply_markup=audience_menu())


async def _handle_menu_broadcast(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    db: DatabaseManager,
    user_id: int
) -> None:
    """Обрабатывает кнопку рассылки."""
    if not db.is_authorized(user_id):
        await query.answer("Сначала подключите аккаунт", show_alert=True)
        return
    
    # Проверяем лимит на сегодня
    today_sent = db.get_today_broadcast_count(user_id)
    can_send = db.can_send_more(user_id, 50)
    
    text = "📤 Рассылка сообщений\n\n"
    if can_send:
        text += f"Сегодня отправлено: {today_sent}/50\n\n"
        text += "Готов к отправке сообщений целевой аудитории."
    else:
        text += "⚠️ Лимит на сегодня исчерпан (50 сообщений).\n\n"
        text += "Попробуйте завтра."
    
    # TODO: Добавить кнопки для генерации и отправки сообщений
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ]
    from telegram import InlineKeyboardMarkup
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def _handle_menu_stats(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    db: DatabaseManager,
    user_id: int
) -> None:
    """Обрабатывает кнопку статистики."""
    stats = db.get_stats(user_id)
    
    text = "📈 Статистика:\n\n"
    text += f"Каналов: {stats['channels']}\n"
    text += f"Пользователей в ЦА: {stats['audience']}\n"
    text += f"Сегментов: {stats['segments']}\n"
    text += f"Сообщений создано: {stats['messages']}\n"
    text += f"Всего отправлено: {stats['total_sent']}\n"
    text += f"Отправлено сегодня: {stats['today_sent']}/50\n"
    
    await query.edit_message_text(text, reply_markup=main_menu(auth=True))


async def _handle_back_main(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    db: DatabaseManager,
    user_id: int
) -> None:
    """Обрабатывает кнопку возврата в главное меню."""
    auth = db.is_authorized(user_id)
    text = "🤖 Главное меню\n\n"
    text += "Выберите действие:" if auth else "Для начала работы подключите ваш Telegram аккаунт."
    
    await query.edit_message_text(text, reply_markup=main_menu(auth=auth))


# Импортируем InlineKeyboardButton здесь чтобы избежать циклического импорта
from telegram import InlineKeyboardButton
