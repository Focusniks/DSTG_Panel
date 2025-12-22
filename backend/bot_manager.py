"""
Управление процессами ботов
"""
import subprocess
import os
import sys
import psutil
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from backend.database import get_bot, update_bot
from backend.config import BOTS_DIR
from backend.git_manager import is_git_repo, update_bot_from_git

def start_bot(bot_id: int) -> Tuple[bool, Optional[str]]:
    """Запуск бота"""
    bot = get_bot(bot_id)
    if not bot:
        return (False, "Бот не найден")
    
    # Проверяем, не запущен ли уже бот
    if bot['status'] == 'running' and bot['pid']:
        if is_process_running(bot['pid']):
            return (True, None)  # Бот уже запущен
    
    bot_dir = Path(bot['bot_dir'])
    if not bot_dir.exists():
        bot_dir.mkdir(parents=True, exist_ok=True)
    
    # Если директория пустая и есть Git репозиторий, пытаемся клонировать
    if bot.get('git_repo_url'):
        files = [f for f in bot_dir.iterdir() if f.name not in ['.gitkeep', 'config.json']]
        if not files or (len(files) == 0 and not is_git_repo(bot_dir)):
            repo_url = bot['git_repo_url']
            branch = bot.get('git_branch', 'main')
            success, message = update_bot_from_git(bot_dir, repo_url, branch)
    
    start_file = bot.get('start_file') or 'main.py'
    
    start_file_path = bot_dir / start_file
    if not start_file_path.exists():
        return (False, f"Стартовый файл не найден: {start_file}")
    
    # Устанавливаем статус "запускается"
    update_bot(bot_id, status='starting')
    
    # Автоматически устанавливаем зависимости из requirements.txt
    requirements_file = bot_dir / "requirements.txt"
    if requirements_file.exists():
        update_bot(bot_id, status='installing')
        try:
            success = install_dependencies(str(bot_dir))
            if not success:
                update_bot(bot_id, status='error_startup')
                return (False, "Не удалось установить зависимости из requirements.txt")
        except Exception as e:
            error_msg = str(e)
            update_bot(bot_id, status='error_startup')
            return (False, f"Ошибка установки зависимостей: {error_msg}")
    
    # Определяем команду запуска в зависимости от типа файла
    if start_file.endswith('.py'):
        cmd = [sys.executable, str(start_file_path)]
    elif start_file.endswith('.js'):
        cmd = ['node', str(start_file_path)]
    else:
        # Попытка запустить как исполняемый файл
        cmd = [str(start_file_path)]
    
    try:
        # Запускаем процесс в директории бота
        # Для Windows используем CREATE_NEW_PROCESS_GROUP, для Unix - start_new_session
        import platform
        creation_flags = 0
        if platform.system() == 'Windows':
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            start_new_session = True
        
        # Изначально задаем PIPE, но потом изменим на файлы
        kwargs = {
            'cwd': str(bot_dir),
        }
        
        # Удаляем переменные прокси из окружения для процесса бота
        env = os.environ.copy()
        proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
        for var in proxy_vars:
            env.pop(var, None)
        # Устанавливаем NO_PROXY для отключения прокси
        env['NO_PROXY'] = '*'
        kwargs['env'] = env
        
        if platform.system() == 'Windows':
            kwargs['creationflags'] = creation_flags
        else:
            kwargs['start_new_session'] = True
        
        # Сохраняем весь вывод (stdout и stderr) в один файл для удобства
        log_dir = bot_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / "bot.log"
        
        # Очищаем старый лог при запуске бота
        # Сначала открываем в режиме "w" для очистки, затем закрываем
        # Затем открываем в режиме "a" (append), чтобы можно было читать файл одновременно
        if log_path.exists():
            with open(log_path, "w", encoding="utf-8") as f:
                pass  # Очищаем файл
        
        # Открываем файл в режиме добавления для процесса
        log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        
        # Записываем метку времени начала запуска
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"Bot {bot_id} started at {timestamp}\n")
        log_file.flush()
        
        # Перенаправляем stdout и stderr в один файл
        kwargs['stdout'] = log_file
        kwargs['stderr'] = subprocess.STDOUT  # Перенаправляем stderr в stdout (в файл)
        
        process = subprocess.Popen(cmd, **kwargs)
        # Если закрыть их, процесс не сможет писать в них
        
        # Небольшая задержка для проверки, что процесс запустился
        import time
        time.sleep(1.5)
        
        # Проверяем, что процесс еще работает
        if process.poll() is not None:
            exit_code = process.returncode
            
            try:
                log_file.close()
            except:
                pass
            
            log_output = ""
            try:
                if log_path.exists() and log_path.stat().st_size > 0:
                    log_output = log_path.read_text(encoding="utf-8", errors='ignore')
            except Exception:
                pass
            
            # Извлекаем основную ошибку
            if log_output:
                error_msg = f"Exit code {exit_code}\n{log_output[-2000:]}"
            else:
                error_msg = f"Process exited immediately with code {exit_code}. Check logs in {log_dir}"
            
            raise Exception(error_msg)
        
        try:
            apply_resource_limits(process.pid, bot['cpu_limit'], bot['memory_limit'])
        except Exception:
            pass
        
        # Записываем дату запуска
        from datetime import datetime
        current_time = datetime.now().isoformat()
        update_bot(bot_id, pid=process.pid, status='running', started_at=current_time, last_started_at=current_time)
        
        time.sleep(2.0)
        if process.poll() is not None:
            exit_code = process.returncode
            current_time = datetime.now().isoformat()
            update_bot(bot_id, pid=None, status='stopped', started_at=None, last_crashed_at=current_time, last_stopped_at=current_time)
            
            try:
                log_file.close()
            except:
                pass
            
            log_output = ""
            try:
                if log_path.exists() and log_path.stat().st_size > 0:
                    log_output = log_path.read_text(encoding="utf-8", errors='ignore')
            except Exception:
                pass
            
            if log_output:
                error_msg = f"Process exited after startup (code {exit_code}):\n{log_output[-2000:]}"
            else:
                error_msg = f"Process exited after startup with code {exit_code}. Check logs in {log_dir}"
            
            return (False, error_msg)
        
        return (True, None)
    except Exception as e:
        error_msg = str(e)
        update_bot(bot_id, status='error_startup', pid=None)
        return (False, error_msg)

def stop_bot(bot_id: int) -> bool:
    """Остановка бота"""
    bot = get_bot(bot_id)
    if not bot or not bot['pid']:
        return False
    
    pid = bot['pid']
    
    try:
        # Проверяем, существует ли процесс
        if not is_process_running(pid):
            update_bot(bot_id, pid=None, status='stopped')
            # Очищаем кэш CPU для этого PID
            if pid in _cpu_percent_cache:
                del _cpu_percent_cache[pid]
            return True
        
        # Получаем процесс
        process = psutil.Process(pid)
        
        # Останавливаем процесс и все дочерние процессы
        try:
            children = process.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            
            process.terminate()
            
            # Ждем завершения (5 секунд)
            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                # Если не завершился, убиваем принудительно
                try:
                    process.kill()
                except psutil.NoSuchProcess:
                    pass
        except psutil.NoSuchProcess:
            pass
        
        # Записываем дату остановки
        from datetime import datetime
        current_time = datetime.now().isoformat()
        # Обновляем статус
        update_bot(bot_id, pid=None, status='stopped', started_at=None, last_stopped_at=current_time)
        # Очищаем кэш CPU для этого PID
        if pid in _cpu_percent_cache:
            del _cpu_percent_cache[pid]
        return True
        
    except Exception as e:
        from datetime import datetime
        current_time = datetime.now().isoformat()
        update_bot(bot_id, pid=None, status='stopped', started_at=None, last_stopped_at=current_time)
        # Очищаем кэш CPU для этого PID
        if pid in _cpu_percent_cache:
            del _cpu_percent_cache[pid]
        return False

def install_dependencies(bot_dir: str) -> bool:
    """Установка зависимостей из requirements.txt"""
    requirements_file = Path(bot_dir) / "requirements.txt"
    if not requirements_file.exists():
        return True  # Нет requirements.txt - ничего устанавливать не нужно
    
    try:
        cmd = [
            sys.executable, "-m", "pip", "install", 
            "--trusted-host", "pypi.org",
            "--trusted-host", "files.pythonhosted.org",
            "-r", str(requirements_file)
        ]
        
        env = os.environ.copy()
        env.pop('HTTP_PROXY', None)
        env.pop('HTTPS_PROXY', None)
        env.pop('http_proxy', None)
        env.pop('https_proxy', None)
        env['NO_PROXY'] = '*'
        
        result = subprocess.run(
            cmd,
            cwd=bot_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=300,
            text=True,
            env=env
        )
        
        if result.returncode != 0:
            error_msg = result.stdout if result.stdout else "Неизвестная ошибка"
            raise Exception(f"Ошибка pip install с кодом возврата {result.returncode}: {error_msg}")
        
        return True
    except subprocess.TimeoutExpired:
        raise Exception("Timeout installing dependencies (exceeded 5 minutes)")
    except Exception:
        raise


def is_process_running(pid: int) -> bool:
    """Проверка, запущен ли процесс"""
    try:
        process = psutil.Process(pid)
        # Проверяем, что процесс существует и это не зомби
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False

# Кэш для хранения предыдущих значений cpu_percent по PID
_cpu_percent_cache = {}

def get_bot_process_info(bot_id: int) -> Optional[Dict]:
    """Получение информации о процессе бота"""
    bot = get_bot(bot_id)
    if not bot or not bot['pid']:
        return None
    
    pid = bot['pid']
    
    try:
        if not is_process_running(pid):
            # Процесс не запущен, обновляем статус
            update_bot(bot_id, pid=None, status='stopped')
            if pid in _cpu_percent_cache:
                del _cpu_percent_cache[pid]
            return None
        
        process = psutil.Process(pid)
        
        # Получаем метрики CPU
        # cpu_percent требует двух вызовов - первый инициализирует, второй возвращает значение
        # Используем кэш для хранения предыдущего значения, чтобы не терять его между вызовами
        try:
            if pid not in _cpu_percent_cache:
                # Первый вызов для инициализации (вернет 0.0 или None)
                process.cpu_percent(interval=None)
                # Используем 0.0 для первого раза
                cpu_percent = 0.0
                _cpu_percent_cache[pid] = 0.0
            else:
                # Второй и последующие вызовы возвращают реальное значение
                # Используем interval=None для мгновенного значения (быстрее)
                cpu_percent = process.cpu_percent(interval=None)
                if cpu_percent is None:
                    # Если None, используем предыдущее значение
                    cpu_percent = _cpu_percent_cache.get(pid, 0.0)
                else:
                    # Сохраняем значение в кэш
                    _cpu_percent_cache[pid] = cpu_percent
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            cpu_percent = _cpu_percent_cache.get(pid, 0.0)
        
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)  # RSS в MB
        
        return {
            "pid": pid,
            "cpu_percent": cpu_percent,
            "memory_mb": memory_mb,
            "memory_bytes": memory_info.rss,
            "status": "running"
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        # Процесс не найден или нет доступа
        update_bot(bot_id, pid=None, status='stopped')
        if pid in _cpu_percent_cache:
            del _cpu_percent_cache[pid]
        return None

def apply_resource_limits(pid: int, cpu_limit: float, memory_limit_mb: int):
    """Применение лимитов ресурсов к процессу"""
    try:
        process = psutil.Process(pid)
        
        # На Windows возможности ограничены, но можем попробовать установить приоритет
        if sys.platform == 'win32':
            # Устанавливаем низкий приоритет процесса (эффективно ограничивает CPU)
            try:
                # Пытаемся использовать win32api если доступен
                import win32process
                import win32api
                import win32con
                
                handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
                win32process.SetPriorityClass(handle, win32process.BELOW_NORMAL_PRIORITY_CLASS)
                win32api.CloseHandle(handle)
            except (ImportError, OSError, AttributeError):
                # Если win32api не доступен, пытаемся через psutil
                try:
                    # psutil на Windows может не поддерживать nice
                    pass
                except (AttributeError, psutil.AccessDenied):
                    pass
        
        # На Unix-системах можем установить nice и ограничения памяти
        else:
            try:
                # Устанавливаем nice (приоритет CPU)
                if cpu_limit < 50:
                    nice_value = 10  # Низкий приоритет
                elif cpu_limit < 75:
                    nice_value = 5
                else:
                    nice_value = 0
                process.nice(nice_value)
            except (AttributeError, psutil.AccessDenied):
                pass
        
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

def restore_bot_states():
    """Восстановление состояния ботов при запуске панели"""
    from backend.database import get_all_bots
    import logging
    import time
    
    logger = logging.getLogger(__name__)
    
    bots = get_all_bots()
    for bot in bots:
        if bot['status'] == 'running' and bot['pid']:
            # Проверяем, действительно ли процесс запущен
            if not is_process_running(bot['pid']):
                # Процесс не запущен, обновляем статус
                update_bot(bot['id'], pid=None, status='stopped')
            else:
                try:
                    apply_resource_limits(bot['pid'], bot.get('cpu_limit', 50.0), bot.get('memory_limit', 512))
                except Exception:
                    pass
    
    # Автозапуск ботов с включенным auto_start
    logger.info("Проверка ботов для автозапуска...")
    for bot in bots:
        auto_start = bot.get('auto_start', 0)
        # Преобразуем в int, если это bool или None
        if isinstance(auto_start, bool):
            auto_start = 1 if auto_start else 0
        elif auto_start is None:
            auto_start = 0
        else:
            auto_start = int(auto_start) if auto_start else 0
        
        if auto_start and bot['status'] == 'stopped':
            logger.info(f"Автозапуск бота {bot['name']} (ID: {bot['id']})...")
            try:
                success, message = start_bot(bot['id'])
                if success:
                    logger.info(f"Бот {bot['name']} успешно запущен автоматически")
                    # Небольшая задержка между запусками ботов
                    time.sleep(1)
                else:
                    logger.warning(f"Не удалось автоматически запустить бота {bot['name']}: {message}")
            except Exception as e:
                logger.error(f"Ошибка при автозапуске бота {bot['name']}: {e}", exc_info=True)

