"""
Управление SSH ключами для доступа к приватным Git репозиториям
"""
import subprocess
import os
from pathlib import Path
from typing import Tuple, Optional
from backend.config import DATA_DIR

# Директория для хранения SSH ключей панели
SSH_DIR = DATA_DIR / "ssh"
SSH_PRIVATE_KEY = SSH_DIR / "panel_deploy_key"
SSH_PUBLIC_KEY = SSH_DIR / "panel_deploy_key.pub"
SSH_CONFIG_FILE = SSH_DIR / "config"

def ensure_ssh_dir() -> Path:
    """Создание директории для SSH ключей, если её нет"""
    SSH_DIR.mkdir(parents=True, exist_ok=True)
    # Устанавливаем правильные права доступа (700)
    if os.name != 'nt':  # Unix-like системы
        os.chmod(SSH_DIR, 0o700)
    return SSH_DIR

def generate_ssh_key(force: bool = False) -> Tuple[bool, str]:
    """
    Генерация SSH ключа для панели (если ещё не существует)
    
    Args:
        force: Если True, перезаписывает существующий ключ
    
    Returns:
        (success, message)
    """
    try:
        ensure_ssh_dir()
        
        # Проверяем, существует ли уже ключ
        if not force and SSH_PRIVATE_KEY.exists() and SSH_PUBLIC_KEY.exists():
            return True, "SSH key already exists"
        
        # Если force=True, удаляем существующие ключи
        if force:
            try:
                if SSH_PRIVATE_KEY.exists():
                    SSH_PRIVATE_KEY.unlink()
                if SSH_PUBLIC_KEY.exists():
                    SSH_PUBLIC_KEY.unlink()
            except Exception as e:
                return False, f"Failed to remove existing keys: {str(e)}"
        
        # Генерируем новый SSH ключ
        # Используем тип ed25519 (более безопасный и современный)
        result = subprocess.run(
            [
                "ssh-keygen",
                "-t", "ed25519",
                "-f", str(SSH_PRIVATE_KEY),
                "-N", "",  # Без пароля
                "-C", "ds-tg-panel-bot-deploy-key"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Устанавливаем правильные права доступа для приватного ключа
            if os.name != 'nt':  # Unix-like системы
                os.chmod(SSH_PRIVATE_KEY, 0o600)
            return True, "SSH key generated successfully"
        else:
            error_msg = result.stderr or "Unknown error"
            # Если ed25519 не поддерживается, пробуем RSA
            if "unknown key type" in error_msg.lower() or "invalid" in error_msg.lower():
                result = subprocess.run(
                    [
                        "ssh-keygen",
                        "-t", "rsa",
                        "-b", "4096",
                        "-f", str(SSH_PRIVATE_KEY),
                        "-N", "",
                        "-C", "ds-tg-panel-bot-deploy-key"
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    if os.name != 'nt':
                        os.chmod(SSH_PRIVATE_KEY, 0o600)
                    return True, "SSH key (RSA) generated successfully"
            
            return False, error_msg
            
    except subprocess.TimeoutExpired:
        return False, "Timeout while generating SSH key"
    except FileNotFoundError:
        return False, "ssh-keygen not found. Please install OpenSSH."
    except Exception as e:
        return False, str(e)

def get_public_key() -> Optional[str]:
    """Получение публичного SSH ключа"""
    try:
        ensure_ssh_dir()
        
        # Если ключ не существует, генерируем его
        if not SSH_PUBLIC_KEY.exists():
            success, msg = generate_ssh_key()
            if not success:
                return None
        
        # Проверяем существование файла перед чтением
        if not SSH_PUBLIC_KEY.exists():
            return None
        
        # Читаем файл заново каждый раз (без кэширования)
        with open(SSH_PUBLIC_KEY, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            return content if content else None
        
    except Exception:
        return None

def get_ssh_key_exists() -> bool:
    """Проверка существования SSH ключа"""
    return SSH_PRIVATE_KEY.exists() and SSH_PUBLIC_KEY.exists()

def convert_https_to_ssh(url: str) -> str:
    """
    Преобразование HTTPS URL в SSH URL для GitHub/GitLab
    Пример: https://github.com/user/repo.git -> git@github.com:user/repo.git
    """
    if url.startswith('git@'):
        return url  # Уже SSH формат
    
    if url.startswith('https://'):
        # Убираем https://
        url = url.replace('https://', '')
        # Убираем .git в конце если есть
        if url.endswith('.git'):
            url = url[:-4]
        # Разделяем на части
        parts = url.split('/', 1)
        if len(parts) == 2:
            host = parts[0]
            path = parts[1]
            return f"git@{host}:{path}.git"
    
    return url

def setup_ssh_config_for_github():
    """Настройка SSH config для использования ключа панели с GitHub"""
    try:
        ensure_ssh_dir()
        # Используем абсолютный путь для надежности на всех платформах
        identity_file_path = str(SSH_PRIVATE_KEY.resolve())
        config_content = f"""Host github.com
    HostName github.com
    User git
    IdentityFile {identity_file_path}
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
"""
        with open(SSH_CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write(config_content.strip())
        if os.name != 'nt':
            os.chmod(SSH_CONFIG_FILE, 0o600)
    except Exception:
        pass

def get_git_env_with_ssh() -> dict:
    """
    Возвращает переменные окружения для Git команд с SSH
    """
    env = os.environ.copy()
    
    # Устанавливаем переменную SSH для использования нашего ключа
    if SSH_CONFIG_FILE.exists():
        # Используем GIT_SSH_COMMAND для всех платформ (поддерживается в Git 2.3+)
        # Это более надежный способ, чем GIT_SSH
        ssh_config_path = str(SSH_CONFIG_FILE.resolve())
        ssh_key_path = str(SSH_PRIVATE_KEY.resolve())
        
        # Экранируем пути для безопасности (на случай пробелов)
        # На Unix используем одинарные кавычки, на Windows - двойные
        if os.name == 'nt':
            # Windows
            ssh_cmd = f'ssh -F "{ssh_config_path}" -i "{ssh_key_path}"'
        else:
            # Unix-like (Linux, macOS)
            # Используем одинарные кавычки для экранирования путей
            ssh_cmd = f"ssh -F '{ssh_config_path}' -i '{ssh_key_path}'"
        
        env['GIT_SSH_COMMAND'] = ssh_cmd
    
    return env

