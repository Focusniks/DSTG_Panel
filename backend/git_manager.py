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
    
    def is_git_installed(self) -> bool:
        """Проверка установки Git"""
        return self.git_cmd is not None
    
    def is_repo(self) -> bool:
        """Проверка, является ли директория Git репозиторием"""
        return is_git_repo(self.path)
    
    def clone(self, repo_url: str, branch: str = "main") -> Tuple[bool, str]:
        """Клонирование репозитория"""
        if not self.git_cmd:
            return (False, "Git command not found")
        
        try:
            # Преобразуем HTTPS в SSH если нужно
            ssh_url = convert_https_to_ssh(repo_url)
            env = get_git_env_with_ssh()
            
            # Удаляем директорию если она существует и не пуста
            if self.path.exists():
                for item in self.path.iterdir():
                    if item.name not in ['config.json', '.gitkeep']:
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
            
            # Клонируем репозиторий
            cmd = [self.git_cmd, "clone", "-b", branch, "--depth", "1", ssh_url, str(self.path)]
            result = subprocess.run(
                cmd,
                cwd=self.path.parent,
                env=env,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                # Если клонирование прошло в поддиректорию, перемещаем файлы
                cloned_dir = self.path.parent / Path(ssh_url).stem.replace('.git', '')
                if cloned_dir.exists() and cloned_dir != self.path:
                    for item in cloned_dir.iterdir():
                        shutil.move(str(item), str(self.path / item.name))
                    cloned_dir.rmdir()
                
                return (True, "Repository cloned successfully")
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                return (False, f"Git clone failed: {error_msg}")
        except subprocess.TimeoutExpired:
            return (False, "Git clone timeout")
        except Exception as e:
            logger.error(f"Error cloning repository: {e}", exc_info=True)
            return (False, f"Error: {str(e)}")
    
    def update(self) -> Tuple[bool, str]:
        """Обновление репозитория из удаленного источника"""
        if not self.git_cmd:
            return (False, "Git command not found")
        
        if not is_git_repo(self.path):
            return (False, "Not a git repository")
        
        try:
            env = get_git_env_with_ssh()
            
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
                return (True, "Repository updated successfully")
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                return (False, f"Git pull failed: {error_msg}")
        except subprocess.TimeoutExpired:
            return (False, "Git pull timeout")
        except Exception as e:
            logger.error(f"Error updating repository: {e}", exc_info=True)
            return (False, f"Error: {str(e)}")
    
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
            
            return {
                "is_repo": True,
                "branch": branch,
                "commit": commit,
                "remote": remote,
                "has_changes": has_changes,
                "status": "modified" if has_changes else "clean"
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
        env = get_git_env_with_ssh()
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
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
        git_cmd = shutil.which("git") or "git"
        
        # Инициализируем репозиторий
        result = subprocess.run(
            [git_cmd, "init"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return (False, f"Git init failed: {result.stderr}")
        
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
                    return (False, f"Failed to set remote URL: {result.stderr}")
        
        return (True, "Git repository initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing git repo: {e}", exc_info=True)
        return (False, f"Error: {str(e)}")


def set_git_remote(path: Path, repo_url: str) -> bool:
    """Установка URL удаленного репозитория"""
    if not is_git_repo(path):
        return False
    
    try:
        git_cmd = shutil.which("git") or "git"
        ssh_url = convert_https_to_ssh(repo_url)
        env = get_git_env_with_ssh()
        
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
