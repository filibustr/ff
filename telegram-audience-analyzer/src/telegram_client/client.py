"""
Управление Telegram клиентами Telethon.
Создание, кэширование и отключение клиентов.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Добавляем путь к src для импортов
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from src.monitoring.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

# Глобальный кэш клиентов
_clients_cache: Dict[int, TelegramClient] = {}


def get_api_credentials() -> tuple:
    """
    Получает API credentials из переменных окружения.
    
    Returns:
        Кортеж (api_id, api_hash)
    """
    api_id = int(os.getenv('TELEGRAM_API_ID', '0'))
    api_hash = os.getenv('TELEGRAM_API_HASH', '')
    return api_id, api_hash


def create_client(session_string: str) -> TelegramClient:
    """
    Создает нового клиента Telethon из session string.
    
    Args:
        session_string: Session string от Telethon
    
    Returns:
        Подключенный TelegramClient
    """
    api_id, api_hash = get_api_credentials()
    
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    return client


async def get_client_for_user(
    user_id: int,
    session_string: str,
    force_reconnect: bool = False
) -> Optional[TelegramClient]:
    """
    Получает или создает клиента для пользователя.
    
    Args:
        user_id: ID пользователя в боте
        session_string: Session string от Telethon
        force_reconnect: Принудительно переподключить
    
    Returns:
        TelegramClient или None если не удалось подключиться
    """
    # Проверяем кэш
    if user_id in _clients_cache and not force_reconnect:
        client = _clients_cache[user_id]
        if client.is_connected():
            logger.debug("Using cached client", user_id=user_id)
            return client
    
    # Создаем нового клиента
    try:
        client = create_client(session_string)
        await client.connect()
        
        if await client.is_user_authorized():
            _clients_cache[user_id] = client
            logger.info("Client created and authorized", user_id=user_id)
            return client
        else:
            logger.warning("Client not authorized", user_id=user_id)
            await client.disconnect()
            return None
            
    except Exception as e:
        logger.error("Failed to create client", user_id=user_id, error=str(e))
        return None


async def disconnect_client(user_id: int) -> bool:
    """
    Отключает и удаляет клиента из кэша.
    
    Args:
        user_id: ID пользователя
    
    Returns:
        True если клиент был отключен
    """
    if user_id in _clients_cache:
        client = _clients_cache[user_id]
        try:
            if client.is_connected():
                await client.disconnect()
            del _clients_cache[user_id]
            logger.info("Client disconnected", user_id=user_id)
            return True
        except Exception as e:
            logger.error("Failed to disconnect client", user_id=user_id, error=str(e))
            return False
    return False


async def disconnect_all_clients() -> None:
    """Отключает всех клиентов в кэше."""
    for user_id in list(_clients_cache.keys()):
        await disconnect_client(user_id)
    logger.info("All clients disconnected")
