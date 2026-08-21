"""
Модуль анализа аудитории с использованием OpenAI.
Сегментация пользователей по интересам.
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


class AudienceSegmenter:
    """
    Класс для сегментации аудитории с помощью OpenAI.
    
    Атрибуты:
        client: AsyncOpenAI клиент
        model: Модель для использования
        cost_tracker: Трекер затрат
    """
    
    def __init__(self, api_key: str = None, model: str = "gpt-3.5-turbo"):
        """
        Инициализирует сегментер.
        
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
    
    async def segment(
        self,
        data: List[Dict[str, Any]],
        criteria: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Сегментирует аудиторию на основе данных постов.
        
        Args:
            data: Список постов с комментариями от Collector
            criteria: Критерии сегментации (словарь)
        
        Returns:
            Список сегментов с полями name, description, keywords, size, sample_text
        """
        # Извлекаем все тексты для анализа
        texts = []
        for post in data:
            # Текст поста
            if post.get('text'):
                texts.append({
                    'index': len(texts),
                    'text': post['text'],
                    'type': 'post'
                })
            
            # Тексты комментариев
            for comment in post.get('comments', []):
                if comment.get('text'):
                    texts.append({
                        'index': len(texts),
                        'text': comment['text'],
                        'type': 'comment',
                        'username': comment.get('username'),
                        'user_id': comment.get('user_id')
                    })
        
        if not texts:
            logger.warning("No texts to segment")
            return []
        
        # Формируем промпт
        prompt = self._build_segmentation_prompt(texts, criteria)
        
        try:
            # Запрашиваем у OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты – эксперт по анализу аудитории Telegram."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Трекаем использование токенов
            usage = response.usage
            self.cost_tracker.record_usage(
                model=self.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                purpose="audience_segmentation"
            )
            
            # Парсим ответ
            result_text = response.choices[0].message.content
            segments = self._parse_response(result_text)
            
            logger.info("Segmentation completed", segments_count=len(segments))
            return segments
            
        except Exception as e:
            logger.error("Segmentation failed", error=str(e))
            return []
    
    def _build_segmentation_prompt(
        self,
        texts: List[Dict],
        criteria: Optional[Dict] = None
    ) -> str:
        """
        Строит промпт для сегментации.
        
        Args:
            texts: Список текстов для анализа
            criteria: Дополнительные критерии
        
        Returns:
            Промпт для OpenAI
        """
        # Берем первые 50 текстов чтобы не превысить лимит токенов
        sample_texts = texts[:50]
        
        texts_formatted = ""
        for t in sample_texts:
            texts_formatted += f"[{t['index']}] ({t['type']}): {t['text'][:200]}\n\n"
        
        criteria_text = ""
        if criteria:
            criteria_text = f"\nДополнительные критерии: {json.dumps(criteria, ensure_ascii=False)}"
        
        prompt = f"""Ты – эксперт по анализу аудитории Telegram. У тебя есть набор постов и комментариев из нескольких каналов. Твоя задача – сгруппировать эти тексты по тематике так, чтобы каждая группа отражала интересы определённого сегмента аудитории.

Тексты для анализа:
{texts_formatted}
{criteria_text}

Для каждой группы дай:
1. Краткое название (на русском, до 5 слов)
2. Описание основных интересов (до 100 слов)
3. Ключевые слова (массив строк)
4. Список индексов текстов, попавших в группу

Верни ответ ТОЛЬКО в формате JSON-массива объектов со следующей структурой:
[
  {{
    "name": "Название сегмента",
    "description": "Описание интересов",
    "keywords": ["ключевое", "слово"],
    "indices": [0, 1, 2],
    "size": 3
  }}
]

Не добавляй никакого текста кроме JSON."""
        
        return prompt
    
    def _parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Парсит JSON ответ от OpenAI.
        
        Args:
            response_text: Текст ответа
        
        Returns:
            Список сегментов
        """
        try:
            # Пытаемся найти JSON в ответе
            start = response_text.find('[')
            end = response_text.rfind(']') + 1
            
            if start == -1 or end == -1:
                logger.warning("No JSON array found in response")
                return []
            
            json_str = response_text[start:end]
            segments = json.loads(json_str)
            
            # Нормализуем структуру
            result = []
            for seg in segments:
                result.append({
                    'name': seg.get('name', 'Неизвестный сегмент'),
                    'description': seg.get('description', ''),
                    'keywords': seg.get('keywords', []),
                    'indices': seg.get('indices', []),
                    'size': seg.get('size', len(seg.get('indices', [])))
                })
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response", error=str(e))
            return []
        except Exception as e:
            logger.error("Response parsing failed", error=str(e))
            return []
