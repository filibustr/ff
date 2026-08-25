"""
Трекер затрат на использование OpenAI API.
Записывает количество использованных токенов и их стоимость.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from .logger import get_logger

logger = get_logger(__name__)


class CostTracker:
    """
    Класс для отслеживания затрат на OpenAI API.
    
    Атрибуты:
        costs_file: Путь к файлу для хранения истории затрат
        rates: Словарь с ценами за 1K токенов для разных моделей
    """
    
    # Цены за 1000 токенов (на февраль 2024)
    RATES = {
        'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
        'gpt-4': {'input': 0.03, 'output': 0.06},
        'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
    }
    
    def __init__(self, data_dir: str = "/data"):
        """
        Инициализирует трекер затрат.
        
        Args:
            data_dir: Директория для хранения данных о затратах
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.costs_file = self.data_dir / "costs.json"
        self._load_costs()
    
    def _load_costs(self) -> None:
        """Загружает историю затрат из файла."""
        if self.costs_file.exists():
            try:
                with open(self.costs_file, 'r', encoding='utf-8') as f:
                    self.costs = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.costs = {'total': 0.0, 'records': []}
        else:
            self.costs = {'total': 0.0, 'records': []}
    
    def _save_costs(self) -> None:
        """Сохраняет историю затрат в файл."""
        try:
            with open(self.costs_file, 'w', encoding='utf-8') as f:
                json.dump(self.costs, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error("Failed to save costs", error=str(e))
    
    def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        purpose: str = ""
    ) -> float:
        """
        Записывает использование токенов и рассчитывает стоимость.
        
        Args:
            model: Название модели (например, 'gpt-3.5-turbo')
            prompt_tokens: Количество токенов во входном промпте
            completion_tokens: Количество токенов в ответе
            purpose: Цель использования (для логирования)
        
        Returns:
            Стоимость запроса в долларах
        """
        rate = self.RATES.get(model, self.RATES['gpt-3.5-turbo'])
        cost = (
            (prompt_tokens / 1000) * rate['input'] +
            (completion_tokens / 1000) * rate['output']
        )
        
        self.costs['total'] += cost
        self.costs['records'].append({
            'timestamp': datetime.now().isoformat(),
            'model': model,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'cost': cost,
            'purpose': purpose
        })
        
        # Сохраняем последние 1000 записей
        if len(self.costs['records']) > 1000:
            self.costs['records'] = self.costs['records'][-1000:]
        
        self._save_costs()
        
        logger.info(
            "OpenAI usage recorded",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            purpose=purpose
        )
        
        return cost
    
    def get_total_cost(self) -> float:
        """
        Возвращает общую сумму затрат.
        
        Returns:
            Общая стоимость в долларах
        """
        return self.costs['total']
    
    def get_stats(self, days: int = 7) -> Dict:
        """
        Возвращает статистику затрат за последние N дней.
        
        Args:
            days: Количество дней для статистики
        
        Returns:
            Словарь со статистикой
        """
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        recent_records = [
            r for r in self.costs['records']
            if datetime.fromisoformat(r['timestamp']).timestamp() > cutoff
        ]
        
        total_tokens = sum(
            r['prompt_tokens'] + r['completion_tokens']
            for r in recent_records
        )
        
        by_model = {}
        for r in recent_records:
            model = r['model']
            if model not in by_model:
                by_model[model] = {'cost': 0.0, 'tokens': 0}
            by_model[model]['cost'] += r['cost']
            by_model[model]['tokens'] += r['prompt_tokens'] + r['completion_tokens']
        
        return {
            'period_days': days,
            'total_cost': sum(r['cost'] for r in recent_records),
            'total_tokens': total_tokens,
            'requests_count': len(recent_records),
            'by_model': by_model
        }
