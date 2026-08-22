"""
Модуль обработчиков бота.
"""

from bot.handlers.start import start_handler
from bot.handlers.auth_handlers import auth_conversation_handler, get_phone, get_code
from bot.handlers.analyze import channels_message_handler
from bot.handlers.broadcast import broadcast_placeholder

__all__ = [
    'start_handler',
    'auth_conversation_handler',
    'get_phone',
    'get_code',
    'channels_message_handler',
    'broadcast_placeholder'
]
