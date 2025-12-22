"""
Продвинутое управление SSH ключами для доступа к приватным Git репозиториям
Поддерживает GitHub, GitLab, Bitbucket и другие Git хостинги
"""
import subprocess
import os
import shutil
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, List
from backend.config import DATA_DIR

logger = logging.getLogger(__name__)

# Директория для хранения SSH ключей панели
SSH_DIR = DATA_DIR / "ssh"
SSH_PRIVATE_KEY = SSH_DIR / "panel_deploy_key"
SSH_PUBLIC_KEY = SSH_DIR / "panel_deploy_key.pub"
SSH_CONFIG_FILE = SSH_DIR / "config"

# Поддерживаемые Git хостинги и их SSH настройки
GIT_HOSTS_CONFIG = {
    'github.com': {
        'name': 'GitHub',
        'hostname': 'github.com',
        'user': 'git',
        'port': 22
    },
    'gitlab.com': {
        'name': 'GitLab',
        'hostname': 'gitlab.com',
        'user': 'git',
        'port': 22
    },
    'bitbucket.org': {
        'name': 'Bitbucket',
        'hostname': 'bitbucket.org',
        'user': 'git',
        'port': 22
    },
    'gitea.com': {
        'name': 'Gitea',
        'hostname': 'gitea.com',
        'user': 'git',
        'port': 22
    }
}


def ensure_ssh_dir() -> Path:
    """Создание директории для SSH ключей с правильными правами"""
    SSH_DIR.mkdir(parents=True, exist_ok=True)
    # Устанавливаем правильные права доступа (700) для Unix
    if os.name != 'nt':
        try:
            os.chmod(SSH_DIR, 0o700)
        except Exception:
            pass
    return SSH_DIR


def find_ssh_keygen_aggressive() -> Optional[str]:
    """
    Агрессивный поиск ssh-keygen в системе
    Пробует все возможные пути и методы
    """
    import platform
    
    # Метод 1: shutil.which (самый надежный)
    path = shutil.which("ssh-keygen")
    if path:
        logger.info(f"ssh-keygen найден через shutil.which: {path}")
        return path
    
    # Метод 2: Прямой вызов команды (может работать даже если не в PATH)
    try:
        result = subprocess.run(
            ["ssh-keygen", "-V"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False  # На Linux не используем shell
        )
        # OpenSSH выводит версию в stderr
        if "OpenSSH" in (result.stderr or result.stdout or ""):
            logger.info("ssh-keygen найден через прямую проверку команды (работает из PATH)")
            return "ssh-keygen"
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.debug(f"Прямая проверка ssh-keygen вызвала исключение: {e}")
        # Если команда не FileNotFoundError, возможно она найдена, но что-то не так
        # Пробуем использовать "ssh-keygen" как есть
        logger.info("ssh-keygen возможно найден (исключение не FileNotFoundError)")
        return "ssh-keygen"
    
    # Метод 3: Стандартные пути для Linux/Unix
    if platform.system() != 'Windows':
        paths = [
            "/usr/bin/ssh-keygen",           # Стандартный путь на Ubuntu/Debian
            "/usr/local/bin/ssh-keygen",      # Альтернативный путь
            "/bin/ssh-keygen",                # Минимальный путь
            "/opt/local/bin/ssh-keygen",      # MacPorts
            "/usr/sbin/ssh-keygen",           # Некоторые системы
        ]
        
        for path in paths:
            if os.path.exists(path):
                # Проверяем права на выполнение
                if os.access(path, os.X_OK):
                    logger.info(f"ssh-keygen найден в стандартном пути: {path}")
                    return path
                else:
                    logger.warning(f"ssh-keygen найден в {path}, но нет прав на выполнение")
        
        # Метод 4: Linux - через which
        try:
            result = subprocess.run(
                ["which", "ssh-keygen"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                found_path = result.stdout.strip()
                if os.path.exists(found_path):
                    logger.info(f"ssh-keygen найден через which: {found_path}")
                    return found_path
        except:
            pass
        
        # Метод 5: Linux - через dpkg/apt (Ubuntu/Debian)
        try:
            result = subprocess.run(
                ["dpkg", "-L", "openssh-client"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'ssh-keygen' in line and os.path.exists(line.strip()):
                        found_path = line.strip()
                        logger.info(f"ssh-keygen найден через dpkg: {found_path}")
                        return found_path
        except:
            pass
    
    # Метод 6: Windows пути
    else:
        paths = [
            r"C:\Windows\System32\OpenSSH\ssh-keygen.exe",
            r"C:\Program Files\Git\usr\bin\ssh-keygen.exe",
            r"C:\Program Files (x86)\Git\usr\bin\ssh-keygen.exe",
            r"C:\Program Files\OpenSSH\ssh-keygen.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Git\usr\bin\ssh-keygen.exe"),
            os.path.expanduser(r"~\AppData\Local\Programs\Git\mingw64\bin\ssh-keygen.exe"),
        ]
        # Также пробуем найти через переменные окружения
        program_files = os.environ.get('ProgramFiles', r'C:\Program Files')
        program_files_x86 = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
        local_appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        
        paths.extend([
            os.path.join(program_files, 'Git', 'usr', 'bin', 'ssh-keygen.exe'),
            os.path.join(program_files_x86, 'Git', 'usr', 'bin', 'ssh-keygen.exe'),
            os.path.join(local_appdata, 'Programs', 'Git', 'usr', 'bin', 'ssh-keygen.exe'),
        ])
        
        for path in paths:
            if os.path.exists(path):
                logger.info(f"ssh-keygen найден в стандартном пути: {path}")
                return path
        
        # Windows - через where
        try:
            result = subprocess.run(
                ["where", "ssh-keygen"],
                capture_output=True,
                text=True,
                timeout=3,
                shell=True
            )
            if result.returncode == 0 and result.stdout.strip():
                found_path = result.stdout.strip().split('\n')[0].strip()
                logger.info(f"ssh-keygen найден через where: {found_path}")
                return found_path
        except:
            pass
        
        # Windows - через PowerShell
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Command ssh-keygen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                found_path = result.stdout.strip()
                logger.info(f"ssh-keygen найден через PowerShell: {found_path}")
                return found_path
        except:
            pass
    
    logger.warning("ssh-keygen не найден ни одним методом")
    return None


def generate_ssh_key(force: bool = False) -> Tuple[bool, str]:
    """
    Генерация SSH ключа для панели
    
    Args:
        force: Если True, перезаписывает существующий ключ
    
    Returns:
        (success, message)
    """
    try:
        ensure_ssh_dir()
        
        # Проверяем существование ключа
        if not force and SSH_PRIVATE_KEY.exists() and SSH_PUBLIC_KEY.exists():
            return True, "SSH ключ уже существует"
        
        # Удаляем существующие ключи если force=True
        if force:
            try:
                if SSH_PRIVATE_KEY.exists():
                    SSH_PRIVATE_KEY.unlink()
                if SSH_PUBLIC_KEY.exists():
                    SSH_PUBLIC_KEY.unlink()
            except Exception as e:
                return False, f"Не удалось удалить существующие ключи: {str(e)}"
        
        # Проверяем наличие ssh-keygen - используем агрессивный поиск
        logger.info("Поиск ssh-keygen: запуск агрессивного поиска")
        ssh_keygen_path = find_ssh_keygen_aggressive()
        search_log = []
        
        if not ssh_keygen_path:
            # Если агрессивный поиск не дал результата, пробуем старые методы для логирования
            logger.info("Агрессивный поиск не дал результата, пробуем дополнительные методы")
            
            # Метод 1: через which/where
            logger.info("Поиск ssh-keygen: метод 1 - shutil.which")
            ssh_keygen_path = shutil.which("ssh-keygen")
            if ssh_keygen_path:
                logger.info(f"Найден через shutil.which: {ssh_keygen_path}")
            else:
                search_log.append("shutil.which: не найден")
        
        # Метод 2: пробуем стандартные пути
        if not ssh_keygen_path:
            logger.info("Поиск ssh-keygen: метод 2 - стандартные пути")
            standard_paths = []
            if os.name == 'nt':
                # Windows пути - расширенный список
                standard_paths = [
                    r"C:\Program Files\Git\usr\bin\ssh-keygen.exe",
                    r"C:\Program Files (x86)\Git\usr\bin\ssh-keygen.exe",
                    r"C:\Windows\System32\OpenSSH\ssh-keygen.exe",
                    r"C:\Windows\System32\ssh-keygen.exe",
                    r"C:\Program Files\OpenSSH\ssh-keygen.exe",
                    r"C:\Program Files (x86)\OpenSSH\ssh-keygen.exe",
                    r"C:\OpenSSH\ssh-keygen.exe",
                    # Git for Windows может быть в разных местах
                    os.path.expanduser(r"~\AppData\Local\Programs\Git\usr\bin\ssh-keygen.exe"),
                    os.path.expanduser(r"~\AppData\Local\Programs\Git\mingw64\bin\ssh-keygen.exe"),
                ]
            else:
                # Unix пути
                standard_paths = [
                    "/usr/bin/ssh-keygen",
                    "/usr/local/bin/ssh-keygen",
                    "/bin/ssh-keygen",
                    "/opt/local/bin/ssh-keygen",
                    "/usr/sbin/ssh-keygen",
                ]
            
            for path in standard_paths:
                expanded_path = os.path.expanduser(path) if '~' in path else path
                if os.path.exists(expanded_path):
                    if os.name == 'nt' or os.access(expanded_path, os.X_OK):
                        ssh_keygen_path = expanded_path
                        logger.info(f"Найден в стандартном пути: {ssh_keygen_path}")
                        break
                    else:
                        search_log.append(f"{expanded_path}: существует, но нет прав на выполнение")
                else:
                    search_log.append(f"{expanded_path}: не существует")
        
        # Метод 3: пробуем выполнить команду напрямую (для Windows может быть в PATH через Git)
        if not ssh_keygen_path:
            logger.info("Поиск ssh-keygen: метод 3 - прямая проверка команды")
            try:
                # Пробуем разные варианты команды
                test_commands = [
                    ["ssh-keygen", "-V"],
                    ["ssh-keygen", "--version"],
                ]
                
                for cmd in test_commands:
                    try:
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=5,
                            shell=(os.name == 'nt')  # На Windows используем shell
                        )
                        # Если команда выполнилась (даже с ошибкой), значит ssh-keygen доступен
                        if result.returncode == 0 or "OpenSSH" in result.stderr or "OpenSSH" in result.stdout:
                            ssh_keygen_path = "ssh-keygen"
                            logger.info(f"Найден через прямую проверку команды: {cmd}")
                            break
                    except FileNotFoundError:
                        search_log.append(f"Команда {cmd}: FileNotFoundError")
                        continue
                    except subprocess.TimeoutExpired:
                        search_log.append(f"Команда {cmd}: TimeoutExpired")
                        continue
                    except Exception as e:
                        # Любая другая ошибка может означать, что команда найдена
                        logger.warning(f"Команда {cmd} вызвала исключение: {e}, но это может означать что команда найдена")
                        ssh_keygen_path = "ssh-keygen"
                        break
            except Exception as e:
                search_log.append(f"Ошибка при проверке команд: {e}")
        
        # Метод 4: на Windows пробуем найти через where
        if not ssh_keygen_path and os.name == 'nt':
            logger.info("Поиск ssh-keygen: метод 4 - команда where (Windows)")
            try:
                result = subprocess.run(
                    ["where", "ssh-keygen"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    shell=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    paths = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
                    if paths:
                        ssh_keygen_path = paths[0]
                        logger.info(f"Найден через where: {ssh_keygen_path}")
                else:
                    search_log.append("where ssh-keygen: команда не вернула результатов")
            except Exception as e:
                search_log.append(f"Ошибка при выполнении where: {e}")
        
        # Метод 5: на Unix пробуем через which
        if not ssh_keygen_path and os.name != 'nt':
            logger.info("Поиск ssh-keygen: метод 5 - команда which (Unix)")
            try:
                result = subprocess.run(
                    ["which", "ssh-keygen"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0 and result.stdout.strip():
                    ssh_keygen_path = result.stdout.strip()
                    logger.info(f"Найден через which: {ssh_keygen_path}")
                else:
                    search_log.append("which ssh-keygen: команда не вернула результатов")
            except Exception as e:
                search_log.append(f"Ошибка при выполнении which: {e}")
        
        # Метод 7: Ubuntu/Debian - через dpkg (показывает где установлен openssh-client)
        if not ssh_keygen_path and os.name != 'nt':
            logger.info("Поиск ssh-keygen: метод 7 - dpkg (Ubuntu/Debian)")
            try:
                result = subprocess.run(
                    ["dpkg", "-L", "openssh-client"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        line = line.strip()
                        if '/ssh-keygen' in line and os.path.exists(line):
                            ssh_keygen_path = line
                            logger.info(f"Найден через dpkg: {ssh_keygen_path}")
                            break
                else:
                    search_log.append("dpkg openssh-client: пакет не установлен или не найден")
            except FileNotFoundError:
                search_log.append("dpkg: команда не найдена (не Debian/Ubuntu?)")
            except Exception as e:
                search_log.append(f"Ошибка при выполнении dpkg: {e}")
        
        # Метод 6: на Windows пробуем через PowerShell Get-Command
        if not ssh_keygen_path and os.name == 'nt':
            logger.info("Поиск ssh-keygen: метод 6 - PowerShell Get-Command")
            try:
                result = subprocess.run(
                    ["powershell", "-Command", "Get-Command ssh-keygen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    ssh_keygen_path = result.stdout.strip()
                    logger.info(f"Найден через PowerShell: {ssh_keygen_path}")
                else:
                    search_log.append("PowerShell Get-Command: команда не вернула результатов")
            except Exception as e:
                search_log.append(f"Ошибка при выполнении PowerShell: {e}")
        
        if not ssh_keygen_path:
            error_msg = "ssh-keygen не найден. "
            error_msg += f"\n\nПопытки поиска:\n" + "\n".join(f"  - {log}" for log in search_log[:15])
            
            if os.name == 'nt':
                error_msg += "\n\nУстановите Git for Windows (включает OpenSSH) или OpenSSH для Windows."
                error_msg += "\nПосле установки перезапустите сервер."
            else:
                # Проверяем, установлен ли openssh-client на Ubuntu/Debian
                try:
                    check_result = subprocess.run(
                        ["dpkg", "-l", "openssh-client"],
                        capture_output=True,
                        text=True,
                        timeout=3
                    )
                    if check_result.returncode != 0 or "openssh-client" not in check_result.stdout:
                        error_msg += "\n\n⚠️ Пакет openssh-client не установлен!"
                        error_msg += "\n\nУстановите OpenSSH:"
                        error_msg += "\n  sudo apt-get update"
                        error_msg += "\n  sudo apt-get install -y openssh-client"
                        error_msg += "\n\nПосле установки перезапустите сервер панели:"
                        error_msg += "\n  sudo systemctl restart bot-panel"
                    else:
                        error_msg += "\n\n⚠️ openssh-client установлен, но ssh-keygen не найден в PATH."
                        error_msg += "\n\nПопробуйте:"
                        error_msg += "\n  1. Проверить PATH: echo $PATH"
                        error_msg += "\n  2. Найти ssh-keygen: dpkg -L openssh-client | grep ssh-keygen"
                        error_msg += "\n  3. Перезапустить сервер: sudo systemctl restart bot-panel"
                except FileNotFoundError:
                    # Не Ubuntu/Debian, пробуем другие методы
                    error_msg += "\n\nУстановите OpenSSH:"
                    error_msg += "\n  • Ubuntu/Debian: sudo apt-get install -y openssh-client"
                    error_msg += "\n  • CentOS/RHEL: sudo yum install -y openssh-clients"
                    error_msg += "\n  • Fedora: sudo dnf install -y openssh-clients"
                    error_msg += "\n\nПосле установки перезапустите сервер панели."
                except Exception:
                    error_msg += "\n\nУстановите OpenSSH:"
                    error_msg += "\n  • Ubuntu/Debian: sudo apt-get install -y openssh-client"
                    error_msg += "\n  • CentOS/RHEL: sudo yum install -y openssh-clients"
                    error_msg += "\n  • Fedora: sudo dnf install -y openssh-clients"
                    error_msg += "\n\nПосле установки перезапустите сервер панели."
            
            logger.error(error_msg)
            return False, error_msg
        
        # Генерируем SSH ключ (предпочитаем ed25519, fallback на RSA)
        key_types = [
            ("ed25519", []),  # Современный и безопасный
            ("rsa", ["-b", "4096"])  # Fallback для старых систем
        ]
        
        last_error = None
        for key_type, extra_args in key_types:
            try:
                cmd = [
                    ssh_keygen_path,
                    "-t", key_type,
                    "-f", str(SSH_PRIVATE_KEY),
                    "-N", "",  # Без пароля
                    "-C", "dstg-panel-deploy-key"
                ] + extra_args
                
                logger.info(f"Выполняю команду генерации ключа: {' '.join(cmd)}")
                
                # На Windows используем shell=True для правильной работы с путями
                # На Linux не используем shell, чтобы избежать проблем с путями
                use_shell = (os.name == 'nt' and not os.path.isabs(ssh_keygen_path))
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    shell=use_shell,
                    check=False  # Не выбрасываем исключение при ошибке
                )
                
                logger.debug(f"ssh-keygen вернул код: {result.returncode}")
                if result.stdout:
                    logger.debug(f"stdout: {result.stdout[:200]}")
                if result.stderr:
                    logger.debug(f"stderr: {result.stderr[:200]}")
                
                if result.returncode == 0:
                    # Устанавливаем правильные права доступа
                    if os.name != 'nt':
                        try:
                            os.chmod(SSH_PRIVATE_KEY, 0o600)
                            os.chmod(SSH_PUBLIC_KEY, 0o644)
                        except Exception:
                            pass
                    
                    logger.info(f"SSH ключ успешно сгенерирован (тип: {key_type})")
                    return True, f"SSH ключ успешно сгенерирован (тип: {key_type})"
                else:
                    # Сохраняем ошибку для последующего использования
                    error_output = result.stderr or result.stdout or "Unknown error"
                    last_error = f"Ошибка генерации {key_type} ключа: {error_output}"
                    logger.debug(last_error)
                    # Пробуем следующий тип ключа
                    continue
            except subprocess.TimeoutExpired:
                return False, "Превышено время ожидания при генерации ключа"
            except Exception as e:
                # Пробуем следующий тип ключа
                last_error = f"Исключение при генерации {key_type} ключа: {str(e)}"
                logger.debug(last_error)
                continue
        
        error_msg = "Не удалось сгенерировать SSH ключ ни одного типа"
        if last_error:
            error_msg += f". Последняя ошибка: {last_error}"
        return False, error_msg
        
    except FileNotFoundError as e:
        logger.error(f"FileNotFoundError при генерации SSH ключа: {e}")
        error_msg = "ssh-keygen не найден. Установите OpenSSH."
        # Пробуем еще раз найти через разные методы
        import platform
        if platform.system() == 'Windows':
            # На Windows пробуем найти через разные способы
            possible_paths = [
                r"C:\Windows\System32\OpenSSH\ssh-keygen.exe",
                r"C:\Program Files\Git\usr\bin\ssh-keygen.exe",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    logger.info(f"Найден ssh-keygen в {path}, но FileNotFoundError все равно произошел")
                    error_msg += f"\n\nОбнаружен ssh-keygen в: {path}"
                    error_msg += "\nПопробуйте добавить этот путь в переменную окружения PATH и перезапустить сервер."
                    break
        return False, error_msg
    except Exception as e:
        logger.error(f"Ошибка генерации SSH ключа: {e}", exc_info=True)
        return False, f"Ошибка генерации ключа: {str(e)}"


def get_public_key() -> Optional[str]:
    """Получение публичного SSH ключа"""
    try:
        ensure_ssh_dir()
        
        # Если ключ не существует, генерируем его
        if not SSH_PUBLIC_KEY.exists():
            success, msg = generate_ssh_key()
            if not success:
                logger.warning(f"Не удалось автоматически сгенерировать ключ: {msg}")
                return None
        
        if not SSH_PUBLIC_KEY.exists():
            return None
        
        # Читаем публичный ключ
        with open(SSH_PUBLIC_KEY, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            return content if content else None
            
    except Exception as e:
        logger.error(f"Ошибка чтения публичного ключа: {e}")
        return None


def get_ssh_key_exists() -> bool:
    """Проверка существования SSH ключа"""
    return SSH_PRIVATE_KEY.exists() and SSH_PUBLIC_KEY.exists()


def extract_host_from_url(url: str) -> Optional[str]:
    """
    Извлечение хоста из URL репозитория
    
    Examples:
        https://github.com/user/repo.git -> github.com
        git@github.com:user/repo.git -> github.com
        https://gitlab.com/user/repo.git -> gitlab.com
    """
    if url.startswith('git@'):
        # SSH формат: git@host:path
        try:
            host = url.split('@')[1].split(':')[0]
            return host
        except IndexError:
            return None
    elif url.startswith('https://') or url.startswith('http://'):
        # HTTPS формат: https://host/path
        try:
            host = url.split('/')[2]
            # Убираем порт если есть
            host = host.split(':')[0]
            return host
        except IndexError:
            return None
    
    return None


def convert_https_to_ssh(url: str) -> str:
    """
    Преобразование HTTPS URL в SSH URL
    
    Examples:
        https://github.com/user/repo.git -> git@github.com:user/repo.git
        https://gitlab.com/user/repo.git -> git@gitlab.com:user/repo.git
    """
    if url.startswith('git@'):
        return url  # Уже SSH формат
    
    if url.startswith('https://'):
        url = url.replace('https://', '', 1)
    elif url.startswith('http://'):
        url = url.replace('http://', '', 1)
    else:
        return url  # Неизвестный формат
    
    # Убираем .git в конце если есть
    if url.endswith('.git'):
        url = url[:-4]
    
    # Разделяем на хост и путь
    parts = url.split('/', 1)
    if len(parts) == 2:
        host = parts[0]
        path = parts[1]
        return f"git@{host}:{path}.git"
    
    return url


def setup_ssh_config_for_github() -> bool:
    """
    Настройка SSH config для всех поддерживаемых Git хостингов
    
    Returns:
        True если config успешно создан
    """
    try:
        ensure_ssh_dir()
        
        if not SSH_PRIVATE_KEY.exists():
            logger.warning("SSH приватный ключ не найден, не могу настроить SSH config")
            return False
        
        identity_file_path = str(SSH_PRIVATE_KEY.resolve())
        
        # Создаем конфигурацию для всех поддерживаемых хостов
        config_lines = []
        config_lines.append("# SSH config для DSTG Panel")
        config_lines.append("# Автоматически сгенерировано")
        config_lines.append("")
        
        for host_key, host_config in GIT_HOSTS_CONFIG.items():
            config_lines.append(f"Host {host_key}")
            config_lines.append(f"    HostName {host_config['hostname']}")
            config_lines.append(f"    User {host_config['user']}")
            config_lines.append(f"    IdentityFile {identity_file_path}")
            config_lines.append("    IdentitiesOnly yes")
            config_lines.append("    StrictHostKeyChecking accept-new")
            config_lines.append("    UserKnownHostsFile /dev/null")  # Не сохраняем known_hosts
            if host_config.get('port') and host_config['port'] != 22:
                config_lines.append(f"    Port {host_config['port']}")
            config_lines.append("")
        
        # Добавляем общую конфигурацию для всех остальных Git хостов
        config_lines.append("# Общая конфигурация для других Git хостов")
        config_lines.append("Host *")
        config_lines.append(f"    IdentityFile {identity_file_path}")
        config_lines.append("    IdentitiesOnly yes")
        config_lines.append("    StrictHostKeyChecking accept-new")
        config_lines.append("    UserKnownHostsFile /dev/null")
        
        config_content = "\n".join(config_lines)
        
        with open(SSH_CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        # Устанавливаем правильные права доступа
        if os.name != 'nt':
            try:
                os.chmod(SSH_CONFIG_FILE, 0o600)
            except Exception:
                pass
        
        logger.info("SSH config успешно настроен для всех Git хостингов")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка настройки SSH config: {e}", exc_info=True)
        return False


def check_ssh_available() -> Tuple[bool, Optional[str]]:
    """
    Проверка доступности SSH клиента в системе
    
    Returns:
        (is_available, ssh_path)
    """
    # Пробуем найти ssh в PATH
    ssh_path = shutil.which("ssh")
    if ssh_path:
        if os.path.exists(ssh_path) and os.access(ssh_path, os.X_OK):
            return True, ssh_path
    
    # На Unix системах пробуем стандартные пути
    if os.name != 'nt':
        standard_paths = [
            "/usr/bin/ssh",
            "/usr/local/bin/ssh",
            "/bin/ssh"
        ]
        for path in standard_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return True, path
    
    # Дополнительная проверка: пробуем выполнить ssh -V
    try:
        result = subprocess.run(
            ["ssh", "-V"],
            capture_output=True,
            text=True,
            timeout=2
        )
        # SSH выводит версию в stderr
        if "OpenSSH" in result.stderr or "OpenSSH" in result.stdout:
            ssh_path = shutil.which("ssh") or "/usr/bin/ssh"
            return True, ssh_path
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    except Exception:
        pass
    
    return False, None


def get_git_env_with_ssh() -> dict:
    """
    Возвращает переменные окружения для Git команд с SSH
    
    Настраивает GIT_SSH_COMMAND для использования SSH ключа панели
    """
    env = os.environ.copy()
    
    # Проверяем наличие SSH
    ssh_available, ssh_path = check_ssh_available()
    if not ssh_available:
        logger.warning("SSH клиент не найден, Git будет использовать системные настройки")
        return env
    
    # Проверяем наличие SSH ключа
    if not SSH_PRIVATE_KEY.exists():
        logger.warning("SSH ключ не найден, Git будет использовать системные настройки")
        return env
    
    # Убеждаемся, что SSH config настроен
    if not SSH_CONFIG_FILE.exists():
        setup_ssh_config_for_github()
    
    ssh_key_path = str(SSH_PRIVATE_KEY.resolve())
    ssh_config_path = str(SSH_CONFIG_FILE.resolve())
    
    # Формируем команду SSH
    # Используем найденный путь к ssh
    ssh_cmd_base = ssh_path if ssh_path and ssh_path != "ssh" else "ssh"
    
    # Экранируем пути для безопасности
    if os.name == 'nt':
        # Windows - используем двойные кавычки
        ssh_key_path_escaped = ssh_key_path.replace('\\', '\\\\')
        ssh_config_path_escaped = ssh_config_path.replace('\\', '\\\\')
        ssh_cmd = (
            f'{ssh_cmd_base} '
            f'-F "{ssh_config_path_escaped}" '
            f'-i "{ssh_key_path_escaped}" '
            f'-o StrictHostKeyChecking=accept-new '
            f'-o UserKnownHostsFile=NUL'
        )
    else:
        # Unix-like (Linux, macOS)
        # Используем одинарные кавычки для экранирования путей
        ssh_cmd = (
            f"{ssh_cmd_base} "
            f"-F '{ssh_config_path}' "
            f"-i '{ssh_key_path}' "
            f"-o StrictHostKeyChecking=accept-new "
            f"-o UserKnownHostsFile=/dev/null"
        )
    
    env['GIT_SSH_COMMAND'] = ssh_cmd
    logger.debug(f"GIT_SSH_COMMAND установлен: {ssh_cmd}")
    
    return env


def test_ssh_connection(host: str = "github.com") -> Tuple[bool, str]:
    """
    Тестирование SSH подключения к Git хосту
    
    Args:
        host: Хост для тестирования (по умолчанию github.com)
    
    Returns:
        (success, message)
    """
    ssh_available, ssh_path = check_ssh_available()
    if not ssh_available:
        return False, "SSH клиент не установлен"
    
    if not get_ssh_key_exists():
        return False, "SSH ключ не найден"
    
    # Убеждаемся, что SSH config настроен
    setup_ssh_config_for_github()
    
    try:
        # Пробуем подключиться к хосту
        # Используем команду, которая просто проверяет доступность
        env = get_git_env_with_ssh()
        
        result = subprocess.run(
            [ssh_path, "-T", host],
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )
        
        # GitHub возвращает код 1 при успешном подключении с сообщением
        # GitLab и другие могут возвращать 0
        if result.returncode in [0, 1]:
            # Проверяем, что это не ошибка аутентификации
            if "Permission denied" in result.stderr or "denied" in result.stderr.lower():
                return False, "Ошибка аутентификации. Проверьте, что SSH ключ добавлен в ваш аккаунт."
            
            # Успешное подключение
            return True, f"SSH подключение к {host} успешно"
        
        return False, f"Ошибка подключения: {result.stderr or 'Неизвестная ошибка'}"
        
    except subprocess.TimeoutExpired:
        return False, "Превышено время ожидания при подключении"
    except Exception as e:
        return False, f"Ошибка тестирования SSH: {str(e)}"


def get_ssh_key_info() -> Dict[str, Any]:
    """
    Получение информации о SSH ключе
    
    Returns:
        Словарь с информацией о ключе
    """
    info = {
        "exists": get_ssh_key_exists(),
        "private_key_path": str(SSH_PRIVATE_KEY) if SSH_PRIVATE_KEY.exists() else None,
        "public_key_path": str(SSH_PUBLIC_KEY) if SSH_PUBLIC_KEY.exists() else None,
        "public_key": None,
        "key_type": None,
        "key_size": None,
        "ssh_available": False,
        "ssh_path": None
    }
    
    if info["exists"]:
        # Получаем публичный ключ
        info["public_key"] = get_public_key()
        
        # Пытаемся определить тип и размер ключа из публичного ключа
        if info["public_key"]:
            if "ssh-ed25519" in info["public_key"]:
                info["key_type"] = "ed25519"
                info["key_size"] = "256 bits"
            elif "ssh-rsa" in info["public_key"]:
                info["key_type"] = "RSA"
                # Пытаемся извлечь размер из ключа
                try:
                    # RSA ключи содержат размер в битах
                    if "4096" in info["public_key"]:
                        info["key_size"] = "4096 bits"
                    elif "2048" in info["public_key"]:
                        info["key_size"] = "2048 bits"
                    else:
                        info["key_size"] = "Unknown"
                except Exception:
                    info["key_size"] = "Unknown"
            elif "ecdsa" in info["public_key"]:
                info["key_type"] = "ECDSA"
                info["key_size"] = "Unknown"
    
    # Проверяем доступность SSH
    ssh_available, ssh_path = check_ssh_available()
    info["ssh_available"] = ssh_available
    info["ssh_path"] = ssh_path
    
    return info
