"""
Главный файл FastAPI приложения - панель управления ботами
"""
from fastapi import FastAPI, Request, HTTPException, Response, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import shutil
import os

from backend.config import BASE_DIR, set_admin_password_hash, get_admin_password_hash
from backend.auth import verify_password, create_session_token, get_session_from_request, require_auth
from backend.database import (
    create_bot, get_bot, get_all_bots, update_bot, delete_bot
)
from backend.bot_manager import start_bot, stop_bot, get_bot_process_info, is_process_running
from backend.db_manager import (
    create_bot_database, get_bot_database_info, 
    execute_sql_query, get_phpmyadmin_url
)
from backend.git_manager import (
    update_panel_from_git, update_bot_from_git,
    get_git_status, get_git_remote, is_git_repo, init_git_repo,
    GitRepository
)
from backend.ssh_manager import (
    generate_ssh_key, get_public_key, get_ssh_key_exists,
    setup_ssh_config_for_github, test_ssh_connection, get_ssh_key_info,
    extract_host_from_url, convert_https_to_ssh
)

app = FastAPI(title="Bot Admin Panel")

# Подключение статических файлов и шаблонов
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "frontend" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "frontend" / "templates"))

# Модели данных
class LoginRequest(BaseModel):
    password: str

class BotCreate(BaseModel):
    name: str
    bot_type: str  # 'discord' or 'telegram'
    start_file: Optional[str] = None
    cpu_limit: float = 50.0
    memory_limit: int = 512
    git_repo_url: Optional[str] = None
    git_branch: str = "main"

class BotUpdate(BaseModel):
    name: Optional[str] = None
    start_file: Optional[str] = None
    cpu_limit: Optional[float] = None
    memory_limit: Optional[int] = None
    git_repo_url: Optional[str] = None
    git_branch: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

# Middleware для проверки авторизации
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Разрешаем доступ к публичным маршрутам
    public_paths = ["/login", "/api/login", "/api/auth/check", "/static"]
    if any(request.url.path.startswith(path) for path in public_paths):
        return await call_next(request)
    
    # Проверяем авторизацию для остальных маршрутов
    token = get_session_from_request(request)
    if not token:
        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
        return Response(content='Redirecting to login...', status_code=302, headers={"Location": "/login"})
    
    response = await call_next(request)
    return response

# Роуты для страниц
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/bot/{bot_id}", response_class=HTMLResponse)
async def bot_manage_page(request: Request, bot_id: int):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return templates.TemplateResponse("bot_manage.html", {"request": request, "bot_id": bot_id})

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})

# API роуты
@app.post("/api/login")
async def login(login_data: LoginRequest, response: Response):
    if verify_password(login_data.password):
        token = create_session_token()
        response.set_cookie(
            key="panel_session",
            value=token,
            max_age=86400,
            httponly=True,
            samesite="lax"
        )
        return {"success": True, "token": token}
    else:
        raise HTTPException(status_code=401, detail="Invalid password")

@app.get("/api/auth/check")
async def check_auth(request: Request):
    token = get_session_from_request(request)
    if token:
        return {"authenticated": True}
    raise HTTPException(status_code=401, detail="Not authenticated")

@app.get("/api/bots")
async def list_bots():
    bots = get_all_bots()
    
    # Синхронизируем статусы ботов с реальными процессами
    for bot in bots:
        if bot['status'] == 'running' and bot['pid']:
            if not is_process_running(bot['pid']):
                # Процесс не запущен, обновляем статус
                update_bot(bot['id'], pid=None, status='stopped')
                bot['status'] = 'stopped'
                bot['pid'] = None
    
    return bots

@app.post("/api/bots")
async def create_bot_endpoint(bot_data: BotCreate):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        bot_id = create_bot(
            name=bot_data.name,
            bot_type=bot_data.bot_type,
            start_file=bot_data.start_file,
            cpu_limit=bot_data.cpu_limit,
            memory_limit=bot_data.memory_limit,
            git_repo_url=bot_data.git_repo_url,
            git_branch=bot_data.git_branch
        )
        
        # Если указан репозиторий, клонируем его (репозиторий не обязателен)
        if bot_data.git_repo_url and bot_data.git_repo_url.strip():
            try:
                bot = get_bot(bot_id)
                if not bot:
                    logger.error(f"Bot {bot_id} not found after creation")
                    return {"id": bot_id, "success": True, "warning": "Bot created but could not be found for git clone"}
                
                bot_dir = Path(bot['bot_dir'])
                
                # Временно перемещаем config.json, чтобы директория была пуста для клонирования
                config_path = bot_dir / "config.json"
                config_backup = None
                if config_path.exists():
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
                        config_backup = tmp.name
                        shutil.copy2(config_path, config_backup)
                    config_path.unlink()
                
                # Удаляем шаблонные файлы, если они были созданы
                start_file_path = bot_dir / (bot_data.start_file or 'main.py')
                if start_file_path.exists():
                    start_file_path.unlink()
                requirements_path = bot_dir / "requirements.txt"
                if requirements_path.exists():
                    requirements_path.unlink()
                
                # Используем новую систему GitRepository для клонирования
                repo = GitRepository(bot_dir, bot_data.git_repo_url.strip(), bot_data.git_branch)
                if not repo.is_git_installed():
                    return {"id": bot_id, "success": True, "warning": "Git не установлен. Репозиторий не клонирован."}
                
                success, message = repo.clone(bot_data.git_repo_url.strip(), bot_data.git_branch)
                
                # Восстанавливаем config.json
                if config_backup:
                    try:
                        shutil.copy2(config_backup, config_path)
                        os.unlink(config_backup)
                    except Exception as restore_error:
                        logger.error(f"Failed to restore config.json: {restore_error}")
                
                if not success:
                    # Не удаляем бота, но возвращаем предупреждение
                    return {"id": bot_id, "success": True, "warning": f"Бот создан, но клонирование репозитория не удалось: {message}"}
            except Exception as git_error:
                logger.error(f"Error during git clone for bot {bot_id}: {git_error}", exc_info=True)
                # Бот создан, но клонирование не удалось - не критично
                return {"id": bot_id, "success": True, "warning": f"Бот создан, но произошла ошибка при клонировании репозитория: {str(git_error)}"}
        
        return {"id": bot_id, "success": True}
    except Exception as e:
        logger.error(f"Error creating bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка создания бота: {str(e)}")(f"Error creating bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка создания бота: {str(e)}")

@app.get("/api/bots/{bot_id}")
async def get_bot_endpoint(bot_id: int):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return bot

@app.put("/api/bots/{bot_id}")
async def update_bot_endpoint(bot_id: int, bot_data: BotUpdate):
    updates = bot_data.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    success = update_bot(bot_id, **updates)
    if not success:
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"success": True}

@app.delete("/api/bots/{bot_id}")
async def delete_bot_endpoint(bot_id: int):
    success = delete_bot(bot_id)
    if not success:
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"success": True}

# File management endpoints
@app.get("/api/bots/{bot_id}/files")
async def list_bot_files(bot_id: int):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    bot_dir = Path(bot['bot_dir'])
    if not bot_dir.exists():
        return []
    
    def build_tree(directory: Path, base_path: Path = None):
        if base_path is None:
            base_path = directory
        
        items = []
        try:
            for item in sorted(directory.iterdir()):
                # Пропускаем config.json
                if item.name == "config.json":
                    continue
                    
                rel_path = item.relative_to(base_path)
                node = {
                    "name": item.name,
                    "path": str(rel_path).replace("\\", "/"),
                    "type": "directory" if item.is_dir() else "file"
                }
                
                if item.is_dir():
                    node["children"] = build_tree(item, base_path)
                
                items.append(node)
        except PermissionError:
            pass
        
        return items
    
    return build_tree(bot_dir)

@app.get("/api/bots/{bot_id}/file")
async def get_bot_file(bot_id: int, path: str, binary: bool = False):
    """
    Получение содержимого файла.
    Если binary=True, возвращает base64-encoded содержимое для медиа-файлов.
    """
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    file_path = Path(bot['bot_dir']) / path
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Проверка безопасности - файл должен быть внутри директории бота
    try:
        file_path.resolve().relative_to(Path(bot['bot_dir']).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        # Определяем расширение файла
        ext = file_path.suffix.lower()
        image_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico',
            '.tiff', '.tif', '.avif', '.apng', '.heic', '.heif', '.jxl'
        }
        video_extensions = {
            '.mp4', '.webm', '.ogg', '.ogv', '.mov', '.avi', '.mkv', '.flv', '.wmv',
            '.m4v', '.mpeg', '.mpg', '.3gp', '.3g2', '.f4v', '.ts', '.m2ts', '.asf'
        }
        audio_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma', '.opus', '.oga', '.webm'}
        
        is_image = ext in image_extensions
        is_video = ext in video_extensions
        is_audio = ext in audio_extensions
        
        # Если это медиа-файл или явно запрошен бинарный режим, возвращаем base64
        if binary or is_image or is_video or is_audio:
            import base64
            try:
                with open(file_path, 'rb') as f:
                    file_bytes = f.read()
                    file_base64 = base64.b64encode(file_bytes).decode('utf-8')
                    mime_type = 'application/octet-stream'
                    if is_image:
                        if ext == '.jpg' or ext == '.jpeg':
                            mime_type = 'image/jpeg'
                        elif ext == '.png' or ext == '.apng':
                            mime_type = 'image/png'
                        elif ext == '.gif':
                            mime_type = 'image/gif'
                        elif ext == '.webp':
                            mime_type = 'image/webp'
                        elif ext == '.svg':
                            mime_type = 'image/svg+xml'
                        elif ext == '.bmp':
                            mime_type = 'image/bmp'
                        elif ext == '.tiff' or ext == '.tif':
                            mime_type = 'image/tiff'
                        elif ext == '.avif':
                            mime_type = 'image/avif'
                        elif ext == '.heic' or ext == '.heif':
                            mime_type = 'image/heic'
                        elif ext == '.jxl':
                            mime_type = 'image/jxl'
                        elif ext == '.ico':
                            mime_type = 'image/x-icon'
                    elif is_video:
                        if ext == '.mp4' or ext == '.m4v':
                            mime_type = 'video/mp4'
                        elif ext == '.webm':
                            mime_type = 'video/webm'
                        elif ext == '.ogg' or ext == '.ogv':
                            mime_type = 'video/ogg'
                        elif ext == '.mov':
                            mime_type = 'video/quicktime'
                        elif ext == '.avi':
                            mime_type = 'video/x-msvideo'
                        elif ext == '.mkv':
                            mime_type = 'video/x-matroska'
                        elif ext == '.flv' or ext == '.f4v':
                            mime_type = 'video/x-flv'
                        elif ext == '.wmv' or ext == '.asf':
                            mime_type = 'video/x-ms-wmv'
                        elif ext == '.mpeg' or ext == '.mpg':
                            mime_type = 'video/mpeg'
                        elif ext == '.3gp' or ext == '.3g2':
                            mime_type = 'video/3gpp'
                        elif ext == '.ts' or ext == '.m2ts':
                            mime_type = 'video/mp2t'
                    elif is_audio:
                        if ext == '.mp3':
                            mime_type = 'audio/mpeg'
                        elif ext == '.wav':
                            mime_type = 'audio/wav'
                        elif ext == '.ogg':
                            mime_type = 'audio/ogg'
                        elif ext == '.flac':
                            mime_type = 'audio/flac'
                        elif ext == '.m4a':
                            mime_type = 'audio/mp4'
                        elif ext == '.aac':
                            mime_type = 'audio/aac'
                        elif ext == '.wma':
                            mime_type = 'audio/x-ms-wma'
                        elif ext == '.opus':
                            mime_type = 'audio/opus'
                        elif ext == '.oga':
                            mime_type = 'audio/ogg'
                        elif ext == '.webm':
                            mime_type = 'audio/webm'
                    
                    return {
                        "content": file_base64,
                        "path": path,
                        "binary": True,
                        "mime_type": mime_type,
                        "is_image": is_image,
                        "is_video": is_video,
                        "is_audio": is_audio
                    }
            except (IOError, OSError, PermissionError) as e:
                raise HTTPException(status_code=500, detail=f"Error reading file (file may be locked): {str(e)}")
        else:
            # Текстовый файл - читаем как текст
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
            except (IOError, OSError, PermissionError) as e:
                # Если файл заблокирован (например, bot.log открыт процессом), пробуем другой способ
                import shutil
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.tmp') as tmp:
                    try:
                        shutil.copy2(file_path, tmp.name)
                        tmp_path = Path(tmp.name)
                        content = tmp_path.read_text(encoding='utf-8', errors='ignore')
                        tmp_path.unlink()  # Удаляем временный файл
                    except Exception:
                        # Если и это не получилось, возвращаем ошибку
                        raise HTTPException(status_code=500, detail=f"Error reading file (file may be locked): {str(e)}")
            
            return {"content": content, "path": path, "binary": False}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

@app.put("/api/bots/{bot_id}/file")
async def save_bot_file(bot_id: int, request: Request):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    data = await request.json()
    path = data.get("path")
    content = data.get("content", "")
    
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    
    file_path = Path(bot['bot_dir']) / path
    
    # Проверка безопасности
    try:
        file_path.resolve().relative_to(Path(bot['bot_dir']).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Создаем директории если нужно
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        file_path.write_text(content, encoding='utf-8')
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")

@app.post("/api/bots/{bot_id}/file")
async def create_bot_file(bot_id: int, request: Request):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    data = await request.json()
    path = data.get("path")
    content = data.get("content", "")
    
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    
    file_path = Path(bot['bot_dir']) / path
    
    # Проверка безопасности
    try:
        file_path.resolve().relative_to(Path(bot['bot_dir']).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if file_path.exists():
        raise HTTPException(status_code=400, detail="File already exists")
    
    # Создаем директории если нужно
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        file_path.write_text(content, encoding='utf-8')
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating file: {str(e)}")

@app.delete("/api/bots/{bot_id}/file")
async def delete_bot_file(bot_id: int, path: str):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    file_path = Path(bot['bot_dir']) / path
    
    # Проверка безопасности
    try:
        file_path.resolve().relative_to(Path(bot['bot_dir']).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Защита от удаления config.json
    if file_path.name == "config.json":
        raise HTTPException(status_code=403, detail="Cannot delete config.json")
    
    try:
        if file_path.is_dir():
            import shutil
            shutil.rmtree(file_path)
        else:
            file_path.unlink()
        return {"success": True}
    except PermissionError as e:
        error_msg = str(e)
        if "WinError 32" in error_msg or "cannot access" in error_msg.lower() or "file is locked" in error_msg.lower():
            raise HTTPException(status_code=500, detail="File is locked by another process. Stop the bot before deleting files in use.")
        raise HTTPException(status_code=500, detail=f"Permission denied: {error_msg}")
    except OSError as e:
        error_msg = str(e)
        if "WinError 32" in error_msg or "cannot access" in error_msg.lower() or "file is locked" in error_msg.lower():
            raise HTTPException(status_code=500, detail="File is locked by another process. Stop the bot before deleting files in use.")
        raise HTTPException(status_code=500, detail=f"Error deleting file: {error_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")

@app.post("/api/bots/{bot_id}/file/rename")
async def rename_bot_file(bot_id: int, request: Request):
    """Переименование файла или папки"""
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    data = await request.json()
    old_path = data.get("old_path")
    new_path = data.get("new_path")
    
    if not old_path or not new_path:
        raise HTTPException(status_code=400, detail="old_path and new_path are required")
    
    old_file_path = Path(bot['bot_dir']) / old_path
    new_file_path = Path(bot['bot_dir']) / new_path
    
    # Проверка безопасности
    try:
        old_file_path.resolve().relative_to(Path(bot['bot_dir']).resolve())
        new_file_path.resolve().relative_to(Path(bot['bot_dir']).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not old_file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    if new_file_path.exists():
        raise HTTPException(status_code=400, detail="Target file already exists")
    
    # Защита от переименования config.json
    if old_file_path.name == "config.json":
        raise HTTPException(status_code=403, detail="Cannot rename config.json")
    
    try:
        # Создаем директории если нужно
        new_file_path.parent.mkdir(parents=True, exist_ok=True)
        old_file_path.rename(new_file_path)
        return {"success": True, "new_path": str(new_file_path.relative_to(Path(bot['bot_dir'])))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error renaming file: {str(e)}")

@app.post("/api/bots/{bot_id}/file/upload")
async def upload_bot_file(bot_id: int, files: List[UploadFile] = File(...), path: str = Form("")):
    """Загрузка файла(ов) в директорию бота"""
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    try:
        destination_path = path if path else ""
        
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        uploaded_files = []
        errors = []
        bot_dir_path = Path(bot['bot_dir']).resolve()
        
        for file in files:
            # Проверяем, что это объект файла (может быть UploadFile из FastAPI или starlette.datastructures.UploadFile)
            if not hasattr(file, 'filename') or not hasattr(file, 'read'):
                errors.append(f"Skipping invalid file object: {type(file)}")
                continue
            
            if not file.filename:
                errors.append("Skipping file with no filename")
                continue
            
            # Формируем путь назначения
            if destination_path and destination_path.strip():
                target_path = bot_dir_path / destination_path.strip() / file.filename
            else:
                target_path = bot_dir_path / file.filename
            
            # Проверка безопасности
            try:
                resolved_target = target_path.resolve()
                resolved_bot_dir = bot_dir_path.resolve()
                # Проверяем, что целевой путь находится внутри директории бота
                try:
                    resolved_target.relative_to(resolved_bot_dir)
                except ValueError:
                    errors.append(f"Unsafe path for file {file.filename}: path outside bot directory")
                    continue
            except Exception as e:
                errors.append(f"Path resolution error for file {file.filename}: {str(e)}")
                continue
            
            # Создаем директории если нужно
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Failed to create directory for {file.filename}: {str(e)}")
                continue
            
            try:
                # Читаем содержимое файла
                content = await file.read()
                target_path.write_bytes(content)
                relative_path = str(target_path.relative_to(bot_dir_path))
                uploaded_files.append(relative_path.replace("\\", "/"))
            except Exception as e:
                errors.append(f"Failed to upload {file.filename}: {str(e)}")
                continue
        
        if not uploaded_files:
            error_msg = "No files were uploaded"
            if errors:
                error_msg += ". Errors: " + "; ".join(errors[:3])  # Показываем первые 3 ошибки
            raise HTTPException(status_code=500, detail=error_msg)
        
        return {"success": True, "uploaded_files": uploaded_files}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

@app.post("/api/bots/{bot_id}/file/directory")
async def create_bot_directory(bot_id: int, request: Request):
    """Создание директории"""
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    data = await request.json()
    path = data.get("path")
    
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    
    dir_path = Path(bot['bot_dir']) / path
    
    # Проверка безопасности
    try:
        dir_path.resolve().relative_to(Path(bot['bot_dir']).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if dir_path.exists():
        raise HTTPException(status_code=400, detail="Directory already exists")
    
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating directory: {str(e)}")

@app.get("/api/bots/{bot_id}/logs")
async def get_bot_logs(bot_id: int, lines: int = 500):
    """Получение логов бота из единого файла"""
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    log_dir = Path(bot['bot_dir']) / "logs"
    log_file = log_dir / "bot.log"
    
    if not log_file.exists():
        return {"logs": [], "total_lines": 0}
    
    try:
        # Читаем последние N строк
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            total_lines = len(all_lines)
            # Берем последние lines строк
            log_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "logs": [line.rstrip('\n\r') for line in log_lines],
            "total_lines": total_lines
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading logs: {str(e)}")

# Bot process management endpoints
@app.post("/api/bots/{bot_id}/start")
async def start_bot_endpoint(bot_id: int):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    # Проверяем наличие стартового файла
    if not bot.get('start_file'):
        raise HTTPException(status_code=400, detail="Start file not specified")
    
    from pathlib import Path
    start_file_path = Path(bot['bot_dir']) / bot['start_file']
    if not start_file_path.exists():
        raise HTTPException(status_code=400, detail=f"Start file not found: {bot['start_file']}")
    
    result = start_bot(bot_id)
    if isinstance(result, tuple):
        success, error_msg = result
    else:
        # Обратная совместимость
        success = result
        error_msg = None
    
    if not success:
        error_detail = error_msg if error_msg else "Failed to start bot"
        
        # Извлекаем основную ошибку из вывода
        if "ModuleNotFoundError" in error_detail or "No module named" in error_detail:
            # Извлекаем имя модуля из ошибки
            import re
            match = re.search(r"No module named ['\"](\w+)['\"]", error_detail)
            if match:
                module_name = match.group(1)
                # Правильные названия пакетов
                package_map = {
                    'telegram': 'python-telegram-bot',
                    'discord': 'discord.py'
                }
                package_name = package_map.get(module_name, module_name)
                error_detail = f"Отсутствует модуль '{module_name}'. Зависимости должны устанавливаться автоматически из requirements.txt. Если ошибка повторяется, проверьте файл requirements.txt в директории бота (должно быть: {package_name})"
            else:
                error_detail = f"Отсутствует необходимый модуль. Установите зависимости бота. Ошибка: {error_detail.split(chr(10))[-1] if chr(10) in error_detail else error_detail}"
        elif "Traceback" in error_detail:
            # Извлекаем последнюю строку с ошибкой из traceback
            lines = error_detail.split('\n')
            for line in reversed(lines):
                line = line.strip()
                if line and ('Error:' in line or 'Exception:' in line or 'ModuleNotFoundError' in line):
                    error_detail = f"Ошибка запуска бота: {line}"
                    break
        
        raise HTTPException(status_code=500, detail=error_detail)
    
    return {"success": True}

@app.post("/api/bots/{bot_id}/stop")
async def stop_bot_endpoint(bot_id: int):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    success = stop_bot(bot_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to stop bot")
    return {"success": True}

@app.get("/api/bots/{bot_id}/status")
async def get_bot_status(bot_id: int):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    bot_status = bot.get('status', 'stopped')
    
    # Если статус installing, возвращаем его сразу
    if bot_status == 'installing':
        return {
            "running": False,
            "status": "installing",
            "cpu_percent": None,
            "memory_mb": None,
            "pid": None
        }
    
    if bot_status != 'running':
        return {
            "running": False,
            "status": bot_status,
            "cpu_percent": None,
            "memory_mb": None,
            "pid": None
        }
    
    process_info = get_bot_process_info(bot_id)
    if not process_info:
        return {
            "running": False,
            "status": "stopped",
            "cpu_percent": None,
            "memory_mb": None,
            "pid": None
        }
    
    return {
        "running": True,
        "status": "running",
        "cpu_percent": process_info.get("cpu_percent"),
        "memory_mb": process_info.get("memory_mb"),
        "pid": process_info.get("pid")
    }

# Database management endpoints
@app.post("/api/bots/{bot_id}/db")
async def create_bot_database_endpoint(bot_id: int):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    try:
        db_info = create_bot_database(bot_id)
        return {"success": True, **db_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bots/{bot_id}/db")
async def get_bot_database_endpoint(bot_id: int):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    db_info = get_bot_database_info(bot_id)
    if db_info:
        return db_info
    else:
        return {"db_name": None, "error": "Database not created"}

@app.post("/api/bots/{bot_id}/db/query")
async def execute_sql_endpoint(bot_id: int, request: Request):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    data = await request.json()
    query = data.get("query")
    
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    result = execute_sql_query(bot_id, query)
    if result.get("success"):
        return result
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

@app.get("/api/bots/{bot_id}/db/phpmyadmin")
async def get_phpmyadmin_url_endpoint(bot_id: int):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    if not bot.get('db_name'):
        raise HTTPException(status_code=404, detail="Database not created")
    
    url = get_phpmyadmin_url(bot_id)
    return {"url": url}

# Bot Git endpoints
@app.get("/api/bots/{bot_id}/git-status")
async def get_bot_git_status(bot_id: int):
    """
    Получение детального статуса Git репозитория бота
    Включает информацию о ветке, коммитах, обновлениях и локальных изменениях
    """
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    bot_dir = Path(bot['bot_dir'])
    repo_url = bot.get('git_repo_url')
    branch = bot.get('git_branch', 'main')
    
    # Используем новую систему GitRepository
    repo = GitRepository(bot_dir, repo_url, branch)
    status = repo.get_status()
    
    # Добавляем дополнительную информацию
    if status.get("is_repo"):
        # Проверяем, можно ли использовать SSH
        if repo_url:
            normalized_url, is_ssh = repo.normalize_url(repo_url, prefer_ssh=True)
            can_use_ssh, ssh_error = repo.can_use_ssh(normalized_url) if is_ssh else (False, None)
            status["ssh_available"] = is_ssh and can_use_ssh
            status["ssh_error"] = ssh_error if not can_use_ssh else None
            status["repo_url"] = repo_url
            status["normalized_url"] = normalized_url
            status["using_ssh"] = is_ssh
    
    return status

@app.post("/api/bots/{bot_id}/update")
async def update_bot_from_git_endpoint(bot_id: int):
    """Обновление бота из Git репозитория"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        bot = get_bot(bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        if not bot.get('git_repo_url'):
            raise HTTPException(status_code=400, detail="Git repository URL not set for this bot")
        
        bot_dir = Path(bot['bot_dir'])
        branch = bot.get('git_branch', 'main')
        repo_url = bot.get('git_repo_url')
        
        # Используем новую систему GitRepository
        repo = GitRepository(bot_dir, repo_url, branch)
        
        if not repo.is_git_installed():
            raise HTTPException(
                status_code=500,
                detail="Git не установлен. Установите Git для работы с репозиториями."
            )
        
        # Если репозиторий не существует, клонируем
        if not repo.is_repo():
            logger.info(f"Репозиторий не найден, выполняю клонирование...")
            success, message = repo.clone(repo_url, branch)
        else:
            logger.info(f"Обновление существующего репозитория...")
            success, message = repo.update(repo_url, branch)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=500, detail=message)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления бота {bot_id} из Git: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка обновления из Git: {str(e)}")

@app.post("/api/bots/{bot_id}/clone")
async def clone_bot_repository(bot_id: int):
    """
    Принудительное клонирование репозитория бота
    Удаляет существующие файлы кроме config.json и клонирует репозиторий заново
    """
    import logging
    import json
    import tempfile
    logger = logging.getLogger(__name__)
    
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    if not bot.get('git_repo_url'):
        raise HTTPException(status_code=400, detail="Git repository URL not set for this bot")
    
    bot_dir = Path(bot['bot_dir'])
    branch = bot.get('git_branch', 'main')
    repo_url = bot.get('git_repo_url')
    config_path = bot_dir / "config.json"
    config_backup = None
    
    try:
        # Сохраняем config.json во временный файл
        if config_path.exists():
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
                config_backup = tmp.name
                shutil.copy2(config_path, config_backup)
                logger.debug(f"Config.json сохранен во временный файл: {config_backup}")
        
        # Используем новую систему GitRepository для клонирования
        logger.info(f"Принудительное клонирование репозитория {repo_url} (ветка: {branch}) в {bot_dir}")
        
        repo = GitRepository(bot_dir, repo_url, branch)
        
        # Проверяем установку Git
        if not repo.is_git_installed():
            raise HTTPException(
                status_code=500, 
                detail="Git не установлен. Установите Git для работы с репозиториями."
            )
        
        # Если репозиторий существует, удаляем .git для чистого клонирования
        if repo.is_repo():
            git_dir = bot_dir / ".git"
            if git_dir.exists():
                logger.info("Удаление существующего Git репозитория...")
                shutil.rmtree(git_dir)
        
        # Удаляем все файлы кроме config.json
        if bot_dir.exists():
            for item in bot_dir.iterdir():
                if item.name not in ['config.json', '.gitkeep']:
                    try:
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
                    except Exception as e:
                        logger.warning(f"Не удалось удалить {item}: {e}")
        
        # Выполняем клонирование (GitRepository автоматически обработает config.json)
        success, message = repo.clone(repo_url, branch)
        
        if not success:
            # Восстанавливаем config.json при ошибке
            if config_backup and os.path.exists(config_backup):
                try:
                    if not config_path.exists():
                        bot_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(config_backup, config_path)
                except Exception as e:
                    logger.error(f"Не удалось восстановить config.json: {e}")
            
            raise HTTPException(status_code=500, detail=message)
        
        # Восстанавливаем config.json после успешного клонирования
        if config_backup and os.path.exists(config_backup):
            try:
                if config_path.exists():
                    # Читаем существующий конфиг из клонированного репозитория
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            new_config = json.load(f)
                    except (json.JSONDecodeError, FileNotFoundError):
                        new_config = {}
                    
                    # Читаем бэкап с нашими настройками
                    with open(config_backup, 'r', encoding='utf-8') as f:
                        existing_config = json.load(f)
                    
                    # Сохраняем важные настройки из бэкапа
                    for key in ['name', 'bot_type', 'start_file', 'cpu_limit', 'memory_limit', 'git_repo_url', 'git_branch']:
                        if key in existing_config:
                            new_config[key] = existing_config[key]
                    
                    # Сохраняем обновленный конфиг
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(new_config, f, ensure_ascii=False, indent=2)
                else:
                    # Если config.json не существует, просто восстанавливаем из бэкапа
                    shutil.copy2(config_backup, config_path)
                
                # Удаляем временный файл
                os.unlink(config_backup)
                logger.info("Config.json успешно восстановлен")
            except Exception as e:
                logger.error(f"Ошибка при восстановлении config.json: {e}")
                # В крайнем случае просто восстанавливаем из бэкапа
                try:
                    if not config_path.exists():
                        shutil.copy2(config_backup, config_path)
                    os.unlink(config_backup)
                except:
                    pass
        
        logger.info(f"Репозиторий успешно клонирован: {message}")
        return {"success": True, "message": message}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка клонирования репозитория для бота {bot_id}: {e}", exc_info=True)
        
        # Восстанавливаем config.json при ошибке
        if config_backup and os.path.exists(config_backup):
            try:
                if not bot_dir.exists():
                    bot_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(config_backup, config_path)
                os.unlink(config_backup)
            except Exception as restore_error:
                logger.error(f"Не удалось восстановить config.json после ошибки: {restore_error}")
        
        error_msg = str(e) if str(e) else "Неизвестная ошибка при клонировании репозитория"
        raise HTTPException(status_code=500, detail=error_msg)

# Panel settings endpoints
@app.get("/api/panel/git-status")
async def get_panel_git_status():
    """Получение статуса Git репозитория панели"""
    try:
        status = get_git_status(BASE_DIR)
        return status
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting panel git status: {str(e)}", exc_info=True)
        return {
            "is_repo": False,
            "error": f"Ошибка при получении статуса Git: {str(e)}",
            "git_not_installed": False
        }

@app.post("/api/panel/update")
async def update_panel():
    """Обновление панели из Git репозитория"""
    success, message = update_panel_from_git()
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=500, detail=message)

class InitGitRepoRequest(BaseModel):
    repo_url: Optional[str] = None

@app.post("/api/panel/init-git")
async def init_panel_git_repo(request: InitGitRepoRequest):
    """Инициализация Git репозитория для панели"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Используем фиксированный URL репозитория панели
        from backend.config import PANEL_REPO_URL
        repo_url = PANEL_REPO_URL
        logger.info(f"Initializing Git repo at {BASE_DIR}, URL: {repo_url}")
        success, message = init_git_repo(BASE_DIR, repo_url)
        logger.info(f"Git init result: success={success}, message={message}")
        
        if success:
            # Проверяем, что репозиторий действительно создан
            from backend.git_manager import is_git_repo
            if is_git_repo(BASE_DIR):
                return {"success": True, "message": message}
            else:
                logger.warning("Git repo initialized but is_git_repo returns False")
                return {"success": True, "message": message + " (требуется проверка)"}
        else:
            logger.error(f"Git init failed: {message}")
            raise HTTPException(status_code=500, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception during Git init: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error initializing Git repository: {str(e)}")

@app.get("/api/panel/ssh-key")
async def get_panel_ssh_key():
    """
    Получение информации о SSH ключе панели
    Включает публичный ключ, тип ключа, и другую информацию
    """
    key_info = get_ssh_key_info()
    
    if not key_info["exists"]:
        # Попытка сгенерировать ключ, если его нет
        success, msg = generate_ssh_key()
        if success:
            setup_ssh_config_for_github()
            key_info = get_ssh_key_info()
        else:
            return {
                "success": False,
                "key_exists": False,
                "error": msg,
                "public_key": None,
                **key_info
            }
    
    return {
        "success": True,
        "key_exists": True,
        "public_key": key_info["public_key"],
        "key_type": key_info["key_type"],
        "key_size": key_info["key_size"],
        "ssh_available": key_info["ssh_available"],
        "ssh_path": key_info["ssh_path"]
    }

@app.post("/api/panel/ssh-key/generate")
async def generate_panel_ssh_key():
    """
    Генерация нового SSH ключа для панели
    Перезаписывает существующий ключ если он есть
    """
    import time
    
    success, message = generate_ssh_key(force=True)
    if success:
        setup_ssh_config_for_github()
        time.sleep(0.1)
        
        # Получаем информацию о новом ключе
        key_info = get_ssh_key_info()
        public_key = key_info.get("public_key")
        
        if not public_key:
            time.sleep(0.2)
            key_info = get_ssh_key_info()
            public_key = key_info.get("public_key")
        
        return {
            "success": True,
            "message": "SSH ключ успешно сгенерирован" if "generated" in message.lower() or "успешно" in message.lower() else message,
            "public_key": public_key,
            "key_type": key_info.get("key_type"),
            "key_size": key_info.get("key_size")
        }
    else:
        raise HTTPException(status_code=500, detail=message)


@app.post("/api/panel/ssh-key/test")
async def test_panel_ssh_connection(host: str = Query(default="github.com")):
    """
    Тестирование SSH подключения к Git хосту
    
    Args:
        host: Хост для тестирования (по умолчанию github.com)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        success, message = test_ssh_connection(host)
        
        if success:
            return {
                "success": True,
                "message": message,
                "host": host
            }
        else:
            raise HTTPException(status_code=500, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing SSH connection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка тестирования SSH: {str(e)}")


@app.get("/api/panel/ssh-key/info")
async def get_panel_ssh_key_info():
    """Получение детальной информации о SSH ключе"""
    key_info = get_ssh_key_info()
    return key_info

@app.post("/api/panel/change-password")
async def change_password(request: Request, password_data: ChangePasswordRequest):
    """Смена пароля администратора"""
    # Проверяем текущий пароль
    if not verify_password(password_data.current_password):
        raise HTTPException(status_code=401, detail="Текущий пароль неверен")
    
    # Проверяем, что новый пароль не пустой
    if not password_data.new_password or len(password_data.new_password.strip()) < 3:
        raise HTTPException(status_code=400, detail="Новый пароль должен содержать минимум 3 символа")
    
    # Устанавливаем новый пароль
    if set_admin_password_hash(password_data.new_password):
        # Обновляем хеш в модуле config для текущей сессии
        import backend.config as config_module
        config_module.ADMIN_PASSWORD_HASH = get_admin_password_hash()
        
        return {"success": True, "message": "Пароль успешно изменен"}
    else:
        raise HTTPException(status_code=500, detail="Ошибка при сохранении нового пароля")

# Инициализация при старте приложения
@app.on_event("startup")
async def startup_event():
    """Восстановление состояния ботов при запуске панели"""
    # Инициализируем базу данных (гарантируем создание таблиц)
    from backend.database import init_database
    init_database()
    
    from backend.bot_manager import restore_bot_states
    restore_bot_states()
    
    # Убеждаемся, что SSH ключ существует при запуске
    if not get_ssh_key_exists():
        generate_ssh_key()
        setup_ssh_config_for_github()
    
    # Автоматически инициализируем Git репозиторий панели, если его нет
    from backend.config import PANEL_REPO_URL, PANEL_REPO_BRANCH
    from backend.git_manager import is_git_repo, init_git_repo, set_git_remote, get_git_remote
    
    if not is_git_repo(BASE_DIR):
        # Пытаемся инициализировать репозиторий
        success, message = init_git_repo(BASE_DIR, PANEL_REPO_URL)
        if success:
            # Проверяем, что remote установлен правильно
            remote = get_git_remote(BASE_DIR)
            if remote != PANEL_REPO_URL:
                set_git_remote(BASE_DIR, PANEL_REPO_URL)

if __name__ == "__main__":
    import uvicorn
    from backend.config import PANEL_HOST, PANEL_PORT
    uvicorn.run(app, host=PANEL_HOST, port=PANEL_PORT)

