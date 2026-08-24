"""
Поиск целевой аудитории в каналах.
Анализирует комментаторов и оценивает их интерес по ключевым словам.
"""

import asyncio
from typing import List, Dict, Any, Optional
from telethon import TelegramClient

from src.monitoring.logger import get_logger

logger = get_logger(__name__)


class AudienceFinder:
    """
    Класс для поиска целевой аудитории в каналах.
    
    Атрибуты:
        client: TelegramClient для работы с API
    """
    
    def __init__(self, client: TelegramClient):
        """
        Инициализирует поисковик аудитории.
        
        Args:
            client: Авторизованный TelegramClient
        """
        self.client = client
        self.collector = Collector(client)
    
    async def find_target_audience(
        self,
        channels: List[str],
        keywords: List[str],
        posts_limit: int = 50,
        comments_limit: int = 30,
        min_score: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Находит активных пользователей в каналах по ключевым словам.
        
        Args:
            channels: Список username каналов для анализа
            keywords: Список ключевых слов для оценки интереса
            posts_limit: Максимальное количество постов на канал
            comments_limit: Максимальное количество комментариев на пост
            min_score: Минимальный score для включения в результат
        
        Returns:
            Список найденных пользователей с данными
        """
        found_users = {}  # user_id -> данные пользователя
        
        logger.info(
            "Starting audience search",
            channels_count=len(channels),
            keywords_count=len(keywords)
        )
        
        for channel in channels:
            try:
                channel_users = await self._analyze_channel(
                    channel,
                    keywords,
                    posts_limit,
                    comments_limit,
                    min_score
                )
                
                # Объединяем результаты
                for user in channel_users:
                    user_id = user['user_id']
                    if user_id in found_users:
                        # Обновляем score и добавляем чат
                        found_users[user_id]['activity_score'] += user['activity_score']
                        if channel not in found_users[user_id]['chats']:
                            found_users[user_id]['chats'].append(channel)
                    else:
                        found_users[user_id] = user
                        
            except Exception as e:
                logger.error("Failed to analyze channel", channel=channel, error=str(e))
            
            # Пауза между каналами
            await asyncio.sleep(1)
        
        # Конвертируем в список и ограничиваем score максимум 100
        result = []
        for user in found_users.values():
            user['activity_score'] = min(user['activity_score'], 100)
            if user['activity_score'] > min_score:
                result.append(user)
        
        # Сортируем по score
        result.sort(key=lambda x: x['activity_score'], reverse=True)
        
        logger.info("Audience search completed", found_count=len(result))
        return result
    
    async def _analyze_channel(
        self,
        channel: str,
        keywords: List[str],
        posts_limit: int,
        comments_limit: int,
        min_score: int
    ) -> List[Dict[str, Any]]:
        """
        Анализирует один канал и находит активных пользователей.
        
        Args:
            channel: Username канала
            keywords: Ключевые слова
            posts_limit: Лимит постов
            comments_limit: Лимит комментариев
            min_score: Минимальный score
        
        Returns:
            Список пользователей из этого канала
        """
        users = {}
        
        # Собираем посты с комментариями
        posts_data = await self.collector.scrape_channel(
            channel,
            limit=posts_limit,
            comments_limit=comments_limit
        )
        
        # Получаем информацию о канале
        try:
            entity = await self.client.get_entity(channel)
            channel_title = getattr(entity, 'title', channel)
            chat_id = entity.id
        except Exception:
            channel_title = channel
            chat_id = 0
        
        # Анализируем комментарии
        for post in posts_data:
            for comment in post.get('comments', []):
                user_id = comment.get('user_id')
                if not user_id:
                    continue
                
                username = comment.get('username')
                if not username:
                    continue  # Пропускаем без username
                
                # Считаем score по ключевым словам
                comment_text = comment.get('text', '').lower()
                score = 0
                
                for keyword in keywords:
                    keyword_lower = keyword.lower()
                    count = comment_text.count(keyword_lower)
                    score += count * 20  # 20 баллов за каждое вхождение
                
                # Ограничиваем макс 100 за комментарий
                score = min(score, 100)
                
                if score >= min_score:
                    if user_id in users:
                        users[user_id]['activity_score'] += score
                    else:
                        users[user_id] = {
                            'user_id': user_id,
                            'username': username,
                            'full_name': f"{comment.get('first_name', '')} {comment.get('last_name', '')}".strip(),
                            'chat_id': chat_id,
                            'chat_title': channel_title,
                            'activity_score': score,
                            'interests': [],  # Заполняется при сегментации
                            'segment': 'ЦА',
                            'chats': [channel]
                        }
        
        return list(users.values())
    
    def calculate_keyword_score(self, text: str, keywords: List[str]) -> int:
        """
        Считает score текста по ключевым словам.
        
        Args:
            text: Текст для анализа
            keywords: Ключевые слова
        
        Returns:
            Score (макс 100)
        """
        text_lower = text.lower()
        score = 0
        
        for keyword in keywords:
            count = text_lower.count(keyword.lower())
            score += count * 20
        
        return min(score, 100)
