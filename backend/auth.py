"""
Система авторизации для панели управления ботами
"""
import bcrypt
from datetime import datetime
from fastapi import HTTPException, Request
from itsdangerous import URLSafeTimedSerializer
from backend.config import SECRET_KEY, SESSION_COOKIE_NAME, SESSION_COOKIE_MAX_AGE, get_admin_password_hash

serializer = URLSafeTimedSerializer(SECRET_KEY)

def verify_password(password: str) -> bool:
    """Проверка пароля"""
    try:
        # Получаем актуальный хеш (на случай, если пароль был изменен)
        current_hash = get_admin_password_hash()
        return bcrypt.checkpw(password.encode(), current_hash.encode())
    except Exception:
        return False

def create_session_token() -> str:
    """Создание токена сессии"""
    data = {
        'timestamp': datetime.utcnow().isoformat(),
        'user': 'admin'
    }
    return serializer.dumps(data)

def verify_session_token(token: str) -> bool:
    """Проверка токена сессии"""
    try:
        serializer.loads(token, max_age=SESSION_COOKIE_MAX_AGE)
        return True
    except Exception:
        return False

def get_session_from_request(request: Request) -> str | None:
    """Получение токена сессии из запроса"""
    # Проверяем cookie
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token and verify_session_token(token):
        return token
    
    # Проверяем заголовок Authorization
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if verify_session_token(token):
            return token
    
    return None

async def require_auth(request: Request) -> bool:
    """Middleware для проверки авторизации"""
    token = get_session_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True


