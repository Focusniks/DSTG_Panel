"""
Управление MySQL базами данных для ботов
"""
import pymysql
from typing import Optional, Dict, List, Any, Tuple
from backend.config import MYSQL_PREFIX
from backend.database import get_bot, update_bot, get_db_connection, get_mysql_settings
import secrets
import string
import logging

logger = logging.getLogger(__name__)

# Кэш для настроек MySQL (обновляется при каждом подключении)
_mysql_settings_cache = None

def _get_mysql_config():
    """Получение настроек MySQL из базы данных панели (с кэшированием)"""
    global _mysql_settings_cache
    if _mysql_settings_cache is None:
        _mysql_settings_cache = get_mysql_settings()
    return _mysql_settings_cache

def get_mysql_connection(db_name: Optional[str] = None) -> pymysql.Connection:
    """Получение соединения с MySQL"""
    try:
        # Получаем настройки из базы данных панели
        mysql_config = _get_mysql_config()
        mysql_host = mysql_config['host']
        mysql_port = mysql_config['port']
        mysql_user = mysql_config['user']
        mysql_password = mysql_config['password']
        
        # Логируем информацию о подключении (без пароля для безопасности)
        password_length = len(mysql_password) if mysql_password else 0
        logger.info(f"Connecting to MySQL: host={mysql_host}, port={mysql_port}, user={mysql_user}, database={db_name}, password_length={password_length}")
        
        # Создаем параметры подключения
        connect_params = {
            'host': mysql_host,
            'port': mysql_port,
            'user': mysql_user,
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }
        
        # Добавляем database только если указана
        if db_name:
            connect_params['database'] = db_name
        
        # ВАЖНО: Всегда передаем password явно
        # pymysql.connect требует явной передачи password параметра
        # Если пароль пустой, передаем пустую строку (не None)
        if mysql_password:
            connect_params['password'] = mysql_password
            password_info = f"YES (length={len(mysql_password)})"
        else:
            connect_params['password'] = ""  # Явно передаем пустую строку
            password_info = "NO (empty string)"
        
        logger.debug(f"Connection params: host={mysql_host}, port={mysql_port}, user={mysql_user}, database={db_name}, password_provided={password_info}")
        
        connection = pymysql.connect(**connect_params)
        logger.info(f"Successfully connected to MySQL")
        return connection
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to connect to MySQL: {error_msg}", exc_info=True)
        # Добавляем дополнительную информацию об ошибке
        if "Access denied" in error_msg:
            mysql_config = _get_mysql_config()
            logger.error(f"MySQL connection details: host={mysql_config['host']}, port={mysql_config['port']}, user={mysql_config['user']}, password_set={'YES' if mysql_config['password'] else 'NO'}")
        raise Exception(f"Failed to connect to MySQL: {error_msg}")

def generate_db_name(bot_id: int, custom_name: Optional[str] = None) -> str:
    """Генерация имени базы данных для бота"""
    if custom_name:
        # Очищаем имя от недопустимых символов
        safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in custom_name.lower().replace(' ', '_'))
        return f"{MYSQL_PREFIX}{bot_id}_{safe_name}"
    return f"{MYSQL_PREFIX}{bot_id}"

def generate_db_password(length: int = 16) -> str:
    """Генерация пароля для базы данных"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_bot_database(bot_id: int, db_name: Optional[str] = None) -> Dict[str, str]:
    """Создание базы данных для бота"""
    logger.info(f"Starting database creation for bot {bot_id}")
    
    bot = get_bot(bot_id)
    if not bot:
        logger.error(f"Bot {bot_id} not found")
        raise ValueError("Bot not found")
    
    if not db_name:
        db_name = generate_db_name(bot_id)
    else:
        # Очищаем имя от недопустимых символов
        safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in db_name.lower().replace(' ', '_'))
        db_name = f"{MYSQL_PREFIX}{bot_id}_{safe_name}"
    db_user = f"bot_{bot_id}_user"
    db_password = generate_db_password()
    
    logger.info(f"Generated database name: {db_name}, user: {db_user}")
    
    conn = None
    try:
        # Подключаемся к MySQL без выбора БД (чтобы создать новую)
        try:
            logger.info(f"Attempting to connect to MySQL server...")
            conn = get_mysql_connection()
            logger.info(f"Successfully connected to MySQL server")
        except Exception as e:
            logger.error(f"Failed to connect to MySQL: {str(e)}", exc_info=True)
            raise Exception(f"Не удалось подключиться к MySQL серверу. Проверьте настройки подключения в config.py. Ошибка: {str(e)}")
        
        try:
            with conn.cursor() as cursor:
                # Создаем базу данных
                try:
                    logger.info(f"Creating database '{db_name}'...")
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                    conn.commit()
                    logger.info(f"Database '{db_name}' created successfully")
                except Exception as e:
                    logger.error(f"Failed to create database '{db_name}': {str(e)}", exc_info=True)
                    raise Exception(f"Не удалось создать базу данных '{db_name}': {str(e)}")
                
                # Создаем пользователя (если поддерживается)
                try:
                    logger.info(f"Creating user '{db_user}'...")
                    cursor.execute(f"CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{db_password}'")
                    cursor.execute(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'localhost'")
                    cursor.execute("FLUSH PRIVILEGES")
                    conn.commit()
                    logger.info(f"User '{db_user}' created and granted privileges")
                except Exception as user_error:
                    logger.warning(f"Failed to create user '{db_user}', using root user instead: {str(user_error)}")
                    mysql_config = _get_mysql_config()
                    db_user = mysql_config['user']
                    db_password = mysql_config['password']
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
        
        # Получаем настройки MySQL для сохранения в базу данных панели
        mysql_config = _get_mysql_config()
        
        # Сохраняем информацию о базе данных в таблицу bot_databases
        try:
            conn_panel = get_db_connection()
            cursor_panel = conn_panel.cursor()
            cursor_panel.execute("""
                INSERT OR REPLACE INTO bot_databases (bot_id, db_name, db_user, db_password, db_host, db_port)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (bot_id, db_name, db_user, db_password, mysql_config['host'], mysql_config['port']))
            conn_panel.commit()
            conn_panel.close()
            logger.info(f"Database info saved to bot_databases table for bot {bot_id}")
        except Exception as e:
            logger.warning(f"Failed to save database info to panel DB: {e}")
        
        # Если это первая база данных, обновляем db_name в таблице bots (для обратной совместимости)
        try:
            bot = get_bot(bot_id)
            if not bot.get('db_name'):
                update_bot(bot_id, db_name=db_name)
        except Exception:
            pass
        
        return {
            "db_name": db_name,
            "db_user": db_user,
            "db_password": db_password,
            "host": mysql_config['host'],
            "port": mysql_config['port']
        }
        
    except Exception as e:
        if conn:
            try:
                conn.close()
            except:
                pass
        raise Exception(f"Ошибка при создании базы данных: {str(e)}")

def get_bot_databases(bot_id: int) -> List[Dict[str, Any]]:
    """Получение списка всех баз данных бота"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, db_name, db_user, db_host, db_port, created_at
            FROM bot_databases
            WHERE bot_id = ?
            ORDER BY created_at DESC
        """, (bot_id,))
        
        rows = cursor.fetchall()
        databases = []
        for row in rows:
            db_name = row['db_name']
            # Получаем дополнительную информацию о БД
            try:
                db_info = get_database_info(db_name)
                databases.append({
                    'id': row['id'],
                    'db_name': db_name,
                    'db_user': row['db_user'],
                    'db_host': row['db_host'],
                    'db_port': row['db_port'],
                    'created_at': row['created_at'],
                    'tables': db_info.get('tables', []),
                    'table_count': db_info.get('table_count', 0),
                    'size_mb': db_info.get('size_mb', 0)
                })
            except Exception as e:
                databases.append({
                    'id': row['id'],
                    'db_name': db_name,
                    'db_user': row['db_user'],
                    'db_host': row['db_host'],
                    'db_port': row['db_port'],
                    'created_at': row['created_at'],
                    'error': str(e)
                })
        
        conn.close()
        return databases
    except Exception as e:
        logger.error(f"Error getting bot databases: {e}", exc_info=True)
        return []

def get_database_info(db_name: str) -> Dict[str, Any]:
    """Получение информации о конкретной базе данных"""
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
        logger.error(f"Error getting database info for {db_name}: {e}", exc_info=True)
        return {
            "db_name": db_name,
            "error": str(e)
        }

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

def delete_bot_database(bot_id: int, db_name: str) -> Tuple[bool, str]:
    """Удаление базы данных бота"""
    logger.info(f"Deleting database '{db_name}' for bot {bot_id}")
    
    try:
        # Получаем информацию о БД из таблицы
        conn_panel = get_db_connection()
        cursor_panel = conn_panel.cursor()
        cursor_panel.execute("""
            SELECT id FROM bot_databases
            WHERE bot_id = ? AND db_name = ?
        """, (bot_id, db_name))
        db_row = cursor_panel.fetchone()
        
        if not db_row:
            conn_panel.close()
            return (False, "База данных не найдена в списке баз данных бота")
        
        # Удаляем БД из MySQL
        try:
            mysql_conn = get_mysql_connection()
            with mysql_conn.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
                mysql_conn.commit()
            mysql_conn.close()
            logger.info(f"Database '{db_name}' dropped from MySQL")
        except Exception as e:
            logger.warning(f"Failed to drop database '{db_name}' from MySQL: {e}")
            # Продолжаем удаление из таблицы даже если не удалось удалить из MySQL
        
        # Удаляем запись из таблицы bot_databases
        cursor_panel.execute("""
            DELETE FROM bot_databases
            WHERE bot_id = ? AND db_name = ?
        """, (bot_id, db_name))
        conn_panel.commit()
        conn_panel.close()
        
        logger.info(f"Database '{db_name}' deleted successfully")
        return (True, "База данных успешно удалена")
    except Exception as e:
        logger.error(f"Error deleting database '{db_name}': {e}", exc_info=True)
        return (False, f"Ошибка при удалении базы данных: {str(e)}")

def execute_sql_query(bot_id: int, query: str, db_name: Optional[str] = None) -> Dict[str, Any]:
    """Выполнение SQL запроса в базе данных бота"""
    # Если db_name не указан, используем первую БД из списка или старую логику
    if not db_name:
        databases = get_bot_databases(bot_id)
        if databases:
            db_name = databases[0]['db_name']
        else:
            # Обратная совместимость: используем db_name из таблицы bots
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

def get_phpmyadmin_url(bot_id: int, db_name: Optional[str] = None, phpmyadmin_base_url: Optional[str] = None) -> str:
    """Генерация URL для phpMyAdmin с автологином"""
    from backend.config import PHPMYADMIN_URL
    from urllib.parse import quote
    
    # Используем переданный базовый URL или значение из конфига
    if phpmyadmin_base_url:
        phpmyadmin_url = phpmyadmin_base_url
    else:
        phpmyadmin_url = PHPMYADMIN_URL
    
    # Если db_name не указан, используем первую БД из списка
    if not db_name:
        databases = get_bot_databases(bot_id)
        if databases:
            db_name = databases[0]['db_name']
        else:
            # Обратная совместимость
            bot = get_bot(bot_id)
            if not bot or not bot.get('db_name'):
                return phpmyadmin_url
            db_name = bot['db_name']
    
    # Получаем credentials из таблицы bot_databases
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT db_user, db_password
            FROM bot_databases
            WHERE bot_id = ? AND db_name = ?
        """, (bot_id, db_name))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            db_user = row['db_user']
            db_password = row['db_password']
        else:
            # Fallback на root credentials из настроек панели
            mysql_config = _get_mysql_config()
            db_user = mysql_config['user']
            db_password = mysql_config['password']
    except Exception:
        mysql_config = _get_mysql_config()
        db_user = mysql_config['user']
        db_password = mysql_config['password']
    
    # Формируем URL для phpMyAdmin с параметрами автологина
    url = f"{phpmyadmin_url}/?pma_username={quote(db_user)}&pma_password={quote(db_password)}&server=1&db={quote(db_name)}"
    return url

