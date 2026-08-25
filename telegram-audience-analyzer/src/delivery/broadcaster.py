"""
Модуль доставки сообщений (рассылка).
Отправка сообщений пользователям через Telethon с паузами.
"""

import asyncio
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from src.monitoring.logger import get_logger

logger = get_logger(__name__)


class Broadcaster:
    """
    Класс для рассылки сообщений пользователям.
    
    Атрибуты:
        client: TelegramClient для отправки
        min_delay: Минимальная задержка между сообщениями (сек)
        max_delay: Максимальная задержка между сообщениями (сек)
    """
    
    def __init__(
        self,
        client: TelegramClient,
        min_delay: int = 30,
        max_delay: int = 120
    ):
        """
        Инициализирует броадкастер.
        
        Args:
            client: Авторизованный TelegramClient
            min_delay: Минимальная задержка в секундах
            max_delay: Максимальная задержка в секундах
        """
        self.client = client
        self.min_delay = min_delay
        self.max_delay = max_delay
    
    async def broadcast(
        self,
        users: List[Dict[str, Any]],
        message: str,
        user_id: int,
        db_manager=None,
        daily_limit: int = 50
    ) -> Dict[str, int]:
        """
        Отправляет сообщение всем пользователям из списка.
        
        Args:
            users: Список пользователей (с username или user_id)
            message: Текст сообщения для отправки
            user_id: ID владельца аккаунта (для проверки лимитов)
            db_manager: Менеджер БД для записи истории
            daily_limit: Лимит сообщений в день
        
        Returns:
            Словарь со статистикой: {total, success, errors, skipped}
        """
        stats = {
            'total': len(users),
            'success': 0,
            'errors': 0,
            'skipped': 0
        }
        
        logger.info(
            "Broadcast started",
            users_count=len(users),
            daily_limit=daily_limit
        )
        
        # Проверяем лимит на сегодня
        if db_manager:
            today_sent = db_manager.get_today_broadcast_count(user_id)
            if today_sent >= daily_limit:
                logger.warning("Daily limit reached", sent=today_sent)
                stats['skipped'] = len(users)
                return stats
        
        sent_today = db_manager.get_today_broadcast_count(user_id) if db_manager else 0
        
        for i, user in enumerate(users):
            # Проверяем дневной лимит
            if sent_today >= daily_limit:
                logger.info("Daily limit reached during broadcast", sent=sent_today)
                stats['skipped'] += len(users) - i
                break
            
            username = user.get('username')
            user_chat_id = user.get('user_id')
            
            if not username and not user_chat_id:
                logger.warning("No username or user_id", user=user)
                stats['errors'] += 1
                continue
            
            try:
                # Пытаемся отправить сообщение
                await self._send_message(username, user_chat_id, message)
                
                stats['success'] += 1
                sent_today += 1
                
                # Записываем в историю
                if db_manager:
                    db_manager.record_broadcast(
                        user_id=user_id,
                        target_username=username or str(user_chat_id),
                        message_id=0  # TODO: получить ID сообщения
                    )
                
                logger.info(
                    "Message sent",
                    username=username,
                    total_sent=sent_today
                )
                
            except FloodWaitError as e:
                logger.warning("Flood wait", seconds=e.seconds)
                await asyncio.sleep(e.seconds + 5)
                stats['errors'] += 1
                
            except Exception as e:
                error_name = type(e).__name__
                if 'Peer' in error_name or 'accessible' in str(e).lower():
                    logger.warning("Peer not accessible", username=username)
                else:
                    logger.error(
                        "Failed to send message",
                        username=username,
                        error=str(e)
                    )
                stats['errors'] += 1
            
            # Пауза между сообщениями (случайная)
            if i < len(users) - 1 and sent_today < daily_limit:
                delay = random.uniform(self.min_delay, self.max_delay)
                logger.debug("Waiting", delay=delay)
                await asyncio.sleep(delay)
        
        logger.info("Broadcast completed", stats=stats)
        return stats
    
    async def _send_message(
        self,
        username: Optional[str],
        user_chat_id: Optional[int],
        message: str
    ) -> None:
        """
        Отправляет сообщение одному пользователю.
        
        Args:
            username: Username пользователя
            user_chat_id: Chat ID пользователя
            message: Текст сообщения
        """
        # Определяем получателя
        if username:
            recipient = f"@{username}".lstrip('@')
        elif user_chat_id:
            recipient = user_chat_id
        else:
            raise ValueError("No username or user_id provided")
        
        # Отправляем сообщение
        await self.client.send_message(recipient, message)
    
    async def broadcast_with_personalization(
        self,
        users: List[Dict[str, Any]],
        base_message: str,
        user_id: int,
        db_manager=None,
        daily_limit: int = 50
    ) -> Dict[str, int]:
        """
        Отправляет персонализированные сообщения.
        
        Args:
            users: Список пользователей
            base_message: Шаблон сообщения (можно использовать {name})
            user_id: ID владельца аккаунта
            db_manager: Менеджер БД
            daily_limit: Дневной лимит
        
        Returns:
            Статистика отправки
        """
        stats = {
            'total': len(users),
            'success': 0,
            'errors': 0,
            'skipped': 0
        }
        
        if db_manager:
            today_sent = db_manager.get_today_broadcast_count(user_id)
            if today_sent >= daily_limit:
                stats['skipped'] = len(users)
                return stats
        
        sent_today = db_manager.get_today_broadcast_count(user_id) if db_manager else 0
        
        for i, user in enumerate(users):
            if sent_today >= daily_limit:
                stats['skipped'] += len(users) - i
                break
            
            try:
                # Персонализируем сообщение
                full_name = user.get('full_name', '')
                name = full_name.split()[0] if full_name else 'друг'
                
                personalized_message = base_message.replace('{name}', name)
                
                username = user.get('username')
                user_chat_id = user.get('user_id')
                
                await self._send_message(username, user_chat_id, personalized_message)
                
                stats['success'] += 1
                sent_today += 1
                
                if db_manager:
                    db_manager.record_broadcast(
                        user_id=user_id,
                        target_username=username or str(user_chat_id),
                        message_id=0
                    )
                
            except Exception as e:
                logger.error(
                    "Failed to send personalized message",
                    user=user.get('username'),
                    error=str(e)
                )
                stats['errors'] += 1
            
            if i < len(users) - 1 and sent_today < daily_limit:
                delay = random.uniform(self.min_delay, self.max_delay)
                await asyncio.sleep(delay)
        
        return stats
