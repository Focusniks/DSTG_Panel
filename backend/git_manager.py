"""
Продвинутая система управления Git репозиториями для ботов
Поддерживает SSH ключи, автоматическое определение типа репозитория,
и улучшенную обработку ошибок
"""
import subprocess
import os
import shutil
import logging
import re
import uuid
import fnmatch
import tempfile
import stat
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional, Dict, Tuple, Any, List, Set
from backend.config import BASE_DIR
from backend.ssh_manager import (
    convert_https_to_ssh, 
    get_git_env_with_ssh, 
    setup_ssh_config_for_github, 
    get_ssh_key_exists,
    check_ssh_available,
    SSH_PRIVATE_KEY
)

logger = logging.getLogger(__name__)

# Поддерживаемые Git хостинги
GIT_HOSTS = {
    'github.com': {
        'ssh_port': 22,
        'https_port': 443
    },
    'gitlab.com': {
        'ssh_port': 22,
        'https_port': 443
    }
}

def is_git_repo(path: Path) -> bool:
    """Проверка, является ли директория Git репозиторием"""
    return (path / ".git").exists() or (path / ".git").is_dir()

def parse_gitignore(gitignore_path: Path) -> List[str]:
    """Парсинг .gitignore файла"""
    patterns = []
    if not gitignore_path.exists():
        return patterns
    
    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Пропускаем пустые строки и комментарии
                if not line or line.startswith('#'):
                    continue
                patterns.append(line)
    except Exception as e:
        logger.warning(f"Ошибка при чтении .gitignore: {e}")
    
    return patterns

def matches_gitignore_pattern(file_path: Path, pattern: str, base_path: Path) -> bool:
    """Проверка, соответствует ли файл паттерну .gitignore"""
    try:
        # Нормализуем путь
        rel_path = file_path.relative_to(base_path)
        rel_str = str(rel_path).replace('\\', '/')
        
        # Обрабатываем паттерны
        if pattern.startswith('/'):
            # Абсолютный паттерн от корня репозитория
            pattern = pattern[1:]
            return fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(rel_str, pattern + '/*')
        elif pattern.endswith('/'):
            # Директория
            pattern = pattern[:-1]
            return fnmatch.fnmatch(rel_str, pattern) or rel_str.startswith(pattern + '/')
        else:
            # Обычный паттерн
            return fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(rel_path.name, pattern) or any(
                fnmatch.fnmatch(part, pattern) for part in rel_str.split('/')
            )
    except Exception:
        return False

def get_ignored_files(base_path: Path, gitignore_patterns: List[str]) -> Set[Path]:
    """Получение списка файлов, соответствующих паттернам .gitignore"""
    ignored = set()
    
    if not gitignore_patterns:
        return ignored
    
    try:
        for root, dirs, files in os.walk(base_path):
            # Пропускаем .git директорию
            if '.git' in dirs:
                dirs.remove('.git')
            
            root_path = Path(root)
            
            # Проверяем файлы
            for file in files:
                file_path = root_path / file
                for pattern in gitignore_patterns:
                    if matches_gitignore_pattern(file_path, pattern, base_path):
                        ignored.add(file_path)
                        break
            
            # Проверяем директории
            for dir_name in dirs[:]:  # Копируем список для безопасного удаления
                dir_path = root_path / dir_name
                for pattern in gitignore_patterns:
                    if matches_gitignore_pattern(dir_path, pattern, base_path):
                        ignored.add(dir_path)
                        # Удаляем из dirs, чтобы не обходить содержимое
                        dirs.remove(dir_name)
                        break
    except Exception as e:
        logger.warning(f"Ошибка при получении игнорируемых файлов: {e}")
    
    return ignored


class GitRepository:
    """Класс для работы с Git репозиторием"""
    
    def __init__(self, path: Path, repo_url: Optional[str] = None, branch: str = "main"):
        self.path = Path(path)
        self.repo_url = repo_url
        self.branch = branch
        self.git_cmd = self._find_git_command()
        self._host_info = None
        
    def _find_git_command(self) -> Optional[str]:
        """Поиск команды git в системе"""
        candidates = [
            shutil.which("git"),
            "git",
        ]
        
        if os.name != 'nt':
            candidates.extend([
                "/usr/bin/git",
                "/usr/local/bin/git",
                "/bin/git"
            ])
        
        for candidate in candidates:
            if not candidate:
                continue
            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    return candidate
            except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
                continue
        
        return None
    
    def is_git_installed(self) -> bool:
        """Проверка установки Git"""
        return self.git_cmd is not None
    
    def is_repo(self) -> bool:
        """Проверка, является ли директория Git репозиторием"""
        return is_git_repo(self.path)
    
    def _get_remote_url(self) -> Optional[str]:
        """Получение URL удаленного репозитория"""
        if not self.git_cmd or not is_git_repo(self.path):
            return None
        
        try:
            result = subprocess.run(
                [self.git_cmd, "remote", "get-url", "origin"],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        
        return None
    
    def clone(self, repo_url: str, branch: str = "main") -> Tuple[bool, str]:
        """
        Клонирование репозитория с автоматическим выбором протокола (HTTPS/SSH)
        
        Логика:
        1. Если URL в формате SSH (git@...) - используем SSH (требует SSH клиент и ключ)
        2. Если SSH недоступен - ВСЕГДА используем HTTPS
        3. Если SSH доступен и есть ключ - пробуем SSH для HTTPS URL, при ошибке fallback на HTTPS
        4. Если SSH доступен, но нет ключа - используем HTTPS
        """
        if not self.git_cmd:
            return (False, "Команда Git не найдена")
        
        temp_dir = None
        try:
            # Используем временную директорию для клонирования
            temp_dir = Path(tempfile.mkdtemp(prefix="git_clone_"))
            
            # Проверяем доступность SSH и наличие ключа
            from backend.ssh_manager import check_ssh_available, get_ssh_key_exists
            ssh_available, ssh_path = check_ssh_available()
            ssh_key_exists = get_ssh_key_exists() if ssh_available else False
            
            # Определяем, является ли URL SSH-адресом
            is_ssh_url = repo_url.startswith("git@") or repo_url.startswith("ssh://")
            is_https_url = repo_url.startswith("https://")
            
            # Логика выбора протокола
            use_https = False
            clone_url = repo_url
            try_ssh_first = False
            
            if is_ssh_url:
                # Явно указан SSH URL - требуем SSH
                if not ssh_available:
                    return (False, "SSH URL указан, но SSH клиент не установлен. Установите OpenSSH клиент или используйте HTTPS URL.")
                if not ssh_key_exists:
                    return (False, "SSH URL указан, но SSH ключ не найден. Сгенерируйте SSH ключ в настройках панели или используйте HTTPS URL.")
                # Используем SSH URL как есть
                clone_url = repo_url
                try_ssh_first = True
                logger.info(f"Используем SSH URL: {clone_url}")
            elif not ssh_available:
                # SSH недоступен - используем HTTPS
                use_https = True
                clone_url = repo_url if is_https_url else self._convert_to_https(repo_url)
                logger.info(f"SSH недоступен, используем HTTPS: {clone_url}")
            elif not ssh_key_exists:
                # SSH доступен, но нет ключа - используем HTTPS
                use_https = True
                clone_url = repo_url if is_https_url else self._convert_to_https(repo_url)
                logger.info(f"SSH ключ не найден, используем HTTPS: {clone_url}")
            elif is_https_url:
                # HTTPS URL, SSH доступен и есть ключ - пробуем SSH, при ошибке fallback на HTTPS
                try_ssh_first = True
                clone_url = convert_https_to_ssh(repo_url)
                logger.info(f"Пробуем SSH для HTTPS URL: {clone_url}")
            else:
                # Неизвестный формат URL - пробуем как есть (скорее всего HTTPS)
                use_https = True
                clone_url = repo_url
                logger.info(f"Неизвестный формат URL, используем как есть: {clone_url}")
            
            # Подготавливаем окружение для первой попытки
            if use_https:
                env = self._get_https_env()
            else:
                env = self._get_ssh_env()
            
            # Первая попытка клонирования
            logger.info(f"Клонирование репозитория: {clone_url} (ветка: {branch})")
            result = subprocess.run(
                [self.git_cmd, "clone", "-b", branch, "--single-branch", clone_url, str(temp_dir)],
                capture_output=True,
                text=True,
                timeout=600,
                env=env
            )
            
            # Если первая попытка не удалась
            if result.returncode != 0:
                error_output = result.stderr or result.stdout or "Unknown error"
                
                # Проверяем, была ли это ошибка SSH
                is_ssh_error = (
                    "cannot run ssh" in error_output.lower() or
                    "No such file or directory" in error_output or
                    "unable to fork" in error_output.lower() or
                    "ssh:" in error_output.lower()
                )
                
                # Если это была попытка SSH и произошла ошибка SSH - пробуем HTTPS
                if try_ssh_first and is_ssh_error and is_https_url:
                    logger.warning(f"SSH не работает ({error_output[:200]}), пробуем HTTPS")
                    clone_url = repo_url  # Возвращаемся к оригинальному HTTPS URL
                    env = self._get_https_env()
                    result = subprocess.run(
                        [self.git_cmd, "clone", "-b", branch, "--single-branch", clone_url, str(temp_dir)],
                        capture_output=True,
                        text=True,
                        timeout=600,
                        env=env
                    )
                    if result.returncode == 0:
                        logger.info("Клонирование через HTTPS успешно")
                    else:
                        error_msg = result.stderr or result.stdout or "Unknown error"
                        return (False, f"Ошибка клонирования через HTTPS: {error_msg}")
                elif try_ssh_first and is_ssh_url:
                    # SSH URL не сработал - это критическая ошибка для SSH URL
                    return (False, self._format_ssh_error(error_output))
                elif result.returncode != 0:
                    # Другая ошибка
                    return (False, f"Ошибка клонирования: {error_output}")
            
            # Клонирование успешно, перемещаем файлы
            return self._move_cloned_files(temp_dir)
            
        except subprocess.TimeoutExpired:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            return (False, "Таймаут при клонировании репозитория")
        except Exception as e:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            logger.error(f"Ошибка клонирования репозитория: {e}", exc_info=True)
            return (False, f"Ошибка клонирования: {str(e)}")
    
    def _convert_to_https(self, url: str) -> str:
        """Конвертация URL в HTTPS формат"""
        if url.startswith("https://"):
            return url
        if "github.com" in url:
            return url.replace("git@github.com:", "https://github.com/").replace("ssh://git@github.com/", "https://github.com/")
        elif "gitlab.com" in url:
            return url.replace("git@gitlab.com:", "https://gitlab.com/").replace("ssh://git@gitlab.com/", "https://gitlab.com/")
        else:
            # Общий паттерн
            return url.replace("git@", "https://").replace("ssh://git@", "https://").replace(":", "/", 1)
    
    def _get_https_env(self) -> dict:
        """Получение окружения для HTTPS клонирования (без SSH)"""
        env = os.environ.copy()
        # Убираем все SSH-связанные переменные
        for key in list(env.keys()):
            if "SSH" in key.upper() or "GIT_SSH" in key.upper():
                del env[key]
        return env
    
    def _get_ssh_env(self) -> dict:
        """Получение окружения для SSH клонирования с проверкой доступности SSH"""
        try:
            # Сначала проверяем доступность SSH
            from backend.ssh_manager import check_ssh_available
            ssh_available, ssh_path = check_ssh_available()
            
            if not ssh_available:
                logger.warning("SSH недоступен, используем HTTPS окружение")
                return self._get_https_env()
            
            # Проверяем, что путь к SSH существует и доступен
            if ssh_path and not os.path.exists(ssh_path) and not shutil.which("ssh"):
                logger.warning(f"SSH путь не существует: {ssh_path}, используем HTTPS")
                return self._get_https_env()
            
            # Получаем SSH окружение
            env = get_git_env_with_ssh()
            
            # Дополнительная проверка: если GIT_SSH_COMMAND установлен, проверяем что SSH доступен
            if "GIT_SSH_COMMAND" in env:
                ssh_cmd = env["GIT_SSH_COMMAND"]
                # Извлекаем путь к ssh из команды
                ssh_match = re.search(r"['\"]?([^'\"]*ssh[^'\"]*)['\"]?", ssh_cmd)
                if ssh_match:
                    cmd_ssh_path = ssh_match.group(1).split()[0] if ssh_match.group(1) else None
                    if cmd_ssh_path:
                        # Проверяем, что путь существует или доступен через which
                        if not os.path.exists(cmd_ssh_path) and not shutil.which(cmd_ssh_path):
                            logger.warning(f"SSH путь в GIT_SSH_COMMAND не существует: {cmd_ssh_path}, используем HTTPS")
                            return self._get_https_env()
            
            return env
        except Exception as e:
            logger.warning(f"Ошибка при получении SSH окружения: {e}, используем HTTPS")
            return self._get_https_env()
    
    def _format_ssh_error(self, error_output: str) -> str:
        """Форматирование ошибки SSH для пользователя"""
        if "Permission denied" in error_output or "publickey" in error_output.lower():
            return (
                f"Ошибка аутентификации SSH:\n{error_output}\n\n"
                "Проверьте:\n"
                "1. SSH ключ добавлен в настройки Git хостинга (GitHub/GitLab)\n"
                "2. SSH ключ сгенерирован в настройках панели\n"
                "3. Правильность URL репозитория\n"
                "4. Попробуйте использовать HTTPS URL вместо SSH"
            )
        elif "Host key verification failed" in error_output:
            return (
                f"Ошибка проверки SSH ключа хоста:\n{error_output}\n\n"
                "Попробуйте протестировать SSH подключение в настройках панели или используйте HTTPS URL"
            )
        elif "cannot run ssh" in error_output.lower() or "No such file or directory" in error_output:
            return (
                f"SSH клиент не найден:\n{error_output}\n\n"
                "Установите OpenSSH клиент или используйте HTTPS URL для клонирования"
            )
        else:
            return f"Ошибка клонирования через SSH:\n{error_output}\n\nПопробуйте использовать HTTPS URL"
    
    def _move_cloned_files(self, temp_dir: Path) -> Tuple[bool, str]:
        """Перемещение файлов из временной директории в целевую"""
        try:
            # Создаем целевую директорию если не существует
            self.path.mkdir(parents=True, exist_ok=True)
            
            # Перемещаем все файлы из временной директории
            for item in temp_dir.iterdir():
                if item.name != '.git':
                    dest = self.path / item.name
                    if item.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
            
            # Перемещаем .git директорию
            git_source = temp_dir / ".git"
            git_dest = self.path / ".git"
            if git_source.exists():
                if git_dest.exists():
                    shutil.rmtree(git_dest)
                shutil.move(str(git_source), str(git_dest))
            
            # Удаляем временную директорию
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return (True, "Репозиторий успешно клонирован")
        except Exception as move_error:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return (False, f"Ошибка при перемещении файлов: {str(move_error)}")
    

    
    def update(self) -> Tuple[bool, str]:
        """Обновление репозитория из удаленного источника с учетом .gitignore"""
        if not self.git_cmd:
            return (False, "Команда Git не найдена")
        
        if not is_git_repo(self.path):
            return (False, "Not a git repository")
        
        try:
            env = get_git_env_with_ssh()
            
            # Читаем .gitignore если он существует
            gitignore_path = self.path / ".gitignore"
            gitignore_patterns = []
            ignored_files = set()
            
            if gitignore_path.exists():
                gitignore_patterns = parse_gitignore(gitignore_path)
                if gitignore_patterns:
                    logger.info(f"Найдено {len(gitignore_patterns)} паттернов в .gitignore")
                    # Получаем список игнорируемых файлов
                    ignored_files = get_ignored_files(self.path, gitignore_patterns)
                    logger.info(f"Найдено {len(ignored_files)} файлов для игнорирования")
            
            # Сохраняем игнорируемые файлы во временную директорию
            backup_dir = None
            if ignored_files:
                backup_dir = Path(tempfile.mkdtemp(prefix="gitignore_backup_"))
                logger.info(f"Создана временная директория для бэкапа: {backup_dir}")
                
                for ignored_file in ignored_files:
                    try:
                        if ignored_file.exists():
                            # Сохраняем относительный путь
                            rel_path = ignored_file.relative_to(self.path)
                            backup_path = backup_dir / rel_path
                            backup_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            if ignored_file.is_file():
                                shutil.copy2(ignored_file, backup_path)
                            elif ignored_file.is_dir():
                                shutil.copytree(ignored_file, backup_path, dirs_exist_ok=True)
                            
                            logger.debug(f"Сохранен игнорируемый файл: {ignored_file} -> {backup_path}")
                    except Exception as backup_error:
                        logger.warning(f"Не удалось сохранить игнорируемый файл {ignored_file}: {backup_error}")
            
            # Получаем изменения
            result = subprocess.run(
                [self.git_cmd, "pull", "origin", self.branch],
                cwd=self.path,
                env=env,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                # Восстанавливаем игнорируемые файлы
                if backup_dir and backup_dir.exists():
                    logger.info("Восстановление игнорируемых файлов из .gitignore...")
                    for ignored_file in ignored_files:
                        try:
                            rel_path = ignored_file.relative_to(self.path)
                            backup_path = backup_dir / rel_path
                            
                            if backup_path.exists():
                                if ignored_file.is_file() or not ignored_file.exists():
                                    # Создаем директорию если нужно
                                    ignored_file.parent.mkdir(parents=True, exist_ok=True)
                                    if backup_path.is_file():
                                        shutil.copy2(backup_path, ignored_file)
                                elif ignored_file.is_dir() and backup_path.is_dir():
                                    # Восстанавливаем директорию
                                    if ignored_file.exists():
                                        shutil.rmtree(ignored_file)
                                    shutil.copytree(backup_path, ignored_file)
                                
                                logger.debug(f"Восстановлен игнорируемый файл: {backup_path} -> {ignored_file}")
                        except Exception as restore_error:
                            logger.warning(f"Не удалось восстановить игнорируемый файл {ignored_file}: {restore_error}")
                    
                    # Удаляем временную директорию
                    try:
                        shutil.rmtree(backup_dir)
                    except Exception as cleanup_error:
                        logger.warning(f"Не удалось удалить временную директорию {backup_dir}: {cleanup_error}")
                
                return (True, "Repository updated successfully")
            else:
                # Восстанавливаем игнорируемые файлы даже при ошибке
                if backup_dir and backup_dir.exists():
                    logger.info("Восстановление игнорируемых файлов после ошибки обновления...")
                    for ignored_file in ignored_files:
                        try:
                            rel_path = ignored_file.relative_to(self.path)
                            backup_path = backup_dir / rel_path
                            if backup_path.exists():
                                ignored_file.parent.mkdir(parents=True, exist_ok=True)
                                if backup_path.is_file():
                                    shutil.copy2(backup_path, ignored_file)
                                elif backup_path.is_dir():
                                    if ignored_file.exists():
                                        shutil.rmtree(ignored_file)
                                    shutil.copytree(backup_path, ignored_file)
                        except Exception:
                            pass
                    try:
                        shutil.rmtree(backup_dir)
                    except Exception:
                        pass
                
                error_msg = result.stderr or result.stdout or "Неизвестная ошибка"
                return (False, f"Ошибка Git pull: {error_msg}")
        except subprocess.TimeoutExpired:
            return (False, "Git pull timeout")
        except Exception as e:
            logger.error(f"Error updating repository: {e}", exc_info=True)
            return (False, f"Ошибка: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса репозитория"""
        if not self.git_cmd or not is_git_repo(self.path):
            return {
                "is_repo": False,
                "branch": None,
                "commit": None,
                "last_commit": None,
                "remote": None,
                "status": "not_a_repo"
            }
        
        try:
            # Определяем окружение: для панели используем HTTPS, для ботов - SSH
            from backend.config import BASE_DIR
            is_panel = self.path == BASE_DIR
            
            if is_panel:
                # Для панели используем HTTPS окружение (без SSH)
                env = os.environ.copy()
                if "GIT_SSH_COMMAND" in env:
                    del env["GIT_SSH_COMMAND"]
            else:
                # Для ботов используем SSH окружение
                env = get_git_env_with_ssh()
            
            # Получаем текущую ветку
            branch_result = subprocess.run(
                [self.git_cmd, "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.path,
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )
            current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
            
            # Получаем последний коммит (хеш)
            commit_result = subprocess.run(
                [self.git_cmd, "rev-parse", "--short", "HEAD"],
                cwd=self.path,
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )
            commit_hash = commit_result.stdout.strip() if commit_result.returncode == 0 else None
            
            # Получаем сообщение последнего коммита
            commit_message = None
            commit_date = None
            if commit_hash:
                try:
                    # Получаем сообщение коммита
                    message_result = subprocess.run(
                        [self.git_cmd, "log", "-1", "--pretty=format:%s", "HEAD"],
                        cwd=self.path,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if message_result.returncode == 0:
                        commit_message = message_result.stdout.strip()
                    
                    # Получаем дату коммита
                    date_result = subprocess.run(
                        [self.git_cmd, "log", "-1", "--pretty=format:%ci", "HEAD"],
                        cwd=self.path,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if date_result.returncode == 0:
                        commit_date = date_result.stdout.strip()
                except Exception as e:
                    logger.warning(f"Не удалось получить детали коммита: {e}")
            
            # Формируем объект last_commit для фронтенда
            last_commit = None
            if commit_hash:
                last_commit = {
                    "hash": commit_hash,
                    "message": commit_message or "Без сообщения",
                    "date": commit_date or None
                }
            
            # Получаем remote URL
            remote_result = subprocess.run(
                [self.git_cmd, "remote", "get-url", "origin"],
                cwd=self.path,
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )
            remote_url = remote_result.stdout.strip() if remote_result.returncode == 0 else None
            
            # Проверяем статус
            status_result = subprocess.run(
                [self.git_cmd, "status", "--porcelain"],
                cwd=self.path,
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )
            has_changes = bool(status_result.stdout.strip()) if status_result.returncode == 0 else False
            
            # Проверяем наличие обновлений в удаленном репозитории
            has_updates = False
            if current_branch and remote_url:
                try:
                    # Делаем fetch для получения информации об удаленном репозитории
                    # Для панели используем HTTPS, для ботов - SSH если настроено
                    # env уже настроен правильно выше (HTTPS для панели, SSH для ботов)
                    fetch_result = subprocess.run(
                        [self.git_cmd, "fetch", "origin", current_branch],
                        cwd=self.path,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if fetch_result.returncode == 0:
                        # Сравниваем локальный и удаленный коммиты
                        local_commit_result = subprocess.run(
                            [self.git_cmd, "rev-parse", "HEAD"],
                            cwd=self.path,
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        remote_commit_result = subprocess.run(
                            [self.git_cmd, "rev-parse", f"origin/{current_branch}"],
                            cwd=self.path,
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        
                        if (local_commit_result.returncode == 0 and 
                            remote_commit_result.returncode == 0):
                            local_commit = local_commit_result.stdout.strip()
                            remote_commit = remote_commit_result.stdout.strip()
                            
                            # Если коммиты разные, есть обновления
                            if local_commit != remote_commit:
                                # Проверяем, что удаленный коммит новее
                                behind_result = subprocess.run(
                                    [self.git_cmd, "rev-list", "--count", f"HEAD..origin/{current_branch}"],
                                    cwd=self.path,
                                    env=env,
                                    capture_output=True,
                                    text=True,
                                    timeout=10
                                )
                                if behind_result.returncode == 0:
                                    behind_count = int(behind_result.stdout.strip() or "0")
                                    has_updates = behind_count > 0
                except Exception as fetch_error:
                    logger.warning(f"Не удалось проверить наличие обновлений: {fetch_error}")
            
            return {
                "is_repo": True,
                "branch": current_branch or self.branch,
                "current_branch": current_branch or self.branch,
                "commit": commit_hash,
                "last_commit": last_commit,
                "remote": remote_url,
                "has_changes": has_changes,
                "has_updates": has_updates,
                "status": "clean" if not has_changes else "dirty"
            }
        except Exception as e:
            logger.error(f"Error getting git status: {e}", exc_info=True)
            return {
                "is_repo": True,
                "branch": self.branch,
                "commit": None,
                "last_commit": None,
                "remote": None,
                "status": "error"
            }


def update_bot_from_git(bot_dir: Path, repo_url: str, branch: str = "main") -> Tuple[bool, str]:
    """Обновление бота из Git репозитория"""
    repo = GitRepository(bot_dir, repo_url, branch)
    
    if not repo.is_git_installed():
        return (False, "Git не установлен")
    
    if not repo.is_repo():
        return repo.clone(repo_url, branch)

    else:
        return repo.update()


def update_panel_from_git() -> Tuple[bool, str]:
    """Обновление панели из Git репозитория по HTTPS с сохранением bots/ и data/.

    Важно:
    - Для панели мы всегда используем HTTPS URL (`PANEL_REPO_URL`), без SSH.
    - Git используется только локально, без SSH-ключей и без `GIT_SSH_COMMAND`.
    - Обновляются ВСЕ отслеживаемые файлы панели, кроме директорий `bots/` и `data/`,
      которые бэкапятся и восстанавливаются после обновления.
    """
    from backend.config import PANEL_REPO_URL, PANEL_REPO_BRANCH, BOTS_DIR, DATA_DIR

    # Находим git
    git_cmd = None
    candidates = [shutil.which("git"), "git"]
    if os.name != "nt":
        candidates.extend(["/usr/bin/git", "/usr/local/bin/git", "/bin/git"])

    for candidate in candidates:
        if not candidate:
            continue
        try:
            result = subprocess.run(
                [candidate, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                git_cmd = candidate
                break
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            continue
    
    if not git_cmd:
        return (False, "Git не найден в системе. Установите git и повторите попытку.")

    # Проверяем, что панель установлена как git‑репозиторий
    if not is_git_repo(BASE_DIR):
        return (
            False,
            "Панель не является Git репозиторием. "
            "Инициализируйте Git в настройках панели или установите панель из репозитория.",
        )

    # Готовим HTTPS URL (на всякий случай отрезаем .git / добавляем его обратно)
    repo_url = PANEL_REPO_URL
    if repo_url.startswith("git@") or repo_url.startswith("ssh://"):
        # На случай, если кто-то изменил PANEL_REPO_URL
        repo_url = repo_url.replace("git@github.com:", "https://github.com/").replace(
            "ssh://git@github.com/", "https://github.com/"
        )
    if not repo_url.startswith("https://"):
        repo_url = "https://github.com/Focusniks/DSTG_Panel.git"
    if not repo_url.endswith(".git"):
        repo_url += ".git"

    logger.info(f"Обновление панели из Git по HTTPS: {repo_url}, ветка: {PANEL_REPO_BRANCH}")

    # Подготавливаем окружение без SSH‑переменных
    env = os.environ.copy()
    if "GIT_SSH_COMMAND" in env:
        logger.info(f"Удаляем GIT_SSH_COMMAND из окружения (было: {env['GIT_SSH_COMMAND']})")
        del env["GIT_SSH_COMMAND"]
    # Убираем любые SSH‑переменные (на всякий случай)
    for key in list(env.keys()):
        if "SSH" in key.upper():
            logger.info(f"Удаляем переменную окружения: {key}")
            del env[key]

    # Бэкапим bots/ и data/
    try:
        backup_dir = Path(tempfile.mkdtemp(prefix="panel_update_backup_"))
        logger.info(f"Создана временная директория для бэкапа: {backup_dir}")
    except Exception as e:
        logger.error(f"Не удалось создать временную директорию: {e}", exc_info=True)
        return (False, f"Не удалось создать временную директорию для бэкапа: {str(e)}")

    protected_dirs: List[Tuple[str, Path]] = []
    if BOTS_DIR.exists() and BOTS_DIR.is_dir():
        protected_dirs.append(("bots", BOTS_DIR))
    if DATA_DIR.exists() and DATA_DIR.is_dir():
        protected_dirs.append(("data", DATA_DIR))

    for dir_name, dir_path in protected_dirs:
        try:
            backup_path = backup_dir / dir_name
            if dir_path.exists() and dir_path.is_dir():
                logger.info(f"Сохранение директории {dir_name}...")
                if backup_path.exists():
                    shutil.rmtree(backup_path)
                shutil.copytree(dir_path, backup_path, dirs_exist_ok=True)
                logger.info(f"Директория {dir_name} сохранена в бэкап")
        except Exception as backup_error:
            logger.error(f"Ошибка при сохранении директории {dir_name}: {backup_error}", exc_info=True)

    try:
        # 1) fetch по HTTPS напрямую с URL (обходим origin и любую SSH‑конфигурацию)
        logger.info("Выполняем git fetch по HTTPS (без SSH)...")
        fetch_result = subprocess.run(
            [git_cmd, "-C", str(BASE_DIR), "fetch", repo_url, PANEL_REPO_BRANCH],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if fetch_result.returncode != 0:
            error_msg = fetch_result.stderr or fetch_result.stdout or "Неизвестная ошибка"
            logger.error(f"Git fetch failed: {error_msg}")
            return (False, f"Ошибка Git fetch: {error_msg}")

        logger.info("Git fetch успешно выполнен, выполняем reset --hard FETCH_HEAD")

        # 2) reset --hard FETCH_HEAD (принудительно обновляем рабочее дерево до полученного коммита)
        reset_result = subprocess.run(
            [git_cmd, "-C", str(BASE_DIR), "reset", "--hard", "FETCH_HEAD"],
            env=env,
                capture_output=True,
                text=True,
            timeout=300,
        )

        if reset_result.returncode != 0:
            error_msg = reset_result.stderr or reset_result.stdout or "Неизвестная ошибка"
            logger.error(f"Git reset --hard failed: {error_msg}")
            return (False, f"Ошибка Git reset: {error_msg}")

        logger.info("Git reset --hard успешно выполнен")

        # 3) Восстанавливаем защищаемые директории
        logger.info("Восстановление защищаемых директорий (bots, data)...")
        for dir_name, dir_path in protected_dirs:
            try:
                backup_path = backup_dir / dir_name
                if backup_path.exists() and backup_path.is_dir():
                    if dir_path.exists():
                        shutil.rmtree(dir_path)
                    shutil.copytree(backup_path, dir_path, dirs_exist_ok=True)
                    logger.info(f"Директория {dir_name} восстановлена")
            except Exception as restore_error:
                logger.error(f"Ошибка при восстановлении директории {dir_name}: {restore_error}", exc_info=True)

        return (
            True,
            "Панель успешно обновлена из Git по HTTPS. Защищенные директории (bots/, data/) сохранены.",
        )

    except subprocess.TimeoutExpired:
        logger.error("Git операция завершилась по таймауту")
        return (False, "Git операция завершилась по таймауту")
    except Exception as e:
        logger.error(f"Критическая ошибка при обновлении панели из Git: {e}", exc_info=True)
        return (False, f"Ошибка обновления панели из Git: {str(e)}")
    finally:
        # Чистим временный бэкап
        try:
            if "backup_dir" in locals() and backup_dir.exists():
                shutil.rmtree(backup_dir)
        except Exception:
            pass


def get_git_status(path: Path) -> Dict[str, Any]:
    """Получение статуса Git репозитория"""
    repo = GitRepository(path)
    return repo.get_status()


def get_git_remote(path: Path) -> Optional[str]:
    """Получение URL удаленного репозитория"""
    if not is_git_repo(path):
        return None
    
    try:
        # Надежный поиск Git команды
        git_cmd = None
        candidates = [
            shutil.which("git"),
            "git",
        ]
        
        if os.name != 'nt':
            candidates.extend([
                "/usr/bin/git",
                "/usr/local/bin/git",
                "/bin/git"
            ])
        
        for candidate in candidates:
            if not candidate:
                continue
            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    git_cmd = candidate
                    break
            except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
                continue
        
        if not git_cmd:
            return None
        
        env = get_git_env_with_ssh()
        result = subprocess.run(
            [git_cmd, "remote", "get-url", "origin"],
            cwd=path,
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    
    return None


def init_git_repo(path: Path, repo_url: Optional[str] = None) -> Tuple[bool, str]:
    """Инициализация Git репозитория"""
    try:
        # Надежный поиск Git команды (используем тот же метод, что и в GitRepository)
        git_cmd = None
        candidates = [
            shutil.which("git"),
            "git",
        ]
        
        if os.name != 'nt':
            candidates.extend([
                "/usr/bin/git",
                "/usr/local/bin/git",
                "/bin/git"
            ])
        
        for candidate in candidates:
            if not candidate:
                continue
            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    git_cmd = candidate
                    break
            except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
                continue
        
        if not git_cmd:
            return (False, "Git не установлен. Установите Git: sudo apt-get install git (Ubuntu/Debian) или sudo yum install git (CentOS/RHEL)")
        
        # Инициализируем репозиторий
        result = subprocess.run(
            [git_cmd, "init"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return (False, f"Ошибка инициализации Git: {result.stderr}")
        
        # Если указан URL, добавляем remote
        if repo_url:
            # Для панели всегда используем HTTPS (публичный репозиторий)
            # Для ботов используем SSH если URL начинается с https://
            use_https = False
            if repo_url.startswith("https://"):
                # Проверяем, это репозиторий панели или нет
                from backend.config import PANEL_REPO_URL
                if repo_url == PANEL_REPO_URL or path == BASE_DIR:
                    use_https = True
                    logger.info("Используем HTTPS для репозитория панели")
            
            if use_https:
                # Используем HTTPS напрямую
                remote_url = repo_url
                env = os.environ.copy()
            else:
                # Конвертируем HTTPS в SSH для приватных репозиториев ботов
                remote_url = convert_https_to_ssh(repo_url)
                env = get_git_env_with_ssh()
            
            result = subprocess.run(
                [git_cmd, "remote", "add", "origin", remote_url],
                cwd=path,
                env=env,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                # Если remote уже существует, обновляем его
                result = subprocess.run(
                    [git_cmd, "remote", "set-url", "origin", remote_url],
                    cwd=path,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    return (False, f"Не удалось установить remote URL: {result.stderr}")
        
        return (True, "Git repository initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing git repo: {e}", exc_info=True)
        return (False, f"Error: {str(e)}")


def set_git_remote(path: Path, repo_url: str) -> bool:
    """Установка URL удаленного репозитория"""
    if not is_git_repo(path):
        return False
    
    try:
        # Надежный поиск Git команды
        git_cmd = None
        candidates = [
            shutil.which("git"),
            "git",
        ]
        
        if os.name != 'nt':
            candidates.extend([
                "/usr/bin/git",
                "/usr/local/bin/git",
                "/bin/git"
            ])
        
        for candidate in candidates:
            if not candidate:
                continue
            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    git_cmd = candidate
                    break
            except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
                continue
        
        if not git_cmd:
            return False
        
        ssh_url = convert_https_to_ssh(repo_url)
        env = get_git_env_with_ssh()
        
        # Сначала пробуем добавить remote
        result = subprocess.run(
            [git_cmd, "remote", "add", "origin", ssh_url],
            cwd=path,
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Если remote уже существует, обновляем его
        if result.returncode != 0:
            result = subprocess.run(
                [git_cmd, "remote", "set-url", "origin", ssh_url],
                cwd=path,
                env=env,
                capture_output=True,
                text=True,
                timeout=30
            )
        
        return result.returncode == 0
    except Exception:
        return False
