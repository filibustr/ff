"""
Функции для создания Inline клавиатур.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional


def main_menu(auth: bool = False) -> InlineKeyboardMarkup:
    """
    Создает главное меню бота.
    
    Args:
        auth: Пользователь авторизован или нет
    
    Returns:
        InlineKeyboardMarkup с кнопками главного меню
    """
    keyboard = []
    
    if not auth:
        # Меню для неавторизованных
        keyboard.append([
            InlineKeyboardButton("🔐 Подключить аккаунт", callback_data="login")
        ])
    else:
        # Меню для авторизованных
        keyboard.append([
            InlineKeyboardButton("📊 Анализ каналов", callback_data="menu_analyze"),
            InlineKeyboardButton("🎯 Поиск ЦА", callback_data="find_audience")
        ])
        keyboard.append([
            InlineKeyboardButton("📤 Рассылка", callback_data="menu_broadcast"),
            InlineKeyboardButton("📈 Статистика", callback_data="menu_stats")
        ])
    
    return InlineKeyboardMarkup(keyboard)


def analyze_menu() -> InlineKeyboardMarkup:
    """
    Создает меню анализа каналов.
    
    Returns:
        InlineKeyboardMarkup с кнопками анализа
    """
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить каналы", callback_data="add_channels"),
            InlineKeyboardButton("📋 Список каналов", callback_data="list_channels")
        ],
        [
            InlineKeyboardButton("▶️ Запустить анализ", callback_data="run_analysis")
        ],
        [
            InlineKeyboardButton("📑 Просмотр сегментов", callback_data="view_segments")
        ],
        [
            InlineKeyboardButton("🔙 Назад", callback_data="back_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def audience_menu() -> InlineKeyboardMarkup:
    """
    Создает меню поиска целевой аудитории.
    
    Returns:
        InlineKeyboardMarkup с кнопками поиска ЦА
    """
    keyboard = [
        [
            InlineKeyboardButton("🔍 Найти аудиторию", callback_data="run_audience_search")
        ],
        [
            InlineKeyboardButton("👥 Показать аудиторию", callback_data="show_audience")
        ],
        [
            InlineKeyboardButton("🔙 Назад", callback_data="back_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def back_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой "Назад".
    
    Returns:
        InlineKeyboardMarkup с кнопкой назад
    """
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)
