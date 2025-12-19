"""
Управление Git репозиториями для обновления панели и бото
"""
import subprocess
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Tuple, Any
from backend.config import BASE_DIR
from backend.ssh_manager import convert_https_to_ssh, get_git_env_with_ssh

def get_git_command() -> str:
    """Получение команды git с учетом платформы"""
    # Сначала пробуем найти через which
    git_cmd = shutil.which("git")
    if git_cmd:
        return git_cmd
    
    # Если не найдено, пробуем стандартные пути для Unix
    if os.name != 'nt':
        standard_paths = [
            "/usr/bin/git",
            "/usr/local/bin/git",
            "/bin/git"
        ]
        for path in standard_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
    
    # В крайнем случае просто "git" - пусть система сама найдет
    return "git"

def run_git_command(path: Path, *args, **kwargs) -> subprocess.CompletedProcess:
    """Выполнение Git команды с автоматическим определением пути к git"""
    git_cmd = get_git_command()
    cmd = [git_cmd] + list(args)
    cwd = kwargs.pop('cwd', str(path))
    return subprocess.run(cmd, cwd=cwd, **kwargs)

def is_git_repo(path: Path) -> bool:
    """Проверка, является ли директория Git репозиторием"""
    git_dir = path / ".git"
    return git_dir.exists() and git_dir.is_dir()

def get_git_remote(path: Path) -> Optional[str]:
    """Получение URL удаленного репозитория"""
    try:
        git_cmd = get_git_command()
        result = subprocess.run(
            [git_cmd, "remote", "get-url", "origin"],
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
        git_cmd = get_git_command()
        # Проверяем существование remote
        result = subprocess.run(
            [git_cmd, "remote", "get-url", "origin"],
            cwd=str(path),
            capture_output=True,
            timeout=5
        )
        
        if result.returncode == 0:
            # Обновляем существующий remote
            result = subprocess.run(
                [git_cmd, "remote", "set-url", "origin", url],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=10
            )
        else:
            # Создаем новый remote
            result = subprocess.run(
                [git_cmd, "remote", "add", "origin", url],
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

def check_git_installed() -> bool:
    """Проверка, установлен ли Git"""
    # Пробуем несколько способов проверки
    methods = [
        # Способ 1: Через get_git_command()
        lambda: _try_git_command(get_git_command()),
        # Способ 2: Прямо через "git" (может быть в PATH)
        lambda: _try_git_command("git"),
        # Способ 3: Через shell на Unix (если предыдущие не сработали)
        lambda: _try_git_via_shell() if os.name != 'nt' else False
    ]
    
    for method in methods:
        try:
            if method():
                return True
        except Exception:
            continue
    
    return False

def _try_git_command(git_cmd: str) -> bool:
    """Попытка выполнить git --version с указанной командой"""
    try:
        result = subprocess.run(
            [git_cmd, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # Игнорируем stderr
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False

def _try_git_via_shell() -> bool:
    """Попытка найти git через shell команды (только для Unix)"""
    try:
        # Пробуем через which
        result = subprocess.run(
            ["which", "git"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if result.returncode == 0 and result.stdout.strip():
            git_path = result.stdout.strip()
            return _try_git_command(git_path)
    except Exception:
        pass
    
    try:
        # Пробуем через whereis (если which не сработал)
        result = subprocess.run(
            ["whereis", "-b", "git"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            # whereis выводит "git: /usr/bin/git /usr/local/bin/git"
            if ":" in output:
                paths = output.split(":", 1)[1].strip().split()
                for path in paths:
                    if os.path.exists(path) and os.access(path, os.X_OK):
                        if _try_git_command(path):
                            return True
    except Exception:
        pass
    
    return False

def get_git_status(path: Path) -> Dict[str, Any]:
    """Получение статуса Git репозитория"""
    # Сначала проверяем, является ли путь Git репозиторием
    if not is_git_repo(path):
        return {
            "is_repo": False,
            "error": "Not a Git repository"
        }
    
    # Пробуем выполнить git команду напрямую, без предварительной проверки
    git_cmd = None
    git_found = False
    
    # Пробуем несколько способов найти git
    candidates = [
        get_git_command(),  # Через нашу функцию
        "git",  # Прямо через PATH
    ]
    
    # Добавляем стандартные пути для Unix
    if os.name != 'nt':
        candidates.extend([
            "/usr/bin/git",
            "/usr/local/bin/git",
            "/bin/git"
        ])
    
    # Пробуем найти рабочий git
    for candidate in candidates:
        try:
            # Пробуем выполнить простую команду
            test_result = subprocess.run(
                [candidate, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3
            )
            if test_result.returncode == 0:
                git_cmd = candidate
                git_found = True
                break
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            continue
    
    # Если git не найден, возвращаем ошибку
    if not git_found:
        return {
            "is_repo": False,
            "error": "Git не установлен. Установите Git для работы с репозиториями.",
            "git_not_installed": True
        }
    
    try:
        # Проверяем, есть ли изменения
        try:
            result = subprocess.run(
                [git_cmd, "status", "--porcelain"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=10
            )
            has_changes = bool(result.stdout.strip())
        except Exception:
            has_changes = False
        
        # Получаем текущую ветку
        current_branch = None
        try:
            result = subprocess.run(
                [git_cmd, "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=10
            )
            current_branch = result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            pass
        
        # Если ветка не определена (нет коммитов), пробуем получить имя ветки из .git/HEAD
        if not current_branch:
            try:
                head_file = path / ".git" / "HEAD"
                if head_file.exists():
                    head_content = head_file.read_text().strip()
                    if head_content.startswith("ref: refs/heads/"):
                        current_branch = head_content.replace("ref: refs/heads/", "")
                    elif not head_content:
                        current_branch = "main"  # Дефолтная ветка
            except Exception:
                current_branch = "main"  # Дефолтная ветка
        
        # Получаем последний коммит
        last_commit = None
        try:
            # Проверяем, есть ли коммиты
            result = subprocess.run(
                [git_cmd, "rev-list", "--count", "HEAD"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=10
            )
            has_commits = result.returncode == 0 and result.stdout.strip() and int(result.stdout.strip() or "0") > 0
            
            if has_commits:
                result = subprocess.run(
                    [git_cmd, "log", "-1", "--format=%H|%s|%ar", "--no-decorate"],
                    cwd=str(path),
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
        except Exception:
            # Игнорируем ошибки при получении коммитов
            pass
        
        # Проверяем, есть ли обновления
        has_updates = False
        remote_url = None
        try:
            remote_url = get_git_remote(path)
            if remote_url:
                try:
                    result = subprocess.run(
                        [git_cmd, "fetch", "origin"],
                        cwd=str(path),
                        capture_output=True,
                        timeout=30
                    )
                    if result.returncode == 0:
                        result = subprocess.run(
                            [git_cmd, "rev-list", "--count", "HEAD..origin/" + (current_branch or "main")],
                            cwd=str(path),
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        has_updates = result.returncode == 0 and int(result.stdout.strip() or "0") > 0
                except Exception:
                    # Игнорируем ошибки при проверке обновлений
                    pass
        except Exception:
            # Игнорируем ошибки при получении remote
            pass
        
        return {
            "is_repo": True,
            "has_changes": has_changes,
            "current_branch": current_branch,
            "last_commit": last_commit,
            "has_updates": has_updates,
            "remote": remote_url
        }
    except FileNotFoundError:
        return {
            "is_repo": False,
            "error": "Git не установлен. Установите Git для работы с репозиториями.",
            "git_not_installed": True
        }
    except Exception as e:
        error_msg = str(e)
        # Проверяем, является ли это ошибкой отсутствия Git
        if "No such file or directory" in error_msg or "git" in error_msg.lower():
            return {
                "is_repo": False,
                "error": "Git не установлен. Установите Git для работы с репозиториями.",
                "git_not_installed": True
            }
        return {
            "is_repo": False,
            "error": error_msg
        }

def init_git_repo(path: Path, repo_url: Optional[str] = None) -> Tuple[bool, str]:
    """Инициализация Git репозитория"""
    if is_git_repo(path):
        return True, "Already a Git repository"
    
    # Пробуем найти git напрямую, без предварительной проверки
    git_cmd = None
    git_found = False
    
    # Пробуем несколько способов найти git
    candidates = [
        get_git_command(),  # Через нашу функцию
        "git",  # Прямо через PATH
    ]
    
    # Добавляем стандартные пути для Unix
    if os.name != 'nt':
        candidates.extend([
            "/usr/bin/git",
            "/usr/local/bin/git",
            "/bin/git"
        ])
    
    # Пробуем найти рабочий git
    for candidate in candidates:
        try:
            # Пробуем выполнить простую команду
            test_result = subprocess.run(
                [candidate, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3
            )
            if test_result.returncode == 0:
                git_cmd = candidate
                git_found = True
                break
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            continue
    
    # Если git не найден, возвращаем ошибку
    if not git_found:
        return False, "Git не установлен. Установите Git для работы с репозиториями."
    
    try:
        # Инициализируем репозиторий
        result = subprocess.run(
            [git_cmd, "init"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return False, f"Failed to initialize Git repository: {result.stderr}"
        
        # Настраиваем имя пользователя и email для коммитов (если не настроено)
        # Проверяем, настроены ли git config
        result = subprocess.run(
            [git_cmd, "config", "user.name"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0 or not result.stdout.strip():
            # Устанавливаем дефолтные значения
            subprocess.run(
                [git_cmd, "config", "user.name", "Panel User"],
                cwd=str(path),
                capture_output=True,
                timeout=5
            )
        
        result = subprocess.run(
            [git_cmd, "config", "user.email"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0 or not result.stdout.strip():
            subprocess.run(
                [git_cmd, "config", "user.email", "panel@localhost"],
                cwd=str(path),
                capture_output=True,
                timeout=5
            )
        
        # Создаем начальный коммит, если есть файлы для коммита
        subprocess.run(
            [git_cmd, "add", "."],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Проверяем, есть ли что-то для коммита
        result = subprocess.run(
            [git_cmd, "status", "--porcelain"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.stdout.strip():
            # Есть изменения для коммита
            subprocess.run(
                [git_cmd, "commit", "-m", "Initial commit"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=30
            )
            # Не критично, если коммит не удался (может быть пустой репозиторий)
        
        # Если указан URL, добавляем remote
        if repo_url:
            success, msg = set_git_remote(path, repo_url)
            if not success:
                return False, f"Failed to set remote: {msg}"
        
        return True, "Git repository initialized successfully"
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except FileNotFoundError:
        return False, "Git не установлен. Установите Git для работы с репозиториями."
    except Exception as e:
        error_msg = str(e)
        if "No such file or directory" in error_msg or "git" in error_msg.lower():
            return False, "Git не установлен. Установите Git для работы с репозиториями."
        return False, str(e)

def update_panel_from_git() -> Tuple[bool, str]:
    """Обновление панели из GitHub репозитория"""
    if not is_git_repo(BASE_DIR):
        return False, "Not a Git repository"
    
    # Пробуем найти git напрямую
    git_cmd = None
    git_found = False
    
    candidates = [
        get_git_command(),
        "git",
    ]
    
    if os.name != 'nt':
        candidates.extend([
            "/usr/bin/git",
            "/usr/local/bin/git",
            "/bin/git"
        ])
    
    for candidate in candidates:
        try:
            test_result = subprocess.run(
                [candidate, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3
            )
            if test_result.returncode == 0:
                git_cmd = candidate
                git_found = True
                break
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            continue
    
    if not git_found:
        return False, "Git не установлен. Установите Git для работы с репозиториями."
    
    try:
        # Используем SSH окружение для приватных репозиториев
        env = get_git_env_with_ssh()
        
        # Сохраняем изменения перед обновлением
        result = subprocess.run(
            [git_cmd, "stash"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        # Получаем обновления
        result = subprocess.run(
            [git_cmd, "fetch", "origin"],
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
            [git_cmd, "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )
        branch = result.stdout.strip() if result.returncode == 0 else "main"
        
        # Обновляем код
        result = subprocess.run(
            [git_cmd, "pull", "origin", branch],
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
        return False, "Git не установлен. Установите Git для работы с репозиториями."
    except Exception as e:
        error_msg = str(e)
        if "No such file or directory" in error_msg or "git" in error_msg.lower():
            return False, "Git не установлен. Установите Git для работы с репозиториями."
        return False, str(e)

def update_bot_from_git(bot_dir: Path, repo_url: Optional[str] = None, branch: str = "main") -> Tuple[bool, str]:
    """Обновление файлов бота из GitHub репозитория"""
    # Пробуем найти git напрямую
    git_cmd = None
    git_found = False
    
    candidates = [
        get_git_command(),
        "git",
    ]
    
    if os.name != 'nt':
        candidates.extend([
            "/usr/bin/git",
            "/usr/local/bin/git",
            "/bin/git"
        ])
    
    for candidate in candidates:
        try:
            test_result = subprocess.run(
                [candidate, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3
            )
            if test_result.returncode == 0:
                git_cmd = candidate
                git_found = True
                break
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            continue
    
    if not git_found:
        return False, "Git не установлен. Установите Git для работы с репозиториями."
    
    try:
        # Если репозиторий не инициализирован
        if not is_git_repo(bot_dir):
            if not repo_url:
                return False, "Repository URL required for initialization"
            
            # Клонируем репозиторий
            # Проверяем, не пуста ли директория (игнорируем .gitkeep, .git и config.json)
            if bot_dir.exists():
                files = [f for f in bot_dir.iterdir() if f.name not in ['.gitkeep', '.git', 'config.json']]
                if files:
                    return False, f"Directory is not empty and not a Git repository. Found files: {', '.join([f.name for f in files[:5]])}"
            
            # Преобразуем HTTPS URL в SSH для приватных репозиториев (если нужно)
            clone_url = repo_url
            if repo_url.startswith('https://') and 'github.com' in repo_url:
                # Пользователь может использовать SSH URL напрямую
                # Если используется HTTPS, можно автоматически конвертировать
                # Но пока оставим как есть, чтобы пользователь сам выбирал
                pass
            
            # Используем SSH окружение для Git команд
            env = get_git_env_with_ssh()
            
            # Git clone не может клонировать в существующую директорию, нужно клонировать во временную и переместить
            # Или использовать git clone с пустой директорией
            if bot_dir.exists() and any(bot_dir.iterdir()):
                # Если директория существует и не пуста (но не Git репозиторий), это ошибка
                # Но мы уже проверили выше, так что здесь должно быть пусто (только config.json)
                pass
            
            result = subprocess.run(
                [git_cmd, "clone", "-b", branch, clone_url, str(bot_dir)],
                capture_output=True,
                text=True,
                timeout=300,
                env=env
            )
            
            if result.returncode == 0:
                return True, "Repository cloned successfully"
            error_msg = result.stderr or result.stdout or "Clone failed"
            return False, f"Git clone failed: {error_msg}"
        
        # Если репозиторий уже существует, обновляем его
        # Используем SSH окружение для всех Git операций
        env = get_git_env_with_ssh()
        
        # Сохраняем изменения
        result = subprocess.run(
            [git_cmd, "stash"],
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
            [git_cmd, "fetch", "origin"],
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
            [git_cmd, "pull", "origin", branch],
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
        return False, "Git не установлен. Установите Git для работы с репозиториями."
    except Exception as e:
        error_msg = str(e)
        if "No such file or directory" in error_msg or "git" in error_msg.lower():
            return False, "Git не установлен. Установите Git для работы с репозиториями."
        return False, str(e)

