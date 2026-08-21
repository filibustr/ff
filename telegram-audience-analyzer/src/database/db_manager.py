"""
Модуль работы с базой данных SQLite.
Все CRUD операции для пользователей, каналов, целевой аудитории и т.д.
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from .logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """
    Менеджер базы данных SQLite.
    
    Атрибуты:
        db_path: Путь к файлу базы данных
    """
    
    def __init__(self, db_path: str = "/data/bot.db"):
        """
        Инициализирует менеджер БД и создает таблицы если их нет.
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Создает и возвращает подключение к БД.
        
        Returns:
            sqlite3.Connection объект
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self) -> None:
        """Создает все необходимые таблицы в БД."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей (авторизованных в боте)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                session_string TEXT,
                is_authorized BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица каналов для анализа
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channel_username TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, channel_username)
            )
        ''')
        
        # Таблица целевой аудитории
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS target_audience (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                full_name TEXT,
                chat_id INTEGER,
                chat_title TEXT,
                activity_score INTEGER DEFAULT 0,
                segment TEXT DEFAULT 'ЦА',
                interests TEXT DEFAULT '[]',
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, username)
            )
        ''')
        
        # Таблица сегментов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                keywords TEXT DEFAULT '[]',
                size INTEGER DEFAULT 0,
                sample_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Таблица сообщений для рассылки
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                segment_id INTEGER,
                text TEXT NOT NULL,
                tokens_used INTEGER DEFAULT 0,
                is_sent BOOLEAN DEFAULT FALSE,
                sent_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (segment_id) REFERENCES segments(id)
            )
        ''')
        
        # Таблица истории рассылок (для ограничения 50 сообщений в день)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS broadcast_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                target_username TEXT,
                message_id INTEGER,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'sent',
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (message_id) REFERENCES messages(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized", db_path=str(self.db_path))
    
    # ========== Методы для работы с пользователями ==========
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает данные пользователя по ID.
        
        Args:
            user_id: Telegram ID пользователя
        
        Returns:
            Словарь с данными пользователя или None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def create_user(self, user_id: int) -> bool:
        """
        Создает нового пользователя.
        
        Args:
            user_id: Telegram ID пользователя
        
        Returns:
            True если пользователь создан, False если уже существует
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (user_id) VALUES (?)",
                (user_id,)
            )
            conn.commit()
            logger.info("User created", user_id=user_id)
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def update_session(self, user_id: int, session_string: str) -> bool:
        """
        Обновляет session string для пользователя.
        
        Args:
            user_id: Telegram ID пользователя
            session_string: Session string от Telethon
        
        Returns:
            True если успешно обновлено
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE users 
               SET session_string = ?, is_authorized = TRUE, updated_at = CURRENT_TIMESTAMP 
               WHERE user_id = ?""",
            (session_string, user_id)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        logger.info("Session updated", user_id=user_id, affected=affected)
        return affected > 0
    
    def is_authorized(self, user_id: int) -> bool:
        """
        Проверяет авторизован ли пользователь.
        
        Args:
            user_id: Telegram ID пользователя
        
        Returns:
            True если пользователь авторизован
        """
        user = self.get_user(user_id)
        return user is not None and user.get('is_authorized', False)
    
    # ========== Методы для работы с каналами ==========
    
    def add_channel(self, user_id: int, channel_username: str) -> bool:
        """
        Добавляет канал для анализа.
        
        Args:
            user_id: Telegram ID пользователя
            channel_username: Username канала (без @)
        
        Returns:
            True если канал добавлен, False если уже существует
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Нормализуем username (убираем @ если есть)
            channel_username = channel_username.lstrip('@')
            cursor.execute(
                "INSERT INTO channels (user_id, channel_username) VALUES (?, ?)",
                (user_id, channel_username)
            )
            conn.commit()
            logger.info("Channel added", user_id=user_id, channel=channel_username)
            return True
        except sqlite3.IntegrityError:
            logger.warning("Channel already exists", user_id=user_id, channel=channel_username)
            return False
        finally:
            conn.close()
    
    def get_channels(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получает список каналов пользователя.
        
        Args:
            user_id: Telegram ID пользователя
        
        Returns:
            Список словарей с данными каналов
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM channels WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def remove_channel(self, user_id: int, channel_username: str) -> bool:
        """
        Удаляет канал из списка.
        
        Args:
            user_id: Telegram ID пользователя
            channel_username: Username канала
        
        Returns:
            True если канал удален
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        channel_username = channel_username.lstrip('@')
        cursor.execute(
            "DELETE FROM channels WHERE user_id = ? AND channel_username = ?",
            (user_id, channel_username)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0
    
    # ========== Методы для работы с целевой аудиторией ==========
    
    def save_target_user(
        self,
        user_id: int,
        username: str,
        full_name: str,
        chat_id: int,
        chat_title: str,
        activity_score: int,
        interests: List[str] = None,
        segment: str = "ЦА"
    ) -> bool:
        """
        Сохраняет пользователя в целевую аудиторию.
        
        Args:
            user_id: ID владельца аккаунта
            username: Username найденного пользователя
            full_name: Полное имя
            chat_id: ID чата где найден
            chat_title: Название чата
            activity_score: Оценка активности
            interests: Список интересов
            segment: Сегмент
        
        Returns:
            True если сохранено успешно
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        interests_json = interests if interests else []
        
        try:
            cursor.execute(
                """INSERT OR REPLACE INTO target_audience 
                   (user_id, username, full_name, chat_id, chat_title, 
                    activity_score, interests, segment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, username, full_name, chat_id, chat_title,
                 activity_score, str(interests_json), segment)
            )
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error("Failed to save target user", error=str(e))
            return False
        finally:
            conn.close()
    
    def get_target_users(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
        min_score: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Получает список пользователей целевой аудитории.
        
        Args:
            user_id: ID владельца аккаунта
            limit: Максимальное количество записей
            offset: Смещение
            min_score: Минимальный score активности
        
        Returns:
            Список пользователей
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM target_audience 
               WHERE user_id = ? AND activity_score >= ?
               ORDER BY activity_score DESC
               LIMIT ? OFFSET ?""",
            (user_id, min_score, limit, offset)
        )
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            d = dict(row)
            # Парсим JSON interests
            try:
                import json
                d['interests'] = json.loads(d.get('interests', '[]'))
            except (json.JSONDecodeError, TypeError):
                d['interests'] = []
            result.append(d)
        
        return result
    
    def count_target_users(self, user_id: int) -> int:
        """
        Подсчитывает количество пользователей в целевой аудитории.
        
        Args:
            user_id: ID владельца аккаунта
        
        Returns:
            Количество пользователей
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM target_audience WHERE user_id = ?",
            (user_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    # ========== Методы для работы с сегментами ==========
    
    def save_segment(
        self,
        user_id: int,
        name: str,
        description: str = "",
        keywords: List[str] = None,
        size: int = 0,
        sample_text: str = ""
    ) -> int:
        """
        Сохраняет сегмент аудитории.
        
        Args:
            user_id: ID владельца аккаунта
            name: Название сегмента
            description: Описание
            keywords: Ключевые слова
            size: Размер сегмента
            sample_text: Пример текста
        
        Returns:
            ID созданного сегмента
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        keywords_json = keywords if keywords else []
        
        cursor.execute(
            """INSERT INTO segments 
               (user_id, name, description, keywords, size, sample_text)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, name, description, str(keywords_json), size, sample_text)
        )
        conn.commit()
        segment_id = cursor.lastrowid
        conn.close()
        
        logger.info("Segment saved", user_id=user_id, segment_id=segment_id, name=name)
        return segment_id
    
    def get_segments(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получает список сегментов пользователя.
        
        Args:
            user_id: ID владельца аккаунта
        
        Returns:
            Список сегментов
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM segments WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            d = dict(row)
            try:
                import json
                d['keywords'] = json.loads(d.get('keywords', '[]'))
            except (json.JSONDecodeError, TypeError):
                d['keywords'] = []
            result.append(d)
        
        return result
    
    # ========== Методы для работы с сообщениями ==========
    
    def save_message(
        self,
        segment_id: int,
        text: str,
        tokens_used: int = 0
    ) -> int:
        """
        Сохраняет сообщение для рассылки.
        
        Args:
            segment_id: ID сегмента
            text: Текст сообщения
            tokens_used: Количество использованных токенов
        
        Returns:
            ID созданного сообщения
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO messages (segment_id, text, tokens_used)
               VALUES (?, ?, ?)""",
            (segment_id, text, tokens_used)
        )
        conn.commit()
        message_id = cursor.lastrowid
        conn.close()
        
        logger.info("Message saved", segment_id=segment_id, message_id=message_id)
        return message_id
    
    def get_unsent_messages(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получает неотправленные сообщения для пользователя.
        
        Args:
            user_id: ID владельца аккаунта
        
        Returns:
            Список неотправленных сообщений
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT m.*, s.name as segment_name
               FROM messages m
               JOIN segments s ON m.segment_id = s.id
               WHERE s.user_id = ? AND m.is_sent = FALSE
               ORDER BY m.created_at ASC""",
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def mark_message_sent(self, message_id: int) -> None:
        """
        Отмечает сообщение как отправленное.
        
        Args:
            message_id: ID сообщения
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE messages 
               SET is_sent = TRUE, sent_count = sent_count + 1
               WHERE id = ?""",
            (message_id,)
        )
        conn.commit()
        conn.close()
    
    # ========== Методы для истории рассылок ==========
    
    def record_broadcast(
        self,
        user_id: int,
        target_username: str,
        message_id: int,
        status: str = "sent"
    ) -> None:
        """
        Записывает историю рассылки.
        
        Args:
            user_id: ID владельца аккаунта
            target_username: Username получателя
            message_id: ID сообщения
            status: Статус отправки
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO broadcast_history 
               (user_id, target_username, message_id, status)
               VALUES (?, ?, ?, ?)""",
            (user_id, target_username, message_id, status)
        )
        conn.commit()
        conn.close()
    
    def get_today_broadcast_count(self, user_id: int) -> int:
        """
        Подсчитывает количество сообщений отправленных сегодня.
        
        Args:
            user_id: ID владельца аккаунта
        
        Returns:
            Количество сообщений отправленных сегодня
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT COUNT(*) FROM broadcast_history 
               WHERE user_id = ? 
               AND DATE(sent_at) = DATE('now')""",
            (user_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def can_send_more(self, user_id: int, limit: int = 50) -> bool:
        """
        Проверяет можно ли еще отправлять сообщения сегодня.
        
        Args:
            user_id: ID владельца аккаунта
            limit: Лимит сообщений в день
        
        Returns:
            True если можно отправлять еще
        """
        today_count = self.get_today_broadcast_count(user_id)
        return today_count < limit
    
    # ========== Общая статистика ==========
    
    def get_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Получает общую статистику пользователя.
        
        Args:
            user_id: ID владельца аккаунта
        
        Returns:
            Словарь со статистикой
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Количество каналов
        cursor.execute("SELECT COUNT(*) FROM channels WHERE user_id = ?", (user_id,))
        channels_count = cursor.fetchone()[0]
        
        # Количество пользователей в ЦА
        cursor.execute("SELECT COUNT(*) FROM target_audience WHERE user_id = ?", (user_id,))
        audience_count = cursor.fetchone()[0]
        
        # Количество сегментов
        cursor.execute("SELECT COUNT(*) FROM segments WHERE user_id = ?", (user_id,))
        segments_count = cursor.fetchone()[0]
        
        # Количество сообщений
        cursor.execute("""
            SELECT COUNT(*), SUM(sent_count) 
            FROM messages m
            JOIN segments s ON m.segment_id = s.id
            WHERE s.user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        messages_count = row[0] or 0
        total_sent = row[1] or 0
        
        conn.close()
        
        return {
            'channels': channels_count,
            'audience': audience_count,
            'segments': segments_count,
            'messages': messages_count,
            'total_sent': total_sent,
            'today_sent': self.get_today_broadcast_count(user_id)
        }
