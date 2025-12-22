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
        """Клонирование репозитория"""
        if not self.git_cmd:
            return (False, "Команда Git не найдена")
        
        try:
            # Используем временную директорию для клонирования
            temp_dir = Path(tempfile.mkdtemp(prefix="git_clone_"))
            
            # Конвертируем HTTPS в SSH если нужно
            ssh_url = convert_https_to_ssh(repo_url)
            env = get_git_env_with_ssh()
            
            # Клонируем во временную директорию
            result = subprocess.run(
                [self.git_cmd, "clone", "-b", branch, "--single-branch", ssh_url, str(temp_dir)],
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode != 0:
                shutil.rmtree(temp_dir, ignore_errors=True)
                error_msg = result.stderr or result.stdout or "Unknown error"
                return (False, f"Ошибка клонирования: {error_msg}")
            
            # Перемещаем содержимое в целевую директорию
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
                
                return (True, "Repository cloned successfully")
            except Exception as move_error:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return (False, f"Ошибка при перемещении файлов: {str(move_error)}")
        except subprocess.TimeoutExpired:
            return (False, "Clone timeout")
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
            
            # Получаем последний коммит
            commit_result = subprocess.run(
                [self.git_cmd, "rev-parse", "--short", "HEAD"],
                cwd=self.path,
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )
            last_commit = commit_result.stdout.strip() if commit_result.returncode == 0 else None
            
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
            
            return {
                "is_repo": True,
                "branch": current_branch or self.branch,
                "current_branch": current_branch or self.branch,
                "commit": last_commit,
                "remote": remote_url,
                "has_changes": has_changes,
                "status": "clean" if not has_changes else "dirty"
            }
        except Exception as e:
            logger.error(f"Error getting git status: {e}", exc_info=True)
            return {
                "is_repo": True,
                "branch": self.branch,
                "commit": None,
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
    """Обновление панели из Git репозитория с сохранением папок bots/ и data/"""
    from backend.config import PANEL_REPO_URL, PANEL_REPO_BRANCH, BOTS_DIR, DATA_DIR
    
    # Находим Git команду
    git_cmd = None
    candidates = [shutil.which("git"), "git"]
    if os.name != 'nt':
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
                timeout=3
            )
            if result.returncode == 0:
                git_cmd = candidate
                break
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            continue
    
    if not git_cmd:
        return (False, "Git не установлен. Установите Git для обновления панели.")
    
    if not is_git_repo(BASE_DIR):
        return (False, "Панель не является Git репозиторием. Инициализируйте репозиторий в настройках.")
    
    # Убеждаемся, что используем HTTPS URL для панели
    https_url = PANEL_REPO_URL
    if not https_url.endswith(".git"):
        https_url += ".git"
    
    logger.info(f"Используем HTTPS URL для панели: {https_url}")
    
    # Принудительно устанавливаем HTTPS URL
    try:
        set_url_result = subprocess.run(
            [git_cmd, "remote", "set-url", "origin", https_url],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=10
        )
        if set_url_result.returncode == 0:
            logger.info("Remote URL установлен на HTTPS")
        else:
            # Пробуем добавить remote если его нет
            add_result = subprocess.run(
                [git_cmd, "remote", "add", "origin", https_url],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=10
            )
            if add_result.returncode != 0:
                logger.warning(f"Не удалось установить remote URL: {add_result.stderr}")
    except Exception as e:
        logger.warning(f"Ошибка при установке remote URL: {e}")
    
    # Создаем временную директорию для бэкапа защищаемых папок
    try:
        backup_dir = Path(tempfile.mkdtemp(prefix="panel_update_backup_"))
        logger.info(f"Создана временная директория для бэкапа: {backup_dir}")
    except Exception as e:
        logger.error(f"Не удалось создать временную директорию: {e}", exc_info=True)
        return (False, f"Не удалось создать временную директорию для бэкапа: {str(e)}")
    
    protected_dirs = []
    if BOTS_DIR.exists() and BOTS_DIR.is_dir():
        protected_dirs.append(("bots", BOTS_DIR))
    if DATA_DIR.exists() and DATA_DIR.is_dir():
        protected_dirs.append(("data", DATA_DIR))
    
    # Сохраняем защищаемые директории
    for dir_name, dir_path in protected_dirs:
        try:
            backup_path = backup_dir / dir_name
            if dir_path.exists() and dir_path.is_dir():
                logger.info(f"Сохранение директории {dir_name}...")
                if backup_path.exists():
                    shutil.rmtree(backup_path)
                shutil.copytree(dir_path, backup_path, dirs_exist_ok=True)
                logger.info(f"Директория {dir_name} сохранена")
        except Exception as backup_error:
            logger.error(f"Ошибка при сохранении директории {dir_name}: {backup_error}", exc_info=True)
    
    # Выполняем git pull через HTTPS (без SSH)
    try:
        env = os.environ.copy()
        # Убираем SSH команду если есть
        if 'GIT_SSH_COMMAND' in env:
            del env['GIT_SSH_COMMAND']
        
        logger.info(f"Выполняем git pull через HTTPS (ветка: {PANEL_REPO_BRANCH})")
        pull_result = subprocess.run(
            [git_cmd, "pull", "origin", PANEL_REPO_BRANCH],
            cwd=BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if pull_result.returncode == 0:
            logger.info("Git pull успешно выполнен")
            
            # Восстанавливаем защищаемые директории
            logger.info("Восстановление защищаемых директорий...")
            for dir_name, dir_path in protected_dirs:
                try:
                    backup_path = backup_dir / dir_name
                    if backup_path.exists() and backup_path.is_dir():
                        if dir_path.exists():
                            logger.info(f"Восстановление директории {dir_name}...")
                            try:
                                shutil.rmtree(dir_path)
                            except Exception as rmtree_error:
                                logger.warning(f"Не удалось удалить {dir_path}, пробуем принудительно")
                                def handle_remove_readonly(func, path, exc):
                                    os.chmod(path, stat.S_IWRITE)
                                    func(path)
                                shutil.rmtree(dir_path, onerror=handle_remove_readonly)
                        
                        shutil.copytree(backup_path, dir_path, dirs_exist_ok=True)
                        logger.info(f"Директория {dir_name} восстановлена")
                except Exception as restore_error:
                    logger.error(f"Ошибка при восстановлении директории {dir_name}: {restore_error}", exc_info=True)
            
            # Удаляем временную директорию
            try:
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
            except Exception:
                pass
            
            return (True, "Панель успешно обновлена. Защищенные директории (bots/, data/) сохранены.")
        else:
            error_msg = pull_result.stderr or pull_result.stdout or "Неизвестная ошибка"
            logger.error(f"Git pull failed: {error_msg}")
            
            # Восстанавливаем директории даже при ошибке
            for dir_name, dir_path in protected_dirs:
                try:
                    backup_path = backup_dir / dir_name
                    if backup_path.exists() and backup_path.is_dir() and not dir_path.exists():
                        shutil.copytree(backup_path, dir_path)
                except Exception:
                    pass
            
            # Удаляем временную директорию
            try:
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
            except Exception:
                pass
            
            return (False, f"Ошибка Git pull: {error_msg}")
            
    except subprocess.TimeoutExpired:
        logger.error("Git pull timeout")
        return (False, "Git pull timeout")
    except Exception as e:
        logger.error(f"Критическая ошибка при обновлении панели: {e}", exc_info=True)
        
        # Восстанавливаем директории при ошибке
        try:
            if backup_dir and backup_dir.exists():
                for dir_name, dir_path in protected_dirs:
                    try:
                        backup_path = backup_dir / dir_name
                        if backup_path.exists() and backup_path.is_dir() and not dir_path.exists():
                            shutil.copytree(backup_path, dir_path)
                    except Exception:
                        pass
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
        except Exception:
            pass
        
        return (False, f"Ошибка обновления панели: {str(e)}")


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
