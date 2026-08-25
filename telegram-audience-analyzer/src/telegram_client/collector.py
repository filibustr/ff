"""
Сборщик данных из Telegram каналов.
Собирает посты и комментарии из каналов/групп.
"""

import asyncio
from typing import List, Dict, Any, Optional
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatAdminRequiredError

from src.monitoring.logger import get_logger

logger = get_logger(__name__)


class Collector:
    """
    Класс для сбора данных из Telegram каналов.
    
    Атрибуты:
        client: TelegramClient для работы с API
    """
    
    def __init__(self, client: TelegramClient):
        """
        Инициализирует сборщик.
        
        Args:
            client: Авторизованный TelegramClient
        """
        self.client = client
    
    async def scrape_channel(
        self,
        channel_username: str,
        limit: int = 50,
        comments_limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Собирает посты и комментарии из канала.
        
        Args:
            channel_username: Username канала (без @)
            limit: Максимальное количество постов для сбора
            comments_limit: Максимальное количество комментариев на пост
        
        Returns:
            Список словарей с данными постов и комментариев
        """
        result = []
        
        try:
            # Получаем entity канала
            entity = await self.client.get_entity(channel_username)
            logger.info("Got channel entity", channel=channel_username, id=entity.id)
            
            # Получаем посты
            posts = await self.client.get_messages(entity, limit=limit)
            
            for post in posts:
                if not post.message:
                    continue
                
                post_data = {
                    'post_id': post.id,
                    'text': post.message,
                    'date': post.date.isoformat() if post.date else None,
                    'views': post.views or 0,
                    'replies': post.replies.replies if post.replies else 0,
                    'channel_username': channel_username,
                    'channel_title': getattr(entity, 'title', channel_username),
                    'comments': []
                }
                
                # Если есть комментарии, собираем их
                if post.replies and post.replies.replies > 0:
                    try:
                        comments = await self._get_comments(
                            entity, post, comments_limit
                        )
                        post_data['comments'] = comments
                    except Exception as e:
                        logger.warning(
                            "Failed to get comments",
                            post_id=post.id,
                            error=str(e)
                        )
                
                result.append(post_data)
                
                # Небольшая пауза между запросами
                await asyncio.sleep(0.5)
                
        except FloodWaitError as e:
            logger.warning("Flood wait", channel=channel_username, seconds=e.seconds)
            await asyncio.sleep(e.seconds + 5)
            return await self.scrape_channel(channel_username, limit, comments_limit)
            
        except ChatAdminRequiredError:
            logger.error("Chat admin required", channel=channel_username)
            return []
            
        except Exception as e:
            logger.error("Failed to scrape channel", channel=channel_username, error=str(e))
            return []
        
        logger.info(
            "Channel scraped",
            channel=channel_username,
            posts_count=len(result)
        )
        
        return result
    
    async def _get_comments(
        self,
        entity,
        post,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Получает комментарии к посту.
        
        Args:
            entity: Entity канала
            post: Пост
            limit: Максимальное количество комментариев
        
        Returns:
            Список комментариев
        """
        comments = []
        
        try:
            # Получаем комментарии через get_replies
            replies = await self.client.get_messages(
                entity,
                reply_to=post.id,
                limit=limit
            )
            
            for comment in replies:
                if not comment.message:
                    continue
                
                sender = await comment.get_sender()
                
                comment_data = {
                    'comment_id': comment.id,
                    'text': comment.message,
                    'date': comment.date.isoformat() if comment.date else None,
                    'user_id': sender.id if sender else None,
                    'username': sender.username if sender else None,
                    'first_name': getattr(sender, 'first_name', ''),
                    'last_name': getattr(sender, 'last_name', '')
                }
                
                comments.append(comment_data)
                
        except FloodWaitError as e:
            logger.warning("Flood wait in comments", seconds=e.seconds)
            await asyncio.sleep(e.seconds + 2)
            
        except Exception as e:
            logger.warning("Failed to get comments", error=str(e))
        
        return comments
    
    async def get_participants(
        self,
        channel_username: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Получает участников канала/группы.
        
        Args:
            channel_username: Username канала
            limit: Максимальное количество участников
        
        Returns:
            Список участников
        """
        participants = []
        
        try:
            entity = await self.client.get_entity(channel_username)
            
            async for user in self.client.iter_participants(entity, limit=limit):
                participant_data = {
                    'user_id': user.id,
                    'username': user.username,
                    'first_name': getattr(user, 'first_name', ''),
                    'last_name': getattr(user, 'last_name', ''),
                    'phone': getattr(user, 'phone', None)
                }
                participants.append(participant_data)
                
        except Exception as e:
            logger.error(
                "Failed to get participants",
                channel=channel_username,
                error=str(e)
            )
        
        return participants
