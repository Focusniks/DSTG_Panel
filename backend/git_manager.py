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


def parse_gitignore(gitignore_path: Path) -> List[str]:
    """
    Парсинг .gitignore файла и возврат списка паттернов
    
    Args:
        gitignore_path: Путь к файлу .gitignore
        
    Returns:
        Список паттернов для игнорирования
    """
    if not gitignore_path.exists():
        return []
    
    patterns = []
    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Пропускаем пустые строки и комментарии
                if not line or line.startswith('#'):
                    continue
                # Убираем пробелы в начале и конце
                line = line.strip()
                if line:
                    patterns.append(line)
    except Exception as e:
        logger.warning(f"Ошибка при чтении .gitignore: {e}")
    
    return patterns


def matches_gitignore_pattern(file_path: Path, patterns: List[str], base_path: Path) -> bool:
    """
    Проверяет, соответствует ли файл паттернам из .gitignore
    
    Args:
        file_path: Путь к файлу для проверки
        patterns: Список паттернов из .gitignore
        base_path: Базовый путь репозитория
        
    Returns:
        True если файл должен быть проигнорирован
    """
    if not patterns:
        return False
    
    # Получаем относительный путь от базового пути
    try:
        rel_path = file_path.relative_to(base_path)
        rel_path_str = str(rel_path).replace('\\', '/')
    except ValueError:
        # Если файл не находится в базовом пути, не игнорируем
        return False
    
    for pattern in patterns:
        # Обрабатываем паттерны .gitignore
        # Упрощенная версия - поддерживаем основные случаи
        
        # Паттерн с / в начале - относительно корня репозитория
        if pattern.startswith('/'):
            pattern = pattern[1:]
            if fnmatch.fnmatch(rel_path_str, pattern) or fnmatch.fnmatch(rel_path_str, pattern + '/*'):
                return True
        
        # Паттерн с / в конце - директория
        elif pattern.endswith('/'):
            pattern = pattern[:-1]
            if rel_path_str.startswith(pattern + '/') or rel_path_str == pattern:
                return True
        
        # Паттерн с ** - рекурсивный поиск
        elif '**' in pattern:
            # Заменяем ** на * для fnmatch
            pattern_fnmatch = pattern.replace('**', '*')
            if fnmatch.fnmatch(rel_path_str, pattern_fnmatch):
                return True
            # Также проверяем вложенные пути
            path_parts = rel_path_str.split('/')
            for i in range(len(path_parts)):
                sub_path = '/'.join(path_parts[i:])
                if fnmatch.fnmatch(sub_path, pattern_fnmatch):
                    return True
        
        # Обычный паттерн
        else:
            # Проверяем точное совпадение или совпадение в любой части пути
            if fnmatch.fnmatch(rel_path_str, pattern):
                return True
            # Проверяем совпадение с именем файла
            if fnmatch.fnmatch(rel_path_str.split('/')[-1], pattern):
                return True
            # Проверяем совпадение в любой части пути
            path_parts = rel_path_str.split('/')
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
    
    return False


def get_ignored_files(base_path: Path, gitignore_patterns: List[str]) -> Set[Path]:
    """
    Получает список файлов, которые должны быть проигнорированы согласно .gitignore
    
    Args:
        base_path: Базовый путь репозитория
        gitignore_patterns: Список паттернов из .gitignore
        
    Returns:
        Множество путей к игнорируемым файлам
    """
    ignored = set()
    
    if not gitignore_patterns:
        return ignored
    
    # Рекурсивно обходим все файлы
    for root, dirs, files in os.walk(base_path):
        root_path = Path(root)
        
        # Проверяем директории
        dirs_to_remove = []
        for dir_name in dirs:
            dir_path = root_path / dir_name
            if matches_gitignore_pattern(dir_path, gitignore_patterns, base_path):
                ignored.add(dir_path)
                dirs_to_remove.append(dir_name)  # Не обходим игнорируемые директории
        
        # Удаляем игнорируемые директории из списка для обхода
        for dir_name in dirs_to_remove:
            dirs.remove(dir_name)
        
        # Проверяем файлы
        for file_name in files:
            file_path = root_path / file_name
            if matches_gitignore_pattern(file_path, gitignore_patterns, base_path):
                ignored.add(file_path)
    
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
    
    def clone(self, repo_url: str, branch: str = "main") -> Tuple[bool, str]:
        """Клонирование репозитория"""
        if not self.git_cmd:
            return (False, "Команда Git не найдена")
        
        try:
            # Преобразуем HTTPS в SSH если нужно
            ssh_url = convert_https_to_ssh(repo_url)
            env = get_git_env_with_ssh()
            
            # Убеждаемся, что директория существует
            self.path.mkdir(parents=True, exist_ok=True)
            
            # Удаляем все содержимое директории кроме config.json и .gitkeep
            # ВАЖНО: также удаляем .git если он существует
            if self.path.exists():
                for item in self.path.iterdir():
                    if item.name not in ['config.json', '.gitkeep']:
                        try:
                            if item.is_dir():
                                shutil.rmtree(item)
                            else:
                                item.unlink()
                        except Exception as e:
                            logger.warning(f"Не удалось удалить {item} перед клонированием: {e}")
            
            # Проверяем, что директория пуста (кроме config.json и .gitkeep)
            remaining_items = [item.name for item in self.path.iterdir() 
                              if item.name not in ['config.json', '.gitkeep']]
            if remaining_items:
                logger.warning(f"В директории остались элементы после очистки: {remaining_items}")
                # Пытаемся удалить оставшиеся элементы еще раз
                for item_name in remaining_items:
                    item_path = self.path / item_name
                    try:
                        if item_path.is_dir():
                            shutil.rmtree(item_path)
                        else:
                            item_path.unlink()
                    except Exception as e:
                        logger.error(f"Не удалось удалить {item_path}: {e}")
                        return (False, f"Не удалось очистить директорию перед клонированием. Остался элемент: {item_name}")
            
            # Клонируем репозиторий
            # Используем временное имя для клонирования, затем перемещаем содержимое
            import tempfile
            import uuid
            temp_clone_dir = self.path.parent / f".temp_clone_{uuid.uuid4().hex[:8]}"
            
            try:
                cmd = [self.git_cmd, "clone", "-b", branch, "--depth", "1", ssh_url, str(temp_clone_dir)]
                result = subprocess.run(
                    cmd,
                    cwd=self.path.parent,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr or result.stdout or "Неизвестная ошибка"
                    return (False, f"Ошибка клонирования Git: {error_msg}")
                
                # Перемещаем содержимое из временной директории в целевую
                if temp_clone_dir.exists():
                    for item in temp_clone_dir.iterdir():
                        if item.name not in ['config.json', '.gitkeep']:
                            try:
                                dest = self.path / item.name
                                if dest.exists():
                                    if dest.is_dir():
                                        shutil.rmtree(dest)
                                    else:
                                        dest.unlink()
                                shutil.move(str(item), str(dest))
                            except Exception as e:
                                logger.error(f"Ошибка при перемещении {item}: {e}")
                                # Пытаемся удалить временную директорию
                                try:
                                    shutil.rmtree(temp_clone_dir)
                                except:
                                    pass
                                return (False, f"Ошибка при перемещении файлов из временной директории: {str(e)}")
                    
                    # Удаляем временную директорию
                    try:
                        shutil.rmtree(temp_clone_dir)
                    except Exception as e:
                        logger.warning(f"Не удалось удалить временную директорию {temp_clone_dir}: {e}")
                
                return (True, "Repository cloned successfully")
            except Exception as clone_error:
                # Удаляем временную директорию при ошибке
                if temp_clone_dir.exists():
                    try:
                        shutil.rmtree(temp_clone_dir)
                    except:
                        pass
                raise clone_error
        except subprocess.TimeoutExpired:
            return (False, "Git clone timeout")
        except Exception as e:
            logger.error(f"Error cloning repository: {e}", exc_info=True)
            return (False, f"Ошибка: {str(e)}")
    
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
                "remote": None,
                "status": "not_a_repo"
            }
        
        try:
            env = get_git_env_with_ssh()
            
            # Текущая ветка
            branch_result = subprocess.run(
                [self.git_cmd, "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.path,
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )
            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
            
            # Если ветка не определена, пробуем другой способ
            if not branch or branch == "":
                # Пробуем получить ветку через symbolic-ref
                branch_result2 = subprocess.run(
                    [self.git_cmd, "symbolic-ref", "--short", "HEAD"],
                    cwd=self.path,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                branch = branch_result2.stdout.strip() if branch_result2.returncode == 0 else None
            
            # Если все еще не определена, используем self.branch
            if not branch or branch == "":
                branch = self.branch
            
            # Последний коммит
            commit_result = subprocess.run(
                [self.git_cmd, "rev-parse", "HEAD"],
                cwd=self.path,
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )
            commit = commit_result.stdout.strip()[:7] if commit_result.returncode == 0 else None
            
            # Удаленный репозиторий
            remote_result = subprocess.run(
                [self.git_cmd, "remote", "get-url", "origin"],
                cwd=self.path,
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )
            remote = remote_result.stdout.strip() if remote_result.returncode == 0 else None
            
            # Статус изменений
            status_result = subprocess.run(
                [self.git_cmd, "status", "--porcelain"],
                cwd=self.path,
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )
            has_changes = bool(status_result.stdout.strip())
            
            # Информация о последнем коммите
            last_commit_message = None
            last_commit_date = None
            last_commit_hash = None
            if commit:
                try:
                    # Получаем сообщение последнего коммита
                    log_result = subprocess.run(
                        [self.git_cmd, "log", "-1", "--pretty=format:%s", "HEAD"],
                        cwd=self.path,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if log_result.returncode == 0:
                        last_commit_message = log_result.stdout.strip()
                    
                    # Получаем дату последнего коммита
                    date_result = subprocess.run(
                        [self.git_cmd, "log", "-1", "--pretty=format:%cd", "--date=format:%Y-%m-%d %H:%M:%S", "HEAD"],
                        cwd=self.path,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if date_result.returncode == 0:
                        last_commit_date = date_result.stdout.strip()
                    
                    # Получаем полный хеш коммита
                    hash_result = subprocess.run(
                        [self.git_cmd, "rev-parse", "HEAD"],
                        cwd=self.path,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if hash_result.returncode == 0:
                        last_commit_hash = hash_result.stdout.strip()[:7]
                except Exception as e:
                    logger.warning(f"Error getting commit info: {e}")
            
            # Проверка наличия обновлений (fetch и сравнение с удаленной веткой)
            has_updates = False
            if remote and branch:
                try:
                    # Выполняем fetch для получения информации об удаленных изменениях
                    fetch_result = subprocess.run(
                        [self.git_cmd, "fetch", "origin", branch],
                        cwd=self.path,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    # Сравниваем локальный и удаленный коммиты
                    if fetch_result.returncode == 0:
                        # Получаем хеш локального коммита
                        local_commit_result = subprocess.run(
                            [self.git_cmd, "rev-parse", "HEAD"],
                            cwd=self.path,
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        local_commit = local_commit_result.stdout.strip() if local_commit_result.returncode == 0 else None
                        
                        # Получаем хеш удаленного коммита
                        remote_commit_result = subprocess.run(
                            [self.git_cmd, "rev-parse", f"origin/{branch}"],
                            cwd=self.path,
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        remote_commit = remote_commit_result.stdout.strip() if remote_commit_result.returncode == 0 else None
                        
                        # Если коммиты разные, есть обновления
                        if local_commit and remote_commit and local_commit != remote_commit:
                            has_updates = True
                except Exception as e:
                    logger.warning(f"Error checking for updates: {e}")
            
            return {
                "is_repo": True,
                "branch": branch,
                "current_branch": branch,
                "commit": commit,
                "remote": remote,
                "has_changes": has_changes,
                "has_updates": has_updates,
                "status": "modified" if has_changes else "clean",
                "last_commit": {
                    "hash": last_commit_hash or commit,
                    "message": last_commit_message,
                    "date": last_commit_date
                } if last_commit_message or last_commit_date else None
            }
        except Exception as e:
            logger.error(f"Error getting git status: {e}", exc_info=True)
            return {
                "is_repo": True,
                "branch": None,
                "commit": None,
                "remote": None,
                "status": "error",
                "error": str(e)
            }


# Вспомогательные функции для обратной совместимости

def is_git_repo(path: Path) -> bool:
    """Проверка, является ли директория Git репозиторием"""
    git_dir = Path(path) / ".git"
    return git_dir.exists() and git_dir.is_dir()


def update_bot_from_git(bot_dir: Path, repo_url: str, branch: str = "main") -> Tuple[bool, str]:
    """Обновление бота из Git репозитория"""
    repo = GitRepository(bot_dir, repo_url, branch)
    
    if not is_git_repo(bot_dir):
        return repo.clone(repo_url, branch)
    else:
        return repo.update()


def update_panel_from_git() -> Tuple[bool, str]:
    """Обновление панели из Git репозитория"""
    from backend.config import PANEL_REPO_URL, PANEL_REPO_BRANCH
    repo = GitRepository(BASE_DIR, PANEL_REPO_URL, PANEL_REPO_BRANCH)
    return repo.update()


def get_git_status(path: Path) -> Dict[str, Any]:
    """Получение статуса Git репозитория"""
    repo = GitRepository(path)
    return repo.get_status()


def get_git_remote(path: Path) -> Optional[str]:
    """Получение URL удаленного репозитория"""
    if not is_git_repo(path):
        return None
    
    try:
        # Проверяем наличие Git
        git_cmd = shutil.which("git")
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
        # Проверяем наличие Git
        git_cmd = shutil.which("git")
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
            ssh_url = convert_https_to_ssh(repo_url)
            env = get_git_env_with_ssh()
            
            result = subprocess.run(
                [git_cmd, "remote", "add", "origin", ssh_url],
                cwd=path,
                env=env,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                # Если remote уже существует, обновляем его
                result = subprocess.run(
                    [git_cmd, "remote", "set-url", "origin", ssh_url],
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
        # Проверяем наличие Git
        git_cmd = shutil.which("git")
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
