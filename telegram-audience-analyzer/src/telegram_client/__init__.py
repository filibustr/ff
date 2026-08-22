"""
Модуль для работы с Telegram клиентом (Telethon).
Управление клиентами, сбор данных из каналов.
"""

from telegram_client.client import get_client_for_user, create_client, disconnect_client
from telegram_client.collector import Collector
from telegram_client.audience_finder import AudienceFinder

__all__ = [
    'get_client_for_user',
    'create_client',
    'disconnect_client',
    'Collector',
    'AudienceFinder'
]
