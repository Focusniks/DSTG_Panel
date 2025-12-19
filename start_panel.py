"""
Скрипт запуска панели управления ботами
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from backend.bot_manager import restore_bot_states
from backend.main import app
from backend.config import PANEL_HOST, PANEL_PORT
import uvicorn

if __name__ == "__main__":
    restore_bot_states()
    uvicorn.run(app, host=PANEL_HOST, port=PANEL_PORT)

