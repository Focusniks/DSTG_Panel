"""
Управление MySQL базами данных для ботов
"""
import pymysql
from typing import Optional, Dict, List, Any
from backend.config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_ROOT_USER, 
    MYSQL_ROOT_PASSWORD, MYSQL_PREFIX
)
from backend.database import get_bot, update_bot
import secrets
import string

def get_mysql_connection(db_name: Optional[str] = None) -> pymysql.Connection:
    """Получение соединения с MySQL"""
    try:
        connection = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_ROOT_USER,
            password=MYSQL_ROOT_PASSWORD,
            database=db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        raise Exception(f"Failed to connect to MySQL: {str(e)}")

def generate_db_name(bot_id: int) -> str:
    """Генерация имени базы данных для бота"""
    return f"{MYSQL_PREFIX}{bot_id}"

def generate_db_password(length: int = 16) -> str:
    """Генерация пароля для базы данных"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_bot_database(bot_id: int) -> Dict[str, str]:
    """Создание базы данных для бота"""
    bot = get_bot(bot_id)
    if not bot:
        raise ValueError("Bot not found")
    
    db_name = generate_db_name(bot_id)
    db_user = f"bot_{bot_id}_user"
    db_password = generate_db_password()
    
    conn = None
    try:
        # Подключаемся к MySQL без выбора БД (чтобы создать новую)
        try:
            conn = get_mysql_connection()
        except Exception as e:
            raise Exception(f"Не удалось подключиться к MySQL серверу. Проверьте настройки подключения в config.py. Ошибка: {str(e)}")
        
        try:
            with conn.cursor() as cursor:
                # Создаем базу данных
                try:
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                    conn.commit()
                except Exception as e:
                    raise Exception(f"Не удалось создать базу данных '{db_name}': {str(e)}")
                
                # Создаем пользователя (если поддерживается)
                try:
                    cursor.execute(f"CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{db_password}'")
                    cursor.execute(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'localhost'")
                    cursor.execute("FLUSH PRIVILEGES")
                    conn.commit()
                except Exception:
                    db_user = MYSQL_ROOT_USER
                    db_password = MYSQL_ROOT_PASSWORD
        except Exception as e:
            # Если ошибка при создании, пробуем удалить созданную БД
            try:
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
                        conn.commit()
            except:
                pass
            raise e
        finally:
            if conn:
                conn.close()
        
        try:
            update_bot(bot_id, db_name=db_name)
        except Exception:
            pass
        
        # Сохраняем credentials в config.json бота
        try:
            from pathlib import Path
            import json
            
            config_path = Path(bot['bot_dir']) / "config.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                config['database'] = {
                    'host': MYSQL_HOST,
                    'port': MYSQL_PORT,
                    'database': db_name,
                    'user': db_user,
                    'password': db_password
                }
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        
        return {
            "db_name": db_name,
            "db_user": db_user,
            "db_password": db_password,
            "host": MYSQL_HOST,
            "port": MYSQL_PORT
        }
        
    except Exception as e:
        if conn:
            try:
                conn.close()
            except:
                pass
        raise Exception(f"Ошибка при создании базы данных: {str(e)}")

def get_bot_database_info(bot_id: int) -> Optional[Dict[str, Any]]:
    """Получение информации о базе данных бота"""
    bot = get_bot(bot_id)
    if not bot or not bot.get('db_name'):
        return None
    
    db_name = bot['db_name']
    
    try:
        conn = get_mysql_connection(db_name)
        
        with conn.cursor() as cursor:
            # Получаем список таблиц
            cursor.execute("SHOW TABLES")
            tables = [list(row.values())[0] for row in cursor.fetchall()]
            
            # Получаем размер БД
            cursor.execute("""
                SELECT 
                    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb
                FROM information_schema.tables 
                WHERE table_schema = %s
            """, (db_name,))
            size_result = cursor.fetchone()
            size_mb = size_result['size_mb'] if size_result else 0
        
        conn.close()
        
        return {
            "db_name": db_name,
            "tables": tables,
            "size_mb": size_mb,
            "table_count": len(tables)
        }
    except Exception as e:
        return {
            "db_name": db_name,
            "error": str(e)
        }

def execute_sql_query(bot_id: int, query: str) -> Dict[str, Any]:
    """Выполнение SQL запроса в базе данных бота"""
    bot = get_bot(bot_id)
    if not bot or not bot.get('db_name'):
        raise ValueError("Bot database not found")
    
    db_name = bot['db_name']
    
    try:
        conn = get_mysql_connection(db_name)
        
        with conn.cursor() as cursor:
            cursor.execute(query)
            
            # Определяем тип запроса
            query_upper = query.strip().upper()
            if query_upper.startswith('SELECT') or query_upper.startswith('SHOW') or query_upper.startswith('DESCRIBE'):
                # SELECT запрос - возвращаем результат
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                conn.close()
                return {
                    "success": True,
                    "type": "select",
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows)
                }
            else:
                # INSERT, UPDATE, DELETE и т.д.
                conn.commit()
                affected_rows = cursor.rowcount
                
                conn.close()
                return {
                    "success": True,
                    "type": "modify",
                    "affected_rows": affected_rows
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def get_phpmyadmin_url(bot_id: int) -> str:
    """Генерация URL для phpMyAdmin с автологином"""
    from backend.config import PHPMYADMIN_URL
    from urllib.parse import quote
    
    bot = get_bot(bot_id)
    if not bot or not bot.get('db_name'):
        return PHPMYADMIN_URL
    
    db_name = bot['db_name']
    
    # Читаем credentials из config.json
    from pathlib import Path
    import json
    
    config_path = Path(bot['bot_dir']) / "config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        db_config = config.get('database', {})
        db_user = db_config.get('user', MYSQL_ROOT_USER)
        db_password = db_config.get('password', MYSQL_ROOT_PASSWORD)
        
        # Формируем URL для phpMyAdmin с параметрами автологина
        # Формат: http://phpmyadmin/?pma_username=user&pma_password=pass&server=1&db=database
        url = f"{PHPMYADMIN_URL}/?pma_username={quote(db_user)}&pma_password={quote(db_password)}&server=1&db={quote(db_name)}"
        return url
    
    return PHPMYADMIN_URL

