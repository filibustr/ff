"""
Модуль авторизации Telegram аккаунта через Telethon.
"""

import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

from monitoring.logger import get_logger

load_dotenv()

logger = get_logger(__name__)


def get_api_credentials() -> tuple:
    """
    Получает API credentials из переменных окружения.
    
    Returns:
        Кортеж (api_id, api_hash)
    
    Raises:
        ValueError: Если credentials не найдены
    """
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    
    if not api_id or not api_hash:
        raise ValueError(
            "TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть установлены в .env"
        )
    
    return int(api_id), api_hash


async def request_code(phone: str) -> TelegramClient:
    """
    Инициирует запрос кода подтверждения для телефона.
    
    Args:
        phone: Номер телефона в международном формате (например, +79991234567)
    
    Returns:
        Клиент Telethon ожидающий код подтверждения
    
    Raises:
        ValueError: Если номер телефона некорректен
    """
    api_id, api_hash = get_api_credentials()
    
    # Создаем клиента с пустой сессией
    client = TelegramClient(StringSession(), api_id, api_hash)
    
    # Подключаемся
    await client.connect()
    
    # Отправляем код
    try:
        await client.send_code_request(phone)
        logger.info("Code sent", phone=phone)
        return client
    except Exception as e:
        await client.disconnect()
        logger.error("Failed to send code", phone=phone, error=str(e))
        raise


async def sign_in(client: TelegramClient, phone: str, code: str) -> StringSession:
    """
    Выполняет вход с использованием кода подтверждения.
    
    Args:
        client: Клиент Telethon от request_code
        phone: Номер телефона
        code: Код подтверждения из Telegram
    
    Returns:
        StringSession для последующего использования
    
    Raises:
        Exception: Если код неверный или другая ошибка
    """
    try:
        # Пытаемся войти с кодом
        await client.sign_in(phone=phone, code=code)
        
        # Проверяем авторизацию
        if not await client.is_user_authorized():
            raise ValueError("Авторизация не удалась")
        
        # Получаем session string
        session_string = client.session.save()
        
        logger.info("User signed in successfully", phone=phone)
        return session_string
        
    except Exception as e:
        logger.error("Sign in failed", phone=phone, error=str(e))
        raise
    finally:
        await client.disconnect()


async def validate_session(session_string: str) -> bool:
    """
    Проверяет валидность session string.
    
    Args:
        session_string: Session string от Telethon
    
    Returns:
        True если сессия валидна
    """
    api_id, api_hash = get_api_credentials()
    
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    
    try:
        await client.connect()
        is_valid = await client.is_user_authorized()
        await client.disconnect()
        return is_valid
    except Exception:
        return False
