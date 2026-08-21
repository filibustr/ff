"""
Модуль генерации сообщений с использованием OpenAI.
Создание персонализированных сообщений для каждого сегмента.
"""

import json
from typing import List, Dict, Any, Optional
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv
from ..monitoring.logger import get_logger
from ..monitoring.cost_tracker import CostTracker

load_dotenv()

logger = get_logger(__name__)


class MessageBuilder:
    """
    Класс для генерации сообщений через OpenAI.
    
    Атрибуты:
        client: AsyncOpenAI клиент
        model: Модель для использования
        cost_tracker: Трекер затрат
    """
    
    def __init__(self, api_key: str = None, model: str = "gpt-3.5-turbo"):
        """
        Инициализирует билдер сообщений.
        
        Args:
            api_key: OpenAI API ключ (если None, берется из окружения)
            model: Модель OpenAI для использования
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = model
        self.cost_tracker = CostTracker()
    
    async def generate(
        self,
        segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Генерирует сообщения для каждого сегмента.
        
        Args:
            segments: Список сегментов от AudienceSegmenter
        
        Returns:
            Список словарей {segment: name, text: ..., tokens_used}
        """
        result = []
        
        for segment in segments:
            try:
                message_data = await self._generate_for_segment(segment)
                result.append(message_data)
            except Exception as e:
                logger.error(
                    "Failed to generate message for segment",
                    segment=segment.get('name'),
                    error=str(e)
                )
                # Добавляем заглушку
                result.append({
                    'segment': segment.get('name', 'Неизвестный'),
                    'text': f"Привет! У нас есть предложение для вас.",
                    'tokens_used': 0,
                    'error': str(e)
                })
        
        logger.info("Message generation completed", count=len(result))
        return result
    
    async def _generate_for_segment(
        self,
        segment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Генерирует сообщение для одного сегмента.
        
        Args:
            segment: Данные сегмента
        
        Returns:
            Словарь с данными сообщения
        """
        name = segment.get('name', 'Аудитория')
        description = segment.get('description', '')
        keywords = segment.get('keywords', [])
        
        # Формируем промпт
        prompt = self._build_message_prompt(name, description, keywords)
        
        try:
            # Запрашиваем у OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты – опытный маркетолог, пишущий вовлекающие сообщения для Telegram."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=150
            )
            
            # Трекаем использование токенов
            usage = response.usage
            tokens_used = usage.prompt_tokens + usage.completion_tokens
            
            self.cost_tracker.record_usage(
                model=self.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                purpose="message_generation"
            )
            
            # Получаем текст
            text = response.choices[0].message.content.strip()
            
            # Очищаем от возможных кавычек
            text = text.strip('"\'')
            
            logger.info(
                "Message generated",
                segment=name,
                tokens=tokens_used
            )
            
            return {
                'segment': name,
                'text': text,
                'tokens_used': tokens_used,
                'keywords': keywords
            }
            
        except Exception as e:
            logger.error("Message generation failed", segment=name, error=str(e))
            raise
    
    def _build_message_prompt(
        self,
        name: str,
        description: str,
        keywords: List[str]
    ) -> str:
        """
        Строит промпт для генерации сообщения.
        
        Args:
            name: Название сегмента
            description: Описание интересов
            keywords: Ключевые слова
        
        Returns:
            Промпт для OpenAI
        """
        keywords_str = ', '.join(keywords[:5]) if keywords else 'тематические интересы'
        
        prompt = f"""Ты – опытный маркетолог. Напиши вовлекающее сообщение для аудитории Telegram, которая:

Сегмент: {name}
Интересы: {description}
Ключевые слова: {keywords_str}

Требования к сообщению:
1. Краткое (до 200 символов)
2. Использует соответствующий тон для этой аудитории
3. Содержит призыв к действию
4. Без эмодзи или с минимальным количеством (1-2)
5. На русском языке

Напиши ТОЛЬКО текст сообщения, без пояснений."""
        
        return prompt
    
    async def generate_custom(
        self,
        context: str,
        tone: str = "friendly",
        max_length: int = 200
    ) -> str:
        """
        Генерирует кастомное сообщение с заданными параметрами.
        
        Args:
            context: Контекст/тема сообщения
            tone: Тон сообщения (friendly, professional, casual)
            max_length: Максимальная длина
        
        Returns:
            Текст сообщения
        """
        prompt = f"""Напиши короткое сообщение для Telegram.

Контекст: {context}
Тон: {tone}
Максимальная длина: {max_length} символов

Напиши ТОЛЬКО текст сообщения на русском языке."""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты помогаешь писать сообщения для Telegram."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=100
            )
            
            usage = response.usage
            self.cost_tracker.record_usage(
                model=self.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                purpose="custom_message"
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("Custom message generation failed", error=str(e))
            return "Привет! У нас есть интересное предложение для вас."
