"""
Модуль для работы с SQLite базами данных ботов
"""
import sqlite3
import json
import random
import string
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from backend.database import get_bot
from backend.config import BOTS_DIR
import logging

logger = logging.getLogger(__name__)

def get_bot_sqlite_db_path(bot_id: int, db_name: str = "bot.db") -> Path:
    """Получение пути к SQLite БД бота"""
    bot = get_bot(bot_id)
    if not bot:
        raise ValueError(f"Бот {bot_id} не найден")
    
    bot_dir = Path(bot['bot_dir'])
    db_path = bot_dir / "data" / db_name
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path

def get_sqlite_connection(bot_id: int, db_name: str = "bot.db") -> sqlite3.Connection:
    """Получение соединения с SQLite БД бота"""
    db_path = get_bot_sqlite_db_path(bot_id, db_name)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

def get_tables(bot_id: int, db_name: str = "bot.db") -> List[Dict[str, Any]]:
    """Получение списка таблиц в БД"""
    try:
        # Проверяем, существует ли файл базы данных
        try:
            db_path = get_bot_sqlite_db_path(bot_id, db_name)
        except (ValueError, Exception) as e:
            # Если бот не найден или другая ошибка при получении пути
            logger.warning(f"Error getting DB path for bot {bot_id}, db {db_name}: {e}")
            return []
        
        if not db_path.exists():
            # База данных не существует - возвращаем пустой список
            return []
        
        try:
            conn = get_sqlite_connection(bot_id, db_name)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name, type 
                FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            
            tables = []
            for row in cursor.fetchall():
                # Получаем количество строк в таблице
                try:
                    cursor.execute(f"SELECT COUNT(*) as count FROM {row['name']}")
                    count_row = cursor.fetchone()
                    row_count = count_row['count'] if count_row else 0
                except Exception:
                    row_count = 0
                
                tables.append({
                    'name': row['name'],
                    'type': row['type'],
                    'row_count': row_count
                })
            
            conn.close()
            return tables
        except sqlite3.Error as e:
            # Ошибка SQLite - возможно, база данных повреждена или недоступна
            logger.warning(f"SQLite error getting tables for bot {bot_id}, db {db_name}: {e}")
            return []
    except Exception as e:
        logger.error(f"Unexpected error getting tables for bot {bot_id}, db {db_name}: {e}", exc_info=True)
        # В любом случае возвращаем пустой список, чтобы не ломать UI
        return []

def get_table_structure(bot_id: int, table_name: str, db_name: str = "bot.db") -> Dict[str, Any]:
    """Получение структуры таблицы"""
    try:
        conn = get_sqlite_connection(bot_id, db_name)
        cursor = conn.cursor()
        
        # Получаем информацию о столбцах
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = []
        for row in cursor.fetchall():
            columns.append({
                'cid': row[0],
                'name': row[1],
                'type': row[2],
                'notnull': bool(row[3]),
                'default_value': row[4],
                'pk': bool(row[5])
            })
        
        # Получаем индексы
        cursor.execute(f"PRAGMA index_list({table_name})")
        indexes = []
        for idx_row in cursor.fetchall():
            idx_name = idx_row[1]
            cursor.execute(f"PRAGMA index_info({idx_name})")
            idx_columns = [col[2] for col in cursor.fetchall()]
            indexes.append({
                'name': idx_name,
                'unique': bool(idx_row[2]),
                'columns': idx_columns
            })
        
        # Получаем внешние ключи
        cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        foreign_keys = []
        for fk_row in cursor.fetchall():
            foreign_keys.append({
                'id': fk_row[0],
                'seq': fk_row[1],
                'table': fk_row[2],
                'from': fk_row[3],
                'to': fk_row[4],
                'on_update': fk_row[5],
                'on_delete': fk_row[6],
                'match': fk_row[7]
            })
        
        conn.close()
        
        return {
            'name': table_name,
            'columns': columns,
            'indexes': indexes,
            'foreign_keys': foreign_keys
        }
    except Exception as e:
        logger.error(f"Error getting table structure: {e}", exc_info=True)
        raise

def get_table_data(bot_id: int, table_name: str, db_name: str = "bot.db", 
                   limit: int = 100, offset: int = 0, order_by: Optional[str] = None) -> Dict[str, Any]:
    """Получение данных из таблицы с пагинацией"""
    try:
        conn = get_sqlite_connection(bot_id, db_name)
        cursor = conn.cursor()
        
        # Получаем общее количество строк
        cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
        total_rows = cursor.fetchone()['count']
        
        # Формируем запрос
        query = f"SELECT * FROM {table_name}"
        if order_by:
            query += f" ORDER BY {order_by}"
        query += f" LIMIT {limit} OFFSET {offset}"
        
        cursor.execute(query)
        rows = []
        column_names = [description[0] for description in cursor.description]
        
        for row in cursor.fetchall():
            row_dict = {}
            for i, col_name in enumerate(column_names):
                value = row[i]
                # Преобразуем None в null для JSON
                row_dict[col_name] = value
            rows.append(row_dict)
        
        conn.close()
        
        return {
            'columns': column_names,
            'rows': rows,
            'total_rows': total_rows,
            'limit': limit,
            'offset': offset
        }
    except Exception as e:
        logger.error(f"Error getting table data: {e}", exc_info=True)
        raise

def execute_sql(bot_id: int, query: str, db_name: str = "bot.db") -> Dict[str, Any]:
    """Выполнение SQL запроса"""
    try:
        conn = get_sqlite_connection(bot_id, db_name)
        cursor = conn.cursor()
        
        # Определяем тип запроса
        query_upper = query.strip().upper()
        is_select = query_upper.startswith('SELECT')
        is_insert = query_upper.startswith('INSERT')
        is_update = query_upper.startswith('UPDATE')
        is_delete = query_upper.startswith('DELETE')
        is_create = query_upper.startswith('CREATE')
        is_alter = query_upper.startswith('ALTER')
        is_drop = query_upper.startswith('DROP')
        
        if is_select:
            cursor.execute(query)
            rows = []
            column_names = [description[0] for description in cursor.description] if cursor.description else []
            for row in cursor.fetchall():
                row_dict = {}
                for i, col_name in enumerate(column_names):
                    row_dict[col_name] = row[i]
                rows.append(row_dict)
            
            conn.close()
            return {
                'success': True,
                'type': 'select',
                'columns': column_names,
                'rows': rows,
                'affected_rows': len(rows)
            }
        else:
            # Для INSERT, UPDATE, DELETE, CREATE, ALTER, DROP
            cursor.execute(query)
            conn.commit()
            affected_rows = cursor.rowcount
            
            conn.close()
            return {
                'success': True,
                'type': 'modify',
                'affected_rows': affected_rows,
                'message': f'Query executed successfully. Affected rows: {affected_rows}'
            }
    except sqlite3.Error as e:
        logger.error(f"SQL error: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }
    except Exception as e:
        logger.error(f"Error executing SQL: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

def create_table(bot_id: int, table_name: str, columns: List, 
                 db_name: str = "bot.db") -> Dict[str, Any]:
    """Создание новой таблицы
    
    Args:
        columns: Может быть списком словарей с полями (name, type, notnull, default_value, pk)
                 или списком строк (SQL определений столбцов)
    """
    try:
        # Валидация имени таблицы (SQLite позволяет буквы, цифры, подчеркивания, дефисы)
        if not table_name or not table_name.strip():
            return {'success': False, 'error': 'Имя таблицы не может быть пустым'}
        
        # Проверяем, что имя содержит только допустимые символы
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_\-]*$', table_name):
            return {'success': False, 'error': 'Недопустимое имя таблицы. Используйте только буквы, цифры, подчеркивания и дефисы. Имя должно начинаться с буквы или подчеркивания.'}
        
        # Формируем SQL для создания таблицы
        column_defs = []
        
        # Проверяем, какой формат columns: список строк или список словарей
        if columns and len(columns) > 0:
            # Если первый элемент - строка, значит это список SQL определений
            if isinstance(columns[0], str):
                column_defs = [col.strip() for col in columns if col and col.strip()]
            else:
                # Иначе это список словарей
                for col in columns:
                    if isinstance(col, dict):
                        col_name = col.get('name', '').strip()
                        col_type = col.get('type', 'TEXT').upper()
                        col_notnull = col.get('notnull', False)
                        col_default = col.get('default_value', None)
                        col_pk = col.get('pk', False)
                        
                        if not col_name:
                            continue
                        
                        # Валидация имени столбца
                        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_\-]*$', col_name):
                            logger.warning(f"Invalid column name: {col_name}")
                            continue
                        
                        # Валидация типа данных
                        valid_types = ['TEXT', 'INTEGER', 'REAL', 'BLOB', 'NUMERIC']
                        if col_type not in valid_types:
                            logger.warning(f"Invalid column type: {col_type}, using TEXT")
                            col_type = 'TEXT'
                        
                        col_def = f"{col_name} {col_type}"
                        if col_notnull:
                            col_def += " NOT NULL"
                        if col_default is not None:
                            if isinstance(col_default, str):
                                # Экранируем одинарные кавычки в строковых значениях
                                escaped_default = col_default.replace("'", "''")
                                col_def += f" DEFAULT '{escaped_default}'"
                            else:
                                col_def += f" DEFAULT {col_default}"
                        if col_pk:
                            col_def += " PRIMARY KEY"
                        
                        column_defs.append(col_def)
        
        if not column_defs:
            return {'success': False, 'error': 'Не предоставлены допустимые столбцы'}
        
        sql = f"CREATE TABLE {table_name} ({', '.join(column_defs)})"
        logger.debug(f"Creating table SQL: {sql}")
        
        result = execute_sql(bot_id, sql, db_name)
        
        if not result.get('success'):
            logger.error(f"SQL execution failed: {result.get('error', 'Unknown error')}")
        
        return result
    except Exception as e:
        logger.error(f"Error creating table: {e}", exc_info=True)
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Traceback: {error_trace}")
        return {'success': False, 'error': f'Ошибка создания таблицы: {str(e)}'}

def drop_table(bot_id: int, table_name: str, db_name: str = "bot.db") -> Dict[str, Any]:
    """Удаление таблицы"""
    try:
        sql = f"DROP TABLE IF EXISTS {table_name}"
        return execute_sql(bot_id, sql, db_name)
    except Exception as e:
        logger.error(f"Error dropping table: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def insert_row(bot_id: int, table_name: str, data: Dict[str, Any], 
               db_name: str = "bot.db") -> Dict[str, Any]:
    """Вставка новой строки"""
    try:
        if not data:
            return {'success': False, 'error': 'Данные для вставки не предоставлены'}
        
        # Валидация имени таблицы
        import re
        if not table_name or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_\-]*$', table_name):
            return {'success': False, 'error': 'Недопустимое имя таблицы'}
        
        # Валидация имен столбцов
        columns = []
        values = []
        for col_name, value in data.items():
            if not col_name or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_\-]*$', col_name):
                logger.warning(f"Invalid column name skipped: {col_name}")
                continue
            columns.append(col_name)
            # Преобразуем None в NULL для SQL
            if value is None or value == '':
                values.append(None)
            else:
                values.append(str(value) if not isinstance(value, (int, float)) else value)
        
        if not columns:
            return {'success': False, 'error': 'Нет допустимых столбцов для вставки'}
        
        placeholders = ', '.join(['?' for _ in values])
        sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
        
        logger.debug(f"Inserting row SQL: {sql}, values: {values}")
        
        conn = get_sqlite_connection(bot_id, db_name)
        cursor = conn.cursor()
        cursor.execute(sql, values)
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        
        return {
            'success': True,
            'row_id': row_id,
            'message': 'Строка успешно добавлена'
        }
    except sqlite3.IntegrityError as e:
        logger.error(f"Integrity error inserting row: {e}", exc_info=True)
        error_msg = str(e)
        if "UNIQUE constraint" in error_msg:
            return {'success': False, 'error': 'Нарушение уникальности: такая запись уже существует'}
        elif "NOT NULL constraint" in error_msg:
            return {'success': False, 'error': 'Ошибка: обязательное поле не заполнено'}
        else:
            return {'success': False, 'error': f'Ошибка целостности данных: {error_msg}'}
    except sqlite3.OperationalError as e:
        logger.error(f"Operational error inserting row: {e}", exc_info=True)
        error_msg = str(e)
        if "no such column" in error_msg.lower():
            return {'success': False, 'error': 'Ошибка: указанный столбец не существует в таблице'}
        else:
            return {'success': False, 'error': f'Ошибка базы данных: {error_msg}'}
    except Exception as e:
        logger.error(f"Error inserting row: {e}", exc_info=True)
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Traceback: {error_trace}")
        return {'success': False, 'error': f'Ошибка добавления строки: {str(e)}'}

def update_row(bot_id: int, table_name: str, row_id: int, data: Dict[str, Any],
               primary_key: str = "id", db_name: str = "bot.db") -> Dict[str, Any]:
    """Обновление строки"""
    try:
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + [row_id]
        
        sql = f"UPDATE {table_name} SET {set_clause} WHERE {primary_key} = ?"
        
        conn = get_sqlite_connection(bot_id, db_name)
        cursor = conn.cursor()
        cursor.execute(sql, values)
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        
        return {
            'success': True,
            'affected_rows': affected_rows,
            'message': 'Row updated successfully'
        }
    except Exception as e:
        logger.error(f"Error updating row: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def delete_row(bot_id: int, table_name: str, row_id: int, 
               primary_key: str = "id", db_name: str = "bot.db") -> Dict[str, Any]:
    """Удаление строки"""
    try:
        sql = f"DELETE FROM {table_name} WHERE {primary_key} = ?"
        
        conn = get_sqlite_connection(bot_id, db_name)
        cursor = conn.cursor()
        cursor.execute(sql, [row_id])
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        
        return {
            'success': True,
            'affected_rows': affected_rows,
            'message': 'Row deleted successfully'
        }
    except Exception as e:
        logger.error(f"Error deleting row: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def add_column(bot_id: int, table_name: str, column_name: str, column_type: str,
               db_name: str = "bot.db", notnull: bool = False, default_value: Optional[str] = None) -> Dict[str, Any]:
    """Добавление столбца в таблицу"""
    try:
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        if notnull:
            sql += " NOT NULL"
        if default_value is not None:
            sql += f" DEFAULT '{default_value}'"
        
        return execute_sql(bot_id, sql, db_name)
    except Exception as e:
        logger.error(f"Error adding column: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def drop_column(bot_id: int, table_name: str, column_name: str, 
                db_name: str = "bot.db") -> Dict[str, Any]:
    """Удаление столбца из таблицы (SQLite не поддерживает напрямую, используем пересоздание)"""
    try:
        # SQLite не поддерживает DROP COLUMN напрямую, нужно пересоздать таблицу
        # Получаем структуру таблицы
        structure = get_table_structure(bot_id, table_name, db_name)
        
        # Фильтруем столбцы
        new_columns = [col for col in structure['columns'] if col['name'] != column_name]
        if len(new_columns) == len(structure['columns']):
            return {'success': False, 'error': 'Столбец не найден'}
        
        # Получаем данные
        data_result = get_table_data(bot_id, table_name, db_name, limit=10000)
        
        # Создаем временную таблицу
        temp_table = f"{table_name}_temp"
        column_defs = []
        for col in new_columns:
            col_def = f"{col['name']} {col['type']}"
            if col['notnull']:
                col_def += " NOT NULL"
            if col['default_value'] is not None:
                col_def += f" DEFAULT '{col['default_value']}'"
            if col['pk']:
                col_def += " PRIMARY KEY"
            column_defs.append(col_def)
        
        conn = get_sqlite_connection(bot_id, db_name)
        cursor = conn.cursor()
        
        # Создаем временную таблицу
        cursor.execute(f"CREATE TABLE {temp_table} ({', '.join(column_defs)})")
        
        # Копируем данные
        if data_result['rows']:
            columns = [col['name'] for col in new_columns]
            placeholders = ', '.join(['?' for _ in columns])
            insert_sql = f"INSERT INTO {temp_table} ({', '.join(columns)}) VALUES ({placeholders})"
            
            for row in data_result['rows']:
                values = [row.get(col) for col in columns]
                cursor.execute(insert_sql, values)
        
        # Удаляем старую таблицу
        cursor.execute(f"DROP TABLE {table_name}")
        
        # Переименовываем временную таблицу
        cursor.execute(f"ALTER TABLE {temp_table} RENAME TO {table_name}")
        
        conn.commit()
        conn.close()
        
        return {'success': True, 'message': 'Column dropped successfully'}
    except Exception as e:
        logger.error(f"Error dropping column: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def get_databases(bot_id: int) -> List[str]:
    """Получение списка SQLite БД бота"""
    try:
        bot = get_bot(bot_id)
        if not bot:
            return []
        
        bot_dir = Path(bot['bot_dir'])
        data_dir = bot_dir / "data"
        
        if not data_dir.exists():
            return []
        
        databases = []
        for db_file in data_dir.glob("*.db"):
            databases.append(db_file.name)
        
        return sorted(databases)
    except Exception as e:
        logger.error(f"Error getting databases: {e}", exc_info=True)
        return []

def _generate_unique_db_name(bot_id: int, base_name: str = "bot") -> str:
    """Генерация уникального имени базы данных с рандомными 3 буквами"""
    existing_databases = get_databases(bot_id)
    max_attempts = 100
    
    for _ in range(max_attempts):
        # Генерируем 3 случайные буквы
        random_suffix = ''.join(random.choices(string.ascii_lowercase, k=3))
        db_name = f"{base_name}_{random_suffix}.db"
        
        # Проверяем, что такого имени еще нет
        if db_name not in existing_databases:
            return db_name
    
    # Если не удалось сгенерировать за 100 попыток, используем timestamp
    import time
    timestamp = int(time.time()) % 100000
    return f"{base_name}_{timestamp}.db"

def create_database(bot_id: int, db_name: Optional[str] = None) -> Dict[str, Any]:
    """Создание новой SQLite БД"""
    try:
        # Если имя не указано или пустое, генерируем уникальное
        if not db_name or db_name.strip() == "" or db_name == "bot.db":
            db_name = _generate_unique_db_name(bot_id)
            logger.info(f"Сгенерировано уникальное имя базы данных: {db_name}")
        else:
            # Валидация имени
            db_name_clean = db_name.strip()
            if not db_name_clean.replace('_', '').replace('.', '').replace('-', '').isalnum():
                return {'success': False, 'error': 'Недопустимое имя базы данных. Используйте только буквы, цифры, дефисы и подчеркивания.'}
            
            if not db_name_clean.endswith('.db'):
                db_name_clean += '.db'
            
            db_name = db_name_clean
        
        db_path = get_bot_sqlite_db_path(bot_id, db_name)
        
        # Если база уже существует, генерируем новое имя
        if db_path.exists():
            logger.warning(f"База данных {db_name} уже существует, генерируем новое имя")
            db_name = _generate_unique_db_name(bot_id)
            db_path = get_bot_sqlite_db_path(bot_id, db_name)
        
        # Создаем пустую БД
        conn = sqlite3.connect(str(db_path))
        conn.close()
        
        return {'success': True, 'message': f'База данных {db_name} успешно создана', 'db_name': db_name}
    except Exception as e:
        logger.error(f"Error creating database: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def delete_database(bot_id: int, db_name: str) -> Dict[str, Any]:
    """Удаление SQLite БД"""
    try:
        db_path = get_bot_sqlite_db_path(bot_id, db_name)
        
        if not db_path.exists():
            return {'success': False, 'error': 'Database not found'}
        
        db_path.unlink()
        
        return {'success': True, 'message': f'Database {db_name} deleted successfully'}
    except Exception as e:
        logger.error(f"Error deleting database: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def _parse_sql_file(sql_file_path: str) -> List[str]:
    """Парсинг SQL файла на отдельные запросы
    
    Args:
        sql_file_path: Путь к SQL файлу
        
    Returns:
        Список SQL запросов
    """
    try:
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Удаляем комментарии /* */ (многострочные)
        import re
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Разбиваем на строки и удаляем комментарии --
        lines = []
        for line in content.split('\n'):
            # Удаляем комментарии -- до конца строки
            comment_pos = line.find('--')
            if comment_pos != -1:
                line = line[:comment_pos]
            lines.append(line)
        
        content = '\n'.join(lines)
        
        # Разбиваем на запросы по точке с запятой
        queries = []
        current_query = []
        in_string = False
        string_char = None
        escape_next = False
        
        for char in content:
            if escape_next:
                current_query.append(char)
                escape_next = False
                continue
            
            if char == '\\' and in_string:
                escape_next = True
                current_query.append(char)
                continue
            
            if not in_string and (char == '"' or char == "'"):
                in_string = True
                string_char = char
                current_query.append(char)
            elif in_string and char == string_char:
                in_string = False
                string_char = None
                current_query.append(char)
            elif not in_string and char == ';':
                query = ''.join(current_query).strip()
                if query:
                    queries.append(query)
                current_query = []
            else:
                current_query.append(char)
        
        # Добавляем последний запрос, если он есть
        query = ''.join(current_query).strip()
        if query:
            queries.append(query)
        
        # Фильтруем пустые запросы
        return [q for q in queries if q.strip()]
    except Exception as e:
        logger.error(f"Error parsing SQL file: {e}", exc_info=True)
        raise

def import_database(bot_id: int, source_db_path: str, target_db_name: Optional[str] = None, import_mode: str = "new") -> Dict[str, Any]:
    """Импорт SQLite БД из файла или SQL скрипта
    
    Args:
        bot_id: ID бота
        source_db_path: Путь к исходному файлу БД (.db, .sqlite, .sqlite3) или SQL скрипту (.sql)
        target_db_name: Имя целевой БД (для режима "new" или "existing")
        import_mode: "new" - создать новую БД из файла, "existing" - импортировать данные в существующую БД
    
    Returns:
        Dict с результатом операции
    """
    try:
        import shutil
        
        source_path = Path(source_db_path)
        if not source_path.exists():
            return {'success': False, 'error': 'Исходный файл не найден'}
        
        # Определяем тип файла по расширению
        file_ext = source_path.suffix.lower()
        is_sql_file = file_ext == '.sql'
        
        # Если это SQL файл, обрабатываем его отдельно
        if is_sql_file:
            return _import_from_sql_file(bot_id, source_path, target_db_name, import_mode)
        
        # Для .db, .sqlite, .sqlite3 файлов - проверяем, что это валидный SQLite файл
        try:
            test_conn = sqlite3.connect(str(source_path))
            test_conn.execute("SELECT 1")
            test_conn.close()
        except sqlite3.Error as e:
            return {'success': False, 'error': f'Недопустимый SQLite файл: {str(e)}'}
        
        if import_mode == "new":
            # Создаем новую БД из импортированного файла
            if not target_db_name or target_db_name.strip() == "":
                # Генерируем имя из имени исходного файла или уникальное
                source_name = source_path.stem
                if source_name:
                    target_db_name = f"{source_name}.db"
                else:
                    target_db_name = _generate_unique_db_name(bot_id)
            else:
                # Валидация имени
                target_db_name_clean = target_db_name.strip()
                if not target_db_name_clean.replace('_', '').replace('.', '').replace('-', '').isalnum():
                    return {'success': False, 'error': 'Недопустимое имя базы данных. Используйте только буквы, цифры, дефисы и подчеркивания.'}
                
                if not target_db_name_clean.endswith('.db'):
                    target_db_name_clean += '.db'
                
                target_db_name = target_db_name_clean
            
            # Проверяем, не существует ли уже БД с таким именем
            target_db_path = get_bot_sqlite_db_path(bot_id, target_db_name)
            if target_db_path.exists():
                # Генерируем новое имя
                target_db_name = _generate_unique_db_name(bot_id)
                target_db_path = get_bot_sqlite_db_path(bot_id, target_db_name)
            
            # Копируем файл
            shutil.copy2(source_path, target_db_path)
            
            return {
                'success': True, 
                'message': f'База данных {target_db_name} успешно импортирована', 
                'db_name': target_db_name
            }
        
        elif import_mode == "existing":
            # Импортируем данные в существующую БД
            if not target_db_name:
                return {'success': False, 'error': 'Не указано имя целевой базы данных'}
            
            target_db_path = get_bot_sqlite_db_path(bot_id, target_db_name)
            if not target_db_path.exists():
                return {'success': False, 'error': f'База данных {target_db_name} не найдена'}
            
            # Подключаемся к обеим БД
            target_conn = get_sqlite_connection(bot_id, target_db_name)
            source_conn = sqlite3.connect(str(source_path))
            source_conn.row_factory = sqlite3.Row
            
            try:
                target_cursor = target_conn.cursor()
                source_cursor = source_conn.cursor()
                
                # Получаем список таблиц из исходной БД
                source_cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                source_tables = [row[0] for row in source_cursor.fetchall()]
                
                imported_tables = []
                skipped_tables = []
                
                for table_name in source_tables:
                    try:
                        # Проверяем, существует ли таблица в целевой БД
                        target_cursor.execute("""
                            SELECT name FROM sqlite_master 
                            WHERE type='table' AND name=?
                        """, (table_name,))
                        
                        if target_cursor.fetchone():
                            skipped_tables.append(table_name)
                            continue
                        
                        # Получаем структуру таблицы из исходной БД
                        source_cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                        create_sql_row = source_cursor.fetchone()
                        if not create_sql_row or not create_sql_row[0]:
                            continue
                        create_sql = create_sql_row[0]
                        
                        # Создаем таблицу в целевой БД
                        target_cursor.execute(create_sql[0])
                        
                        # Копируем данные
                        source_cursor.execute(f"SELECT * FROM {table_name}")
                        columns = [description[0] for description in source_cursor.description]
                        rows = source_cursor.fetchall()
                        
                        if rows:
                            placeholders = ','.join(['?' for _ in columns])
                            insert_sql = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
                            target_cursor.executemany(insert_sql, [tuple(row) for row in rows])
                        
                        imported_tables.append(table_name)
                    except Exception as e:
                        logger.error(f"Error importing table {table_name}: {e}")
                        skipped_tables.append(f"{table_name} (ошибка: {str(e)})")
                
                target_conn.commit()
                
                message = f'Импортировано таблиц: {len(imported_tables)}'
                if skipped_tables:
                    message += f'. Пропущено: {len(skipped_tables)}'
                
                return {
                    'success': True,
                    'message': message,
                    'imported_tables': imported_tables,
                    'skipped_tables': skipped_tables,
                    'db_name': target_db_name
                }
            finally:
                target_conn.close()
                source_conn.close()
        
        else:
            return {'success': False, 'error': f'Недопустимый режим импорта: {import_mode}'}
            
    except Exception as e:
        logger.error(f"Error importing database: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def _import_from_sql_file(bot_id: int, sql_file_path: Path, target_db_name: Optional[str] = None, import_mode: str = "new") -> Dict[str, Any]:
    """Импорт из SQL файла
    
    Args:
        bot_id: ID бота
        sql_file_path: Путь к SQL файлу
        target_db_name: Имя целевой БД
        import_mode: "new" или "existing"
    
    Returns:
        Dict с результатом операции
    """
    try:
        # Парсим SQL файл
        queries = _parse_sql_file(str(sql_file_path))
        
        if not queries:
            return {'success': False, 'error': 'SQL файл не содержит валидных запросов'}
        
        if import_mode == "new":
            # Создаем новую БД
            if not target_db_name or target_db_name.strip() == "":
                source_name = sql_file_path.stem
                if source_name:
                    target_db_name = f"{source_name}.db"
                else:
                    target_db_name = _generate_unique_db_name(bot_id)
            else:
                target_db_name_clean = target_db_name.strip()
                if not target_db_name_clean.replace('_', '').replace('.', '').replace('-', '').isalnum():
                    return {'success': False, 'error': 'Недопустимое имя базы данных. Используйте только буквы, цифры, дефисы и подчеркивания.'}
                
                if not target_db_name_clean.endswith('.db'):
                    target_db_name_clean += '.db'
                
                target_db_name = target_db_name_clean
            
            # Проверяем, не существует ли уже БД с таким именем
            target_db_path = get_bot_sqlite_db_path(bot_id, target_db_name)
            if target_db_path.exists():
                target_db_name = _generate_unique_db_name(bot_id)
                target_db_path = get_bot_sqlite_db_path(bot_id, target_db_name)
            
            # Создаем новую БД
            conn = get_sqlite_connection(bot_id, target_db_name)
            
            try:
                cursor = conn.cursor()
                executed_queries = 0
                errors = []
                
                # Выполняем каждый запрос
                for query in queries:
                    try:
                        cursor.execute(query)
                        executed_queries += 1
                    except sqlite3.Error as e:
                        error_msg = f"Ошибка выполнения запроса: {str(e)}"
                        logger.warning(f"{error_msg}\nQuery: {query[:100]}")
                        errors.append(error_msg)
                
                conn.commit()
                
                message = f'База данных {target_db_name} успешно создана из SQL файла. Выполнено запросов: {executed_queries}'
                if errors:
                    message += f'. Ошибок: {len(errors)}'
                
                return {
                    'success': True,
                    'message': message,
                    'db_name': target_db_name,
                    'executed_queries': executed_queries,
                    'errors': errors if errors else None
                }
            finally:
                conn.close()
        
        elif import_mode == "existing":
            # Импортируем в существующую БД
            if not target_db_name:
                return {'success': False, 'error': 'Не указано имя целевой базы данных'}
            
            target_db_path = get_bot_sqlite_db_path(bot_id, target_db_name)
            if not target_db_path.exists():
                return {'success': False, 'error': f'База данных {target_db_name} не найдена'}
            
            conn = get_sqlite_connection(bot_id, target_db_name)
            
            try:
                cursor = conn.cursor()
                executed_queries = 0
                errors = []
                
                # Выполняем каждый запрос
                for query in queries:
                    try:
                        cursor.execute(query)
                        executed_queries += 1
                    except sqlite3.Error as e:
                        error_msg = f"Ошибка выполнения запроса: {str(e)}"
                        logger.warning(f"{error_msg}\nQuery: {query[:100]}")
                        errors.append(error_msg)
                
                conn.commit()
                
                message = f'Импортировано в {target_db_name}. Выполнено запросов: {executed_queries}'
                if errors:
                    message += f'. Ошибок: {len(errors)}'
                
                return {
                    'success': True,
                    'message': message,
                    'db_name': target_db_name,
                    'executed_queries': executed_queries,
                    'errors': errors if errors else None
                }
            finally:
                conn.close()
        
        else:
            return {'success': False, 'error': f'Недопустимый режим импорта: {import_mode}'}
            
    except Exception as e:
        logger.error(f"Error importing from SQL file: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

