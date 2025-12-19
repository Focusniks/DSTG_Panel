"""
Управление Git репозиториями для обновления панели и ботов
"""
import subprocess
import os
from pathlib import Path
from typing import Optional, Dict, Tuple, Any
from backend.config import BASE_DIR
from backend.ssh_manager import convert_https_to_ssh, get_git_env_with_ssh

def is_git_repo(path: Path) -> bool:
    """Проверка, является ли директория Git репозиторием"""
    git_dir = path / ".git"
    return git_dir.exists() and git_dir.is_dir()

def get_git_remote(path: Path) -> Optional[str]:
    """Получение URL удаленного репозитория"""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None

def set_git_remote(path: Path, url: str) -> Tuple[bool, str]:
    """Установка удаленного репозитория"""
    try:
        # Проверяем существование remote
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(path),
            capture_output=True,
            timeout=5
        )
        
        if result.returncode == 0:
            # Обновляем существующий remote
            result = subprocess.run(
                ["git", "remote", "set-url", "origin", url],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=10
            )
        else:
            # Создаем новый remote
            result = subprocess.run(
                ["git", "remote", "add", "origin", url],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=10
            )
        
        if result.returncode == 0:
            return True, "Remote updated"
        return False, result.stderr or "Unknown error"
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except FileNotFoundError:
        return False, "Git not installed"
    except Exception as e:
        return False, str(e)

def get_git_status(path: Path) -> Dict[str, Any]:
    """Получение статуса Git репозитория"""
    # Сначала проверяем, является ли путь Git репозиторием
    if not is_git_repo(path):
        return {
            "is_repo": False,
            "error": "Not a Git repository"
        }
    
    try:
        # Проверяем, есть ли изменения
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=10
        )
        has_changes = bool(result.stdout.strip())
        
        # Получаем текущую ветку
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=10
        )
        current_branch = result.stdout.strip() if result.returncode == 0 else None
        
        # Получаем последний коммит
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H|%s|%ar", "--no-decorate"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=10
        )
        last_commit = None
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("|", 2)
            if len(parts) == 3:
                last_commit = {
                    "hash": parts[0][:7],
                    "message": parts[1],
                    "date": parts[2]
                }
        
        # Проверяем, есть ли обновления
        has_updates = False
        if get_git_remote(path):
            result = subprocess.run(
                ["git", "fetch", "origin"],
                cwd=str(path),
                capture_output=True,
                timeout=30
            )
            if result.returncode == 0:
                result = subprocess.run(
                    ["git", "rev-list", "--count", "HEAD..origin/" + (current_branch or "main")],
                    cwd=str(path),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                has_updates = result.returncode == 0 and int(result.stdout.strip() or "0") > 0
        
        return {
            "is_repo": True,
            "has_changes": has_changes,
            "current_branch": current_branch,
            "last_commit": last_commit,
            "has_updates": has_updates,
            "remote": get_git_remote(path)
        }
    except Exception as e:
        return {
            "is_repo": False,
            "error": str(e)
        }

def init_git_repo(path: Path, repo_url: Optional[str] = None) -> Tuple[bool, str]:
    """Инициализация Git репозитория"""
    try:
        if is_git_repo(path):
            return True, "Already a Git repository"
        
        # Инициализируем репозиторий
        result = subprocess.run(
            ["git", "init"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return False, f"Failed to initialize Git repository: {result.stderr}"
        
        # Если указан URL, добавляем remote
        if repo_url:
            success, msg = set_git_remote(path, repo_url)
            if not success:
                return False, f"Failed to set remote: {msg}"
        
        return True, "Git repository initialized successfully"
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except FileNotFoundError:
        return False, "Git not installed"
    except Exception as e:
        return False, str(e)

def update_panel_from_git() -> Tuple[bool, str]:
    """Обновление панели из GitHub репозитория"""
    try:
        if not is_git_repo(BASE_DIR):
            return False, "Not a Git repository"
        
        # Используем SSH окружение для приватных репозиториев
        env = get_git_env_with_ssh()
        
        # Сохраняем изменения перед обновлением
        result = subprocess.run(
            ["git", "stash"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        # Получаем обновления
        result = subprocess.run(
            ["git", "fetch", "origin"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=60,
            env=env
        )
        if result.returncode != 0:
            return False, f"Fetch failed: {result.stderr}"
        
        # Определяем текущую ветку
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )
        branch = result.stdout.strip() if result.returncode == 0 else "main"
        
        # Обновляем код
        result = subprocess.run(
            ["git", "pull", "origin", branch],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=120,
            env=env
        )
        
        if result.returncode == 0:
            return True, "Panel updated successfully"
        return False, result.stderr or "Pull failed"
        
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except FileNotFoundError:
        return False, "Git not installed"
    except Exception as e:
        return False, str(e)

def update_bot_from_git(bot_dir: Path, repo_url: Optional[str] = None, branch: str = "main") -> Tuple[bool, str]:
    """Обновление файлов бота из GitHub репозитория"""
    try:
        # Если репозиторий не инициализирован
        if not is_git_repo(bot_dir):
            if not repo_url:
                return False, "Repository URL required for initialization"
            
            # Клонируем репозиторий
            if bot_dir.exists():
                # Проверяем, не пуста ли директория (игнорируем .gitkeep и .git)
                files = [f for f in bot_dir.iterdir() if f.name not in ['.gitkeep', '.git']]
                if files:
                    return False, "Directory is not empty and not a Git repository"
            
            # Преобразуем HTTPS URL в SSH для приватных репозиториев (если нужно)
            clone_url = repo_url
            if repo_url.startswith('https://') and 'github.com' in repo_url:
                # Пользователь может использовать SSH URL напрямую
                # Если используется HTTPS, можно автоматически конвертировать
                # Но пока оставим как есть, чтобы пользователь сам выбирал
                pass
            
            # Используем SSH окружение для Git команд
            env = get_git_env_with_ssh()
            
            result = subprocess.run(
                ["git", "clone", "-b", branch, clone_url, str(bot_dir)],
                capture_output=True,
                text=True,
                timeout=300,
                env=env
            )
            
            if result.returncode == 0:
                return True, "Repository cloned successfully"
            return False, result.stderr or "Clone failed"
        
        # Если репозиторий уже существует, обновляем его
        # Используем SSH окружение для всех Git операций
        env = get_git_env_with_ssh()
        
        # Сохраняем изменения
        result = subprocess.run(
            ["git", "stash"],
            cwd=str(bot_dir),
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        # Обновляем remote если нужно
        if repo_url:
            remote_url = get_git_remote(bot_dir)
            if remote_url != repo_url:
                success, msg = set_git_remote(bot_dir, repo_url)
                if not success:
                    return False, f"Failed to update remote: {msg}"
        
        # Получаем обновления (используем SSH окружение для приватных репозиториев)
        result = subprocess.run(
            ["git", "fetch", "origin"],
            cwd=str(bot_dir),
            capture_output=True,
            text=True,
            timeout=60,
            env=env
        )
        if result.returncode != 0:
            return False, f"Fetch failed: {result.stderr}"
        
        # Обновляем код (используем SSH окружение для приватных репозиториев)
        result = subprocess.run(
            ["git", "pull", "origin", branch],
            cwd=str(bot_dir),
            capture_output=True,
            text=True,
            timeout=120,
            env=env
        )
        
        if result.returncode == 0:
            return True, "Bot updated successfully"
        return False, result.stderr or "Pull failed"
        
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except FileNotFoundError:
        return False, "Git not installed"
    except Exception as e:
        return False, str(e)

