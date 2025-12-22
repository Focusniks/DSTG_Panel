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
        
        # Таблица баз данных ботов (для поддержки нескольких БД на бота)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_databases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                db_name TEXT NOT NULL,
                db_user TEXT NOT NULL,
                db_password TEXT NOT NULL,
                db_host TEXT NOT NULL,
                db_port INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE,
                UNIQUE(bot_id, db_name)
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
    # Устанавливаем main.py по умолчанию, если start_file не указан
    if not start_file:
        start_file = 'main.py'
    """Создание нового бота"""
    from backend.config import BOTS_DIR
    import os
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Создаем директорию для бота
        # Очищаем имя от недопустимых символов
        safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in name.lower().replace(' ', '_'))
        if not safe_name:
            safe_name = "bot"
        bot_dir = BOTS_DIR / f"bot_{safe_name}"
        bot_dir.mkdir(parents=True, exist_ok=True)
        
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
            try:
                create_bot_templates(bot_dir, bot_type, start_file)
            except Exception as template_error:
                logger.warning(f"Failed to create bot templates: {template_error}")
                # Не критично, продолжаем создание бота
        
        cursor.execute("""
            INSERT INTO bots (name, bot_type, start_file, bot_dir, cpu_limit, memory_limit, git_repo_url, git_branch, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'stopped')
        """, (name, bot_type, start_file, str(bot_dir), cpu_limit, memory_limit, git_repo_url, git_branch))
        
        bot_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Bot created successfully: {name} (ID: {bot_id})")
        return bot_id
    except sqlite3.IntegrityError as e:
        logger.error(f"Database integrity error creating bot: {e}")
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        raise ValueError(f"Бот с таким именем уже существует: {name}")
    except Exception as e:
        logger.error(f"Error in create_bot: {e}", exc_info=True)
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        raise

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
Замените YOUR_BOT_TOKEN на токен вашего бота от @BotFather
"""

import logging
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('logs/bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Токен бота (получите у @BotFather в Telegram)
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

# Счетчик сообщений (пример использования контекста)
user_message_count = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    # Инициализируем счетчик для пользователя
    if user_id not in user_message_count:
        user_message_count[user_id] = 0
    
    welcome_text = f"Привет, {user.first_name}!\\n\\nЯ функциональный Telegram бот-шаблон.\\n\\nДоступные команды:\\n/start - Начать работу\\n/help - Показать справку\\n/info - Информация о боте\\n/stats - Статистика сообщений\\n/time - Текущее время\\n/echo <текст> - Повторить текст\\n\\nПросто отправьте мне любое сообщение, и я отвечу!"
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = "Справка по командам:\\n\\n/start - Начать работу с ботом\\n/help - Показать эту справку\\n/info - Информация о боте\\n/stats - Ваша статистика сообщений\\n/time - Текущее время и дата\\n/echo <текст> - Повторить ваш текст\\n\\nЭто шаблон бота для разработки. Вы можете добавить свои команды и функционал!"
    await update.message.reply_text(help_text)


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о боте"""
    bot_info = await context.bot.get_me()
    info_text = f"Информация о боте:\\n\\nИмя: {bot_info.first_name}\\nUsername: @{bot_info.username}\\nID: {bot_info.id}"
    await update.message.reply_text(info_text)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика сообщений пользователя"""
    user_id = update.effective_user.id
    count = user_message_count.get(user_id, 0)
    await update.message.reply_text(f'Вы отправили мне {count} сообщений!')


async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Текущее время"""
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await update.message.reply_text(f'Текущее время: {current_time}')


async def echo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /echo"""
    if context.args:
        text = ' '.join(context.args)
        await update.message.reply_text(f'Эхо: {text}')
    else:
        await update.message.reply_text('Использование: /echo <текст>')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех текстовых сообщений"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Увеличиваем счетчик
    user_message_count[user_id] = user_message_count.get(user_id, 0) + 1
    
    # Простой ответ на сообщение
    response = f'Вы написали: "{message_text}"\\n\\nЭто сообщение #{user_message_count[user_id]} от вас!'
    await update.message.reply_text(response)


def main():
    """Основная функция запуска бота"""
    # Удаляем переменные прокси из окружения для бота
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
    for var in proxy_vars:
        if var in os.environ:
            del os.environ[var]
    
    # Устанавливаем NO_PROXY для всех хостов
    os.environ['NO_PROXY'] = '*'
    
    # Создаем директорию для логов
    os.makedirs('logs', exist_ok=True)
    
    logger.info("Прокси настройки очищены. NO_PROXY: " + os.environ.get('NO_PROXY', 'не установлен'))
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN":
        logger.error("ВНИМАНИЕ: Установите токен бота в переменной BOT_TOKEN или в коде!")
        logger.error("Получите токен у @BotFather в Telegram")
        return
    
    # Создаем приложение без прокси
    application = Application.builder().token(BOT_TOKEN).proxy_url(None).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("echo", echo_command))

    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    logger.info("Бот запущен и готов к работе!")
    logger.info(f"Бот: @{application.bot.username}")
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
        
        # Создаем README для Telegram бота
        readme_file = bot_dir / "README.md"
        if not readme_file.exists():
            readme_content = '''# Telegram Bot Template

Это шаблон Telegram бота, созданный через DSTG Panel.

## Настройка

1. Получите токен бота у [@BotFather](https://t.me/BotFather) в Telegram
2. Замените `YOUR_BOT_TOKEN` в файле `main.py` на ваш токен
   ИЛИ установите переменную окружения `BOT_TOKEN`

## Функционал

- `/start` - Начать работу с ботом
- `/help` - Справка по командам
- `/info` - Информация о боте
- `/stats` - Статистика сообщений
- `/time` - Текущее время
- `/echo <текст>` - Повторить текст

## Запуск

Бот запускается автоматически через панель управления.

Для ручного запуска:
```bash
python main.py
```

## Зависимости

Все зависимости указаны в `requirements.txt` и устанавливаются автоматически при первом запуске.
'''
            readme_file.write_text(readme_content, encoding='utf-8')
    
    elif bot_type == 'discord':
        # Создаем main.py для Discord
        main_file = bot_dir / start_file
        if not main_file.exists():
            main_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord бот - шаблон
Замените YOUR_BOT_TOKEN на токен вашего бота
Получите токен на https://discord.com/developers/applications
"""

import discord
from discord.ext import commands
import logging
import os
from datetime import datetime

# Настройка логирования
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Токен бота (получите на https://discord.com/developers/applications)
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

# Намерения (intents) бота - необходимы для работы с сообщениями и участниками
intents = discord.Intents.default()
intents.message_content = True  # Для чтения содержимого сообщений
intents.members = True  # Для работы с участниками сервера

# Создаем клиент бота с префиксом команд '!'
bot = commands.Bot(command_prefix='!', intents=intents)

# Счетчик сообщений
message_count = {}


@bot.event
async def on_ready():
    """Вызывается когда бот готов к работе"""
    logger.info(f'{bot.user} подключился к Discord!')
    logger.info(f'Бот находится на {len(bot.guilds)} серверах')
    logger.info(f'Всего пользователей: {sum(guild.member_count for guild in bot.guilds)}')
    
    # Устанавливаем статус бота
    activity = discord.Game(name="!help для справки")
    await bot.change_presence(status=discord.Status.online, activity=activity)


@bot.event
async def on_message(message):
    """Обработка всех сообщений"""
    # Игнорируем сообщения от ботов
    if message.author.bot:
        return
    
    # Увеличиваем счетчик сообщений
    user_id = message.author.id
    message_count[user_id] = message_count.get(user_id, 0) + 1
    
    # Обрабатываем команды
    await bot.process_commands(message)


@bot.command(name='hello', aliases=['hi', 'привет'])
async def hello(ctx):
    """Простая команда приветствия"""
    await ctx.send(f'Привет, {ctx.author.mention}! Рад тебя видеть!')


@bot.command(name='ping')
async def ping(ctx):
    """Проверка работы бота и задержки"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="Pong!",
        description=f"Задержка: {latency}ms",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@bot.command(name='info', aliases=['инфо'])
async def info(ctx):
    """Информация о боте"""
    embed = discord.Embed(
        title="Информация о боте",
        color=discord.Color.blue()
    )
    embed.add_field(name="Имя", value=bot.user.name, inline=True)
    embed.add_field(name="ID", value=bot.user.id, inline=True)
    embed.add_field(name="Серверов", value=len(bot.guilds), inline=True)
    embed.add_field(name="Пользователей", value=sum(g.member_count for g in bot.guilds), inline=True)
    embed.add_field(name="Задержка", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    await ctx.send(embed=embed)


@bot.command(name='stats', aliases=['статистика'])
async def stats(ctx):
    """Статистика сообщений пользователя"""
    user_id = ctx.author.id
    count = message_count.get(user_id, 0)
    embed = discord.Embed(
        title="Ваша статистика",
        description=f"Вы отправили {count} сообщений на этом сервере!",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)


@bot.command(name='time', aliases=['время'])
async def time_command(ctx):
    """Текущее время"""
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    embed = discord.Embed(
        title="Текущее время",
        description=current_time,
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)


@bot.command(name='help_custom')
async def help_custom(ctx):
    """Расширенная справка по командам"""
    embed = discord.Embed(
        title="Справка по командам",
        description="Доступные команды бота:",
        color=discord.Color.cyan()
    )
    embed.add_field(
        name="!hello / !hi / !привет",
        value="Приветствие от бота",
        inline=False
    )
    embed.add_field(
        name="!ping",
        value="Проверка работы бота и задержки",
        inline=False
    )
    embed.add_field(
        name="!info / !инфо",
        value="Информация о боте",
        inline=False
    )
    embed.add_field(
        name="!stats / !статистика",
        value="Ваша статистика сообщений",
        inline=False
    )
    embed.add_field(
        name="!time / !время",
        value="Текущее время и дата",
        inline=False
    )
    embed.set_footer(text="Это шаблон бота для разработки. Добавьте свои команды!")
    await ctx.send(embed=embed)


@bot.event
async def on_command_error(ctx, error):
    """Обработка ошибок команд"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f'Команда не найдена! Используйте `!help_custom` для списка команд.')
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'Отсутствует обязательный аргумент! Проверьте синтаксис команды.')
    else:
        logger.error(f"Ошибка команды: {error}")
        await ctx.send(f'Произошла ошибка: {error}')


def main():
    """Основная функция запуска бота"""
    if BOT_TOKEN == "YOUR_BOT_TOKEN":
        logger.error("ВНИМАНИЕ: Установите токен бота в переменной BOT_TOKEN или в коде!")
        logger.error("Получите токен на https://discord.com/developers/applications")
        logger.error("Не забудьте включить необходимые intents в настройках приложения!")
        return
    
    try:
        logger.info("Запуск Discord бота...")
        bot.run(BOT_TOKEN)
    except discord.LoginFailure:
        logger.error("Неверный токен бота! Проверьте BOT_TOKEN")
    except discord.PrivilegedIntentsRequired:
        logger.error("Необходимые привилегированные intents не включены!")
        logger.error("Включите их на https://discord.com/developers/applications")
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
        
        # Создаем README для Discord бота
        readme_file = bot_dir / "README.md"
        if not readme_file.exists():
            readme_content = '''# Discord Bot Template

Это шаблон Discord бота, созданный через DSTG Panel.

## Настройка

1. Создайте приложение на [Discord Developer Portal](https://discord.com/developers/applications)
2. Создайте бота в разделе "Bot"
3. Скопируйте токен бота
4. Замените `YOUR_BOT_TOKEN` в файле `main.py` на ваш токен
   ИЛИ установите переменную окружения `BOT_TOKEN`

## Важно: Intents

В настройках бота на Discord Developer Portal включите:
- MESSAGE CONTENT INTENT (для чтения содержимого сообщений)
- SERVER MEMBERS INTENT (для работы с участниками)

Без этих intents бот не сможет работать правильно!

## Функционал

- `!hello` / `!hi` / `!привет` - Приветствие
- `!ping` - Проверка работы бота
- `!info` / `!инфо` - Информация о боте
- `!stats` / `!статистика` - Статистика сообщений
- `!time` / `!время` - Текущее время
- `!help_custom` - Расширенная справка

## Приглашение бота на сервер

1. Перейдите в раздел "OAuth2" → "URL Generator"
2. Выберите scope: `bot`
3. Выберите permissions: `Send Messages`, `Read Message History`, `Use Slash Commands`
4. Скопируйте сгенерированный URL и откройте в браузере
5. Выберите сервер и авторизуйте бота

## Запуск

Бот запускается автоматически через панель управления.

Для ручного запуска:
```bash
python main.py
```

## Зависимости

Все зависимости указаны в `requirements.txt` и устанавливаются автоматически при первом запуске.
'''
            readme_file.write_text(readme_content, encoding='utf-8')

# Инициализируем БД при импорте
init_database()
