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
from pathlib import Path
from typing import Optional, Dict, Tuple, Any, List
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
        'name': 'GitHub',
        'ssh_user': 'git',
        'supports_ssh': True
    },
    'gitlab.com': {
        'name': 'GitLab',
        'ssh_user': 'git',
        'supports_ssh': True
    },
    'bitbucket.org': {
        'name': 'Bitbucket',
        'ssh_user': 'git',
        'supports_ssh': True
    }
}


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
    
    def _get_host_info(self, url: str) -> Optional[Dict]:
        """Получение информации о Git хосте"""
        if self._host_info:
            return self._host_info
        
        # Извлекаем хост из URL
        host = None
        if url.startswith('https://'):
            host = url.split('/')[2]
        elif url.startswith('git@'):
            host = url.split('@')[1].split(':')[0]
        elif url.startswith('http://'):
            host = url.split('/')[2]
        
        if host:
            # Убираем порт если есть
            host = host.split(':')[0]
            self._host_info = GIT_HOSTS.get(host)
        
        return self._host_info
    
    def is_git_installed(self) -> bool:
        """Проверка установки Git"""
        return self.git_cmd is not None
    
    def is_repo(self) -> bool:
    """Проверка, является ли директория Git репозиторием"""
        git_dir = self.path / ".git"
    return git_dir.exists() and git_dir.is_dir()

    def get_remote_url(self) -> Optional[str]:
    """Получение URL удаленного репозитория"""
        if not self.is_repo() or not self.git_cmd:
            return None
        
    try:
        result = subprocess.run(
                [self.git_cmd, "remote", "get-url", "origin"],
                cwd=str(self.path),
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
            pass
        return None

    def normalize_url(self, url: str, prefer_ssh: bool = True) -> Tuple[str, bool]:
        """
        Нормализация URL репозитория
        Returns: (normalized_url, is_ssh)
        """
        url = url.strip()
        
        # Если уже SSH формат
        if url.startswith('git@'):
            return url, True
        
        # Если HTTPS формат
        if url.startswith('https://'):
            if prefer_ssh:
                # Преобразуем в SSH
                ssh_url = convert_https_to_ssh(url)
                return ssh_url, True
            return url, False
        
        # Если HTTP формат, преобразуем в HTTPS
        if url.startswith('http://'):
            url = url.replace('http://', 'https://', 1)
            if prefer_ssh:
                ssh_url = convert_https_to_ssh(url)
                return ssh_url, True
            return url, False
        
        # Если формат не распознан, возвращаем как есть
        return url, url.startswith('git@')
    
    def can_use_ssh(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Проверка возможности использования SSH
        Returns: (can_use, error_message)
        """
        host_info = self._get_host_info(url)
        if not host_info:
            return True, None  # Неизвестный хост, пробуем SSH
        
        if not host_info.get('supports_ssh', False):
            return False, f"{host_info['name']} не поддерживает SSH"
        
        # Проверяем наличие SSH клиента
        ssh_available, _ = check_ssh_available()
        if not ssh_available:
            return False, "SSH клиент не установлен"
        
        # Проверяем наличие SSH ключа
        if not get_ssh_key_exists():
            return False, "SSH ключ не найден. Сгенерируйте ключ в настройках панели"
        
        return True, None
    
    def prepare_ssh_environment(self) -> Dict[str, str]:
        """Подготовка окружения для SSH операций"""
        env = os.environ.copy()
        
        # Настраиваем SSH config
        if get_ssh_key_exists():
            setup_ssh_config_for_github()
            env = get_git_env_with_ssh()
        
        return env
    
    def clone(self, url: Optional[str] = None, branch: Optional[str] = None) -> Tuple[bool, str]:
        """
        Клонирование репозитория
        
        Args:
            url: URL репозитория (если None, используется self.repo_url)
            branch: Ветка для клонирования (если None, используется self.branch)
        
        Returns:
            (success, message)
        """
        if not self.git_cmd:
            return False, "Git не установлен. Установите Git для работы с репозиториями."
        
        # Используем переданные параметры или значения из объекта
        clone_url = url if url is not None else self.repo_url
        clone_branch = branch if branch is not None else self.branch
        
        if not clone_url:
            return False, "URL репозитория не указан"
        
        try:
            # Нормализуем URL (предпочитаем SSH для приватных репозиториев)
            normalized_url, is_ssh = self.normalize_url(clone_url, prefer_ssh=True)
            
            # Проверяем возможность использования SSH
            if is_ssh:
                can_use, error = self.can_use_ssh(normalized_url)
                if not can_use:
                    # Если SSH недоступен, пробуем HTTPS
                    logger.warning(f"SSH недоступен: {error}. Пробуем HTTPS...")
                    normalized_url, is_ssh = self.normalize_url(clone_url, prefer_ssh=False)
                    is_ssh = False
            
            # Подготавливаем окружение
            env = self.prepare_ssh_environment() if is_ssh else os.environ.copy()
            
            # Убеждаемся, что родительская директория существует
            self.path.parent.mkdir(parents=True, exist_ok=True)
            
            # Если директория существует и не пуста, очищаем её
            if self.path.exists():
                # Проверяем, что это не Git репозиторий
                if not self.is_repo():
                    # Удаляем содержимое, кроме config.json
                    for item in self.path.iterdir():
                        if item.name not in ['config.json', '.gitkeep']:
                            try:
                                if item.is_dir():
                                    shutil.rmtree(item)
                                else:
                                    item.unlink()
                            except Exception as e:
                                logger.warning(f"Не удалось удалить {item}: {e}")
                    
                    # Если директория пуста (кроме config.json), удаляем её для git clone
                    remaining = [f for f in self.path.iterdir() if f.name != 'config.json']
                    if not remaining:
                        try:
                            if (self.path / 'config.json').exists():
                                # Временно перемещаем config.json
                                temp_config = self.path.parent / f"config_{self.path.name}.tmp"
                                shutil.move(str(self.path / 'config.json'), str(temp_config))
                            self.path.rmdir()
                        except Exception:
                            pass
            
            # Логируем операцию
            logger.info(f"Клонирование репозитория: {normalized_url} (ветка: {clone_branch}) в {self.path}")
            logger.debug(f"Используется SSH: {is_ssh}")
            
            # Выполняем клонирование
            cmd = [self.git_cmd, "clone", "-b", clone_branch, "--depth", "1", normalized_url, str(self.path)]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                env=env
            )
            
            if result.returncode == 0:
                logger.info(f"Репозиторий успешно клонирован")
                return True, f"Репозиторий успешно клонирован (ветка: {clone_branch})"
            
            # Обработка ошибок
            error_msg = self._parse_clone_error(result.stderr, result.stdout, is_ssh)
            logger.error(f"Ошибка клонирования: {error_msg}")
            return False, error_msg
            
        except subprocess.TimeoutExpired:
            return False, "Превышено время ожидания при клонировании репозитория (5 минут)"
        except Exception as e:
            logger.error(f"Исключение при клонировании: {e}", exc_info=True)
            return False, f"Ошибка клонирования: {str(e)}"
    
    def _parse_clone_error(self, stderr: str, stdout: str, used_ssh: bool) -> str:
        """Парсинг и форматирование ошибок клонирования"""
        combined = f"{stderr} {stdout}".strip()
        
        # Проверка на отсутствие SSH клиента
        if "ssh: not found" in combined or "ssh: command not found" in combined:
            return (
                "SSH клиент не установлен.\n\n"
                "Установите OpenSSH клиент:\n"
                "  • Debian/Ubuntu: sudo apt-get install openssh-client\n"
                "  • CentOS/RHEL: sudo yum install openssh-clients\n"
                "  • Alpine: apk add openssh-client\n"
                "  • Windows: Установите Git for Windows (включает SSH)"
            )
        
        # Проверка на проблемы с аутентификацией SSH
        if "Permission denied" in combined or "Host key verification failed" in combined:
            if used_ssh:
                return (
                    "Ошибка SSH аутентификации.\n\n"
                    "Проверьте:\n"
                    "  1. SSH ключ добавлен в ваш GitHub/GitLab аккаунт\n"
                    "  2. Ключ сгенерирован в настройках панели\n"
                    "  3. У вас есть доступ к репозиторию"
                )
            else:
                return "Ошибка доступа к репозиторию. Проверьте URL и права доступа."
        
        # Проверка на несуществующий репозиторий
        if "repository not found" in combined.lower() or "not found" in combined.lower():
            return (
                "Репозиторий не найден.\n\n"
                "Проверьте:\n"
                "  1. URL репозитория правильный\n"
                "  2. Репозиторий существует\n"
                "  3. У вас есть доступ к репозиторию"
            )
        
        # Проверка на проблемы с сетью
        if "Could not resolve hostname" in combined or "Connection refused" in combined:
            return "Ошибка подключения. Проверьте интернет-соединение и доступность Git хостинга."
        
        # Проверка на проблемы с веткой
        if "not found in upstream origin" in combined or "branch" in combined.lower():
            return f"Ветка '{self.branch}' не найдена в репозитории. Проверьте название ветки."
        
        # Общая ошибка
        error_lines = stderr.split('\n') if stderr else []
        fatal_lines = [line for line in error_lines if 'fatal:' in line.lower()]
        
        if fatal_lines:
            # Берем последнюю строку с fatal
            last_fatal = fatal_lines[-1].replace('fatal:', '').strip()
            if last_fatal:
                return f"Ошибка Git: {last_fatal}"
        
        # Если ничего не подошло, возвращаем общее сообщение
        return f"Ошибка клонирования репозитория. Детали: {combined[:200]}"
    
    def update(self, url: Optional[str] = None, branch: Optional[str] = None) -> Tuple[bool, str]:
        """
        Обновление репозитория из удаленного источника
        
        Args:
            url: URL репозитория (если None, используется текущий remote)
            branch: Ветка для обновления (если None, используется self.branch)
        
        Returns:
            (success, message)
        """
        if not self.git_cmd:
            return False, "Git не установлен. Установите Git для работы с репозиториями."
        
        if not self.is_repo():
            # Если репозиторий не инициализирован, клонируем
            update_url = url if url is not None else self.repo_url
            if update_url:
                return self.clone(update_url, branch)
            return False, "Репозиторий не инициализирован и URL не указан"
        
        update_branch = branch if branch is not None else self.branch
        update_url = url if url is not None else self.repo_url
        
        try:
            # Нормализуем URL если указан
            is_ssh = False
            if update_url:
                normalized_url, is_ssh = self.normalize_url(update_url, prefer_ssh=True)
                if is_ssh:
                    can_use, error = self.can_use_ssh(normalized_url)
                    if not can_use:
                        normalized_url, is_ssh = self.normalize_url(update_url, prefer_ssh=False)
                
                # Обновляем remote если нужно
                current_remote = self.get_remote_url()
                if current_remote != normalized_url:
                    self._set_remote(normalized_url)
            
            # Подготавливаем окружение
            env = self.prepare_ssh_environment() if is_ssh else os.environ.copy()
            
            # Сохраняем локальные изменения
            logger.info(f"Сохранение локальных изменений...")
            stash_result = subprocess.run(
                [self.git_cmd, "stash", "push", "-m", "Panel auto-stash"],
                cwd=str(self.path),
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
            # Не критично, если stash не удался
            
            # Получаем обновления
            logger.info(f"Получение обновлений из удаленного репозитория...")
            fetch_result = subprocess.run(
                [self.git_cmd, "fetch", "origin"],
                cwd=str(self.path),
                capture_output=True,
                text=True,
                timeout=120,
                env=env
            )
            
            if fetch_result.returncode != 0:
                error_msg = fetch_result.stderr or "Неизвестная ошибка"
                return False, f"Ошибка получения обновлений: {error_msg}"
            
            # Проверяем, есть ли обновления
            check_result = subprocess.run(
                [self.git_cmd, "rev-list", "--count", f"HEAD..origin/{update_branch}"],
                cwd=str(self.path),
                capture_output=True,
                text=True,
                timeout=10,
                env=env
            )
            
            commits_ahead = 0
            if check_result.returncode == 0:
                try:
                    commits_ahead = int(check_result.stdout.strip() or "0")
                except ValueError:
                    pass
            
            if commits_ahead == 0:
                return True, "Репозиторий уже актуален, обновлений нет"
            
            # Выполняем обновление
            logger.info(f"Применение обновлений ({commits_ahead} коммитов)...")
            pull_result = subprocess.run(
                [self.git_cmd, "pull", "origin", update_branch],
                cwd=str(self.path),
                capture_output=True,
                text=True,
                timeout=180,
                env=env
            )
            
            if pull_result.returncode == 0:
                return True, f"Репозиторий успешно обновлен ({commits_ahead} коммитов применено)"
            
            error_msg = pull_result.stderr or "Неизвестная ошибка"
            return False, f"Ошибка обновления: {error_msg}"
            
        except subprocess.TimeoutExpired:
            return False, "Превышено время ожидания при обновлении репозитория"
        except Exception as e:
            logger.error(f"Исключение при обновлении: {e}", exc_info=True)
            return False, f"Ошибка обновления: {str(e)}"
    
    def _set_remote(self, url: str) -> Tuple[bool, str]:
    """Установка удаленного репозитория"""
    try:
        # Проверяем существование remote
        result = subprocess.run(
                [self.git_cmd, "remote", "get-url", "origin"],
                cwd=str(self.path),
            capture_output=True,
            timeout=5
        )
        
        if result.returncode == 0:
            # Обновляем существующий remote
            result = subprocess.run(
                    [self.git_cmd, "remote", "set-url", "origin", url],
                    cwd=str(self.path),
                capture_output=True,
                text=True,
                timeout=10
            )
        else:
            # Создаем новый remote
            result = subprocess.run(
                    [self.git_cmd, "remote", "add", "origin", url],
                    cwd=str(self.path),
                capture_output=True,
                text=True,
                timeout=10
            )
        
        if result.returncode == 0:
                return True, "Remote обновлен"
            return False, result.stderr or "Неизвестная ошибка"
    except Exception as e:
        return False, str(e)

    def get_status(self) -> Dict[str, Any]:
        """Получение статуса репозитория"""
        if not self.is_repo():
        return {
            "is_repo": False,
            "error": "Not a Git repository"
        }
    
        if not self.git_cmd:
        return {
            "is_repo": False,
                "error": "Git не установлен",
            "git_not_installed": True
        }
    
    try:
            # Проверяем локальные изменения
            result = subprocess.run(
                [self.git_cmd, "status", "--porcelain"],
                cwd=str(self.path),
                capture_output=True,
                text=True,
                timeout=10
            )
            has_changes = bool(result.stdout.strip())
        
        # Получаем текущую ветку
            result = subprocess.run(
                [self.git_cmd, "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(self.path),
                capture_output=True,
                text=True,
                timeout=10
            )
            current_branch = result.stdout.strip() if result.returncode == 0 else None
        
        # Получаем последний коммит
        last_commit = None
            result = subprocess.run(
                [self.git_cmd, "log", "-1", "--format=%H|%s|%ar", "--no-decorate"],
                cwd=str(self.path),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    parts = result.stdout.strip().split("|", 2)
                    if len(parts) == 3:
                        last_commit = {
                            "hash": parts[0][:7],
                            "message": parts[1],
                            "date": parts[2]
                        }
        
            # Проверяем наличие обновлений
        has_updates = False
            remote_url = self.get_remote_url()
            if remote_url:
                try:
                    # Быстрая проверка без fetch
                    result = subprocess.run(
                        [self.git_cmd, "rev-list", "--count", f"HEAD..origin/{current_branch or self.branch}"],
                        cwd=str(self.path),
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        has_updates = result.returncode == 0 and int(result.stdout.strip() or "0") > 0
                except Exception:
            pass
        
        return {
            "is_repo": True,
            "has_changes": has_changes,
            "current_branch": current_branch,
            "last_commit": last_commit,
            "has_updates": has_updates,
            "remote": remote_url
        }
    except Exception as e:
            return {
                "is_repo": False,
                "error": str(e)
            }


# Функции для обратной совместимости
def get_git_command() -> str:
    """Получение команды git"""
    repo = GitRepository(Path.cwd())
    return repo.git_cmd or "git"


def is_git_repo(path: Path) -> bool:
    """Проверка, является ли директория Git репозиторием"""
    repo = GitRepository(path)
    return repo.is_repo()


def get_git_remote(path: Path) -> Optional[str]:
    """Получение URL удаленного репозитория"""
    repo = GitRepository(path)
    return repo.get_remote_url()


def set_git_remote(path: Path, url: str) -> Tuple[bool, str]:
    """Установка удаленного репозитория"""
    repo = GitRepository(path)
    return repo._set_remote(url)


def check_git_installed() -> bool:
    """Проверка установки Git"""
    repo = GitRepository(Path.cwd())
    return repo.is_git_installed()


def get_git_status(path: Path) -> Dict[str, Any]:
    """Получение статуса Git репозитория"""
    repo = GitRepository(path)
    return repo.get_status()


def init_git_repo(path: Path, repo_url: Optional[str] = None) -> Tuple[bool, str]:
    """Инициализация Git репозитория"""
    repo = GitRepository(path, repo_url)
    
    if repo.is_repo():
        return True, "Already a Git repository"
    
    if not repo.git_cmd:
        return False, "Git не установлен. Установите Git для работы с репозиториями."
    
    try:
        # Инициализируем репозиторий
        result = subprocess.run(
            [repo.git_cmd, "init"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return False, f"Failed to initialize: {result.stderr}"
        
        # Настраиваем git config
        subprocess.run(
            [repo.git_cmd, "config", "user.name", "Panel User"],
            cwd=str(path),
            capture_output=True,
            timeout=5
        )
            subprocess.run(
            [repo.git_cmd, "config", "user.email", "panel@localhost"],
            cwd=str(path),
            capture_output=True,
            timeout=5
        )
        
        # Если указан URL, добавляем remote
        if repo_url:
            success, msg = repo._set_remote(repo_url)
            if not success:
                return False, f"Failed to set remote: {msg}"
        
        return True, "Git repository initialized successfully"
    except Exception as e:
        return False, str(e)


def update_panel_from_git() -> Tuple[bool, str]:
    """Обновление панели из GitHub репозитория"""
    from backend.config import PANEL_REPO_URL, PANEL_REPO_BRANCH
    
    repo = GitRepository(BASE_DIR, PANEL_REPO_URL, PANEL_REPO_BRANCH)
    return repo.update(PANEL_REPO_URL, PANEL_REPO_BRANCH)


def update_bot_from_git(bot_dir: Path, repo_url: Optional[str] = None, branch: str = "main") -> Tuple[bool, str]:
    """
    Обновление файлов бота из GitHub репозитория
    
    Это основная функция для работы с репозиториями ботов.
    Автоматически определяет, нужно ли клонировать или обновлять репозиторий.
    """
    repo = GitRepository(bot_dir, repo_url, branch)
    
    if not repo.is_git_installed():
        return False, "Git не установлен. Установите Git для работы с репозиториями."
    
    # Если репозиторий не существует, клонируем
    if not repo.is_repo():
            if not repo_url:
            return False, "URL репозитория не указан для клонирования"
        return repo.clone(repo_url, branch)
    
    # Если репозиторий существует, обновляем
    return repo.update(repo_url, branch)
