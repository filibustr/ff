"""
Модуль для работы с Telegram клиентом (Telethon).
Управление клиентами, сбор данных из каналов.
"""

from .client import get_client_for_user, create_client, disconnect_client
from .collector import Collector
from .audience_finder import AudienceFinder

__all__ = [
    'get_client_for_user',
    'create_client',
    'disconnect_client',
    'Collector',
    'AudienceFinder'
]
