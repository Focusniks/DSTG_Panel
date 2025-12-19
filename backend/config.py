"""
Конфигурация панели управления ботами
"""
import os
from pathlib import Path
import bcrypt

# Базовые пути
BASE_DIR = Path(__file__).parent.parent
BOTS_DIR = BASE_DIR / "bots"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
BOTS_DIR.mkdir(exist_ok=True)

# База данных панели
PANEL_DB_PATH = DATA_DIR / "panel.db"

# Файл для хранения хеша пароля администратора
ADMIN_PASSWORD_FILE = DATA_DIR / "admin_password.hash"

def get_admin_password_hash() -> str:
    """Получение хеша пароля администратора из файла или переменной окружения"""
    # Сначала проверяем переменную окружения
    env_hash = os.getenv("ADMIN_PASSWORD_HASH")
    if env_hash:
        return env_hash
    
    # Затем проверяем файл
    if ADMIN_PASSWORD_FILE.exists():
        try:
            with open(ADMIN_PASSWORD_FILE, 'r', encoding='utf-8') as f:
                stored_hash = f.read().strip()
                if stored_hash:
                    return stored_hash
        except Exception:
            pass
    
    # Если ничего не найдено, создаем дефолтный пароль "admin" и сохраняем его
    default_hash = bcrypt.hashpw("admin".encode(), bcrypt.gensalt()).decode()
    try:
        with open(ADMIN_PASSWORD_FILE, 'w', encoding='utf-8') as f:
            f.write(default_hash)
    except Exception:
        pass
    
    return default_hash

def set_admin_password_hash(new_password: str) -> bool:
    """Установка нового хеша пароля администратора"""
    try:
        new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        with open(ADMIN_PASSWORD_FILE, 'w', encoding='utf-8') as f:
            f.write(new_hash)
        return True
    except Exception:
        return False

# Пароль администратора (загружается из файла или переменной окружения)
ADMIN_PASSWORD_HASH = get_admin_password_hash()

# Настройки сессии
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
SESSION_COOKIE_NAME = "panel_session"
SESSION_COOKIE_MAX_AGE = 86400  # 24 часа

# Настройки MySQL для ботов
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_ROOT_USER = os.getenv("MYSQL_ROOT_USER", "root")
MYSQL_ROOT_PASSWORD = os.getenv("MYSQL_ROOT_PASSWORD", "")
MYSQL_PREFIX = os.getenv("MYSQL_PREFIX", "bot_")  # Префикс для имен БД ботов

# Настройки phpMyAdmin (опционально)
PHPMYADMIN_URL = os.getenv("PHPMYADMIN_URL", "http://localhost/phpmyadmin")

# Настройки панели
PANEL_HOST = os.getenv("PANEL_HOST", "0.0.0.0")
PANEL_PORT = int(os.getenv("PANEL_PORT", "8000"))

# Ресурсы по умолчанию для ботов
DEFAULT_CPU_LIMIT = float(os.getenv("DEFAULT_CPU_LIMIT", "50.0"))  # Процент CPU
DEFAULT_MEMORY_LIMIT = int(os.getenv("DEFAULT_MEMORY_LIMIT", "512"))  # MB RAM

