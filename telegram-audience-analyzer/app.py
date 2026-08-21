"""
Точка входа приложения.
Импортирует и запускает бота.
"""

import sys
from pathlib import Path

# Добавляем src в путь для импортов
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from bot.main import main

if __name__ == '__main__':
    main()
