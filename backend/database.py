"""
Работа с SQLite базой данных панели
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Optional
from backend.config import PANEL_DB_PATH

def get_db_connection():
    """Получение соединения с БД"""
    # Убеждаемся, что директория существует
    PANEL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(PANEL_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Инициализация базы данных"""
    try:
        # Убеждаемся, что директория для БД существует
        PANEL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Таблица ботов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                bot_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'stopped',
                start_file TEXT,
                bot_dir TEXT NOT NULL,
                pid INTEGER,
                cpu_limit REAL DEFAULT 50.0,
                memory_limit INTEGER DEFAULT 512,
                db_name TEXT,
                git_repo_url TEXT,
                git_branch TEXT DEFAULT 'main',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    except Exception as e:
        # Логируем ошибку, но не прерываем выполнение
        import logging
        logging.error(f"Ошибка инициализации базы данных: {e}")
        raise

def create_bot(name: str, bot_type: str, start_file: str = None, 
               cpu_limit: float = 50.0, memory_limit: int = 512,
               git_repo_url: str = None, git_branch: str = "main") -> int:
    """Создание нового бота"""
    from backend.config import BOTS_DIR
    import os
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Создаем директорию для бота
    bot_dir = BOTS_DIR / f"bot_{name.lower().replace(' ', '_')}"
    bot_dir.mkdir(exist_ok=True)
    
    # Сохраняем конфиг бота
    config_path = bot_dir / "config.json"
    config = {
        "name": name,
        "bot_type": bot_type,
        "start_file": start_file,
        "cpu_limit": cpu_limit,
        "memory_limit": memory_limit,
        "git_repo_url": git_repo_url,
        "git_branch": git_branch
    }
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    # Создаем шаблонные файлы, если их нет и не указан Git репозиторий
    # (если указан репозиторий, файлы будут из него)
    if not git_repo_url and (not start_file or not (bot_dir / start_file).exists()):
        create_bot_templates(bot_dir, bot_type, start_file)
    
    cursor.execute("""
        INSERT INTO bots (name, bot_type, start_file, bot_dir, cpu_limit, memory_limit, git_repo_url, git_branch, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'stopped')
    """, (name, bot_type, start_file, str(bot_dir), cpu_limit, memory_limit, git_repo_url, git_branch))
    
    bot_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return bot_id

def get_bot(bot_id: int) -> Optional[Dict]:
    """Получение информации о боте"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def get_all_bots() -> List[Dict]:
    """Получение списка всех ботов"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM bots ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def update_bot(bot_id: int, **kwargs) -> bool:
    """Обновление информации о боте"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Фильтруем только допустимые поля
    allowed_fields = ['name', 'bot_type', 'start_file', 'cpu_limit', 'memory_limit', 
                     'status', 'pid', 'db_name', 'git_repo_url', 'git_branch']
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    if not updates:
        conn.close()
        return False
    
    # Обновляем конфиг файл если изменились настройки
    bot = get_bot(bot_id)
    if bot:
        config_path = Path(bot['bot_dir']) / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            config_updates = ['name', 'bot_type', 'start_file', 'cpu_limit', 'memory_limit', 'git_repo_url', 'git_branch']
            for field in config_updates:
                if field in updates:
                    config[field] = updates[field]
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
    
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    set_clause += ", updated_at = CURRENT_TIMESTAMP"
    values = list(updates.values()) + [bot_id]
    
    cursor.execute(f"UPDATE bots SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    
    return cursor.rowcount > 0

def delete_bot(bot_id: int) -> bool:
    """Удаление бота"""
    import shutil
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем информацию о боте
    bot = get_bot(bot_id)
    if not bot:
        conn.close()
        return False
    
    # Удаляем директорию бота
    bot_dir = Path(bot['bot_dir'])
    if bot_dir.exists():
        shutil.rmtree(bot_dir)
    
    # Удаляем из БД
    cursor.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
    conn.commit()
    conn.close()
    
    return cursor.rowcount > 0


def create_bot_templates(bot_dir: Path, bot_type: str, start_file: str = 'main.py'):
    """Создание шаблонных файлов для бота"""
    if bot_type == 'telegram':
        # Создаем main.py для Telegram
        main_file = bot_dir / start_file
        if not main_file.exists():
            main_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram бот - шаблон
Замените YOUR_BOT_TOKEN на токен вашего бота
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота (получите у @BotFather в Telegram)
BOT_TOKEN = "YOUR_BOT_TOKEN"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        'Привет! Я простой Telegram бот.\\n'
        'Доступные команды:\\n'
        '/start - Начать работу\\n'
        '/help - Показать справку'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text('Это простой Telegram бот-шаблон.')


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Эхо-обработчик - повторяет сообщение пользователя"""
    await update.message.reply_text(f'Вы написали: {update.message.text}')


def main():
    """Основная функция запуска бота"""
    # Удаляем переменные прокси из окружения для бота
    import os
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
    for var in proxy_vars:
        if var in os.environ:
            del os.environ[var]
    
    # Устанавливаем NO_PROXY для всех хостов
    os.environ['NO_PROXY'] = '*'
    
    logger.info(f"Прокси настройки очищены. NO_PROXY: {os.environ.get('NO_PROXY')}")
    
    # Создаем приложение без прокси
    # Используем proxy_url(None) для явного отключения прокси
    application = Application.builder().token(BOT_TOKEN).proxy_url(None).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Регистрируем обработчик текстовых сообщений (эхо)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Запускаем бота
    logger.info("Бот запущен и готов к работе")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
'''
            main_file.write_text(main_content, encoding='utf-8')
        
        # Создаем requirements.txt для Telegram
        requirements_file = bot_dir / "requirements.txt"
        if not requirements_file.exists():
            requirements_content = "python-telegram-bot==20.7\n"
            requirements_file.write_text(requirements_content, encoding='utf-8')
    
    elif bot_type == 'discord':
        # Создаем main.py для Discord
        main_file = bot_dir / start_file
        if not main_file.exists():
            main_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord бот - шаблон
Замените YOUR_BOT_TOKEN на токен вашего бота
"""

import discord
from discord.ext import commands
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Токен бота (получите на https://discord.com/developers/applications)
BOT_TOKEN = "YOUR_BOT_TOKEN"

# Намерения (intents) бота
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Создаем клиент бота
bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    """Вызывается когда бот готов к работе"""
    logger.info(f'{bot.user} подключился к Discord!')
    logger.info(f'Бот находится на {len(bot.guilds)} серверах')


@bot.command(name='hello')
async def hello(ctx):
    """Простая команда приветствия"""
    await ctx.send(f'Привет, {ctx.author.mention}!')


@bot.command(name='ping')
async def ping(ctx):
    """Проверка работы бота"""
    await ctx.send(f'Pong! Задержка: {round(bot.latency * 1000)}ms')


@bot.event
async def on_message(message):
    """Обработка всех сообщений"""
    # Игнорируем сообщения от ботов
    if message.author.bot:
        return
    
    # Обрабатываем команды
    await bot.process_commands(message)


def main():
    """Основная функция запуска бота"""
    try:
        bot.run(BOT_TOKEN)
    except discord.LoginFailure:
        logger.error("Неверный токен бота! Проверьте BOT_TOKEN")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")


if __name__ == '__main__':
    main()
'''
            main_file.write_text(main_content, encoding='utf-8')
        
        # Создаем requirements.txt для Discord
        requirements_file = bot_dir / "requirements.txt"
        if not requirements_file.exists():
            requirements_content = "discord.py==2.3.2\n"
            requirements_file.write_text(requirements_content, encoding='utf-8')

# Инициализируем БД при импорте
init_database()
