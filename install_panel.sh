#!/bin/bash
# Скрипт установки панели управления ботами на VDS (Linux)

set -e

echo "=== Установка панели управления ботами Discord и Telegram ==="
echo ""

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "Ошибка: Запустите скрипт с правами root (sudo ./install_panel.sh)"
    exit 1
fi

# Определяем путь установки
INSTALL_DIR="/opt/bot-panel"
SYSTEM_USER="bot-panel"

echo "1. Создание пользователя для панели..."
if ! id "$SYSTEM_USER" &>/dev/null; then
    useradd -r -s /bin/bash -d "$INSTALL_DIR" -m "$SYSTEM_USER"
    echo "✓ Пользователь $SYSTEM_USER создан"
else
    echo "✓ Пользователь $SYSTEM_USER уже существует"
fi

echo ""
echo "2. Проверка Python 3.8+..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo "Ошибка: Требуется Python 3.8 или выше. Установлен: $PYTHON_VERSION"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION установлен"

echo ""
echo "3. Установка системных зависимостей..."
# Обновляем список пакетов
if command -v apt-get &> /dev/null; then
    apt-get update
    apt-get install -y python3-pip python3-venv git mysql-client openssh-client
    echo "✓ Системные зависимости установлены (Debian/Ubuntu)"
elif command -v yum &> /dev/null; then
    yum install -y python3-pip python3-devel git mysql openssh-clients
    echo "✓ Системные зависимости установлены (RHEL/CentOS)"
elif command -v dnf &> /dev/null; then
    dnf install -y python3-pip python3-devel git mysql openssh-clients
    echo "✓ Системные зависимости установлены (Fedora)"
else
    echo "⚠ Предупреждение: Не удалось определить менеджер пакетов. Установите вручную:"
    echo "  - python3-pip"
    echo "  - python3-venv (python3-devel на RHEL/CentOS)"
    echo "  - git"
    echo "  - mysql-client"
    echo "  - openssh-client"
fi

echo ""
echo "4. Копирование файлов панели..."
if [ -d "$INSTALL_DIR" ]; then
    echo "⚠ Директория $INSTALL_DIR уже существует"
    read -p "Перезаписать? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Установка отменена"
        exit 1
    fi
    rm -rf "$INSTALL_DIR"
fi

# Определяем текущую директорию
CURRENT_DIR=$(pwd)

# Копируем файлы
cp -r "$CURRENT_DIR" "$INSTALL_DIR"
chown -R "$SYSTEM_USER:$SYSTEM_USER" "$INSTALL_DIR"
echo "✓ Файлы скопированы в $INSTALL_DIR"

echo ""
echo "5. Создание виртуального окружения Python..."
sudo -u "$SYSTEM_USER" python3 -m venv "$INSTALL_DIR/venv"
echo "✓ Виртуальное окружение создано"

echo ""
echo "6. Установка Python зависимостей..."
sudo -u "$SYSTEM_USER" "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$SYSTEM_USER" "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
echo "✓ Python зависимости установлены"

echo ""
echo "7. Установка systemd service..."
cat > /etc/systemd/system/bot-panel.service << EOF
[Unit]
Description=Bot Panel - Discord and Telegram Bot Management Panel
After=network.target mysql.service

[Service]
Type=simple
User=$SYSTEM_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/start_panel.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable bot-panel.service
echo "✓ Systemd service создан и включен"

echo ""
echo "8. Создание директорий..."
sudo -u "$SYSTEM_USER" mkdir -p "$INSTALL_DIR/bots" "$INSTALL_DIR/data" "$INSTALL_DIR/data/ssh"
chmod 700 "$INSTALL_DIR/data/ssh"
echo "✓ Директории созданы"

echo ""
echo "=== Установка завершена! ==="
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Настройте конфигурацию:"
echo "   nano $INSTALL_DIR/backend/config.py"
echo ""
echo "2. Смените пароль администратора (в веб-интерфейсе после запуска или через):"
echo "   sudo -u $SYSTEM_USER $INSTALL_DIR/venv/bin/python -c \""
echo "   import bcrypt; print(bcrypt.hashpw('ваш_пароль'.encode(), bcrypt.gensalt()).decode())\""
echo ""
echo "3. Запустите панель:"
echo "   systemctl start bot-panel"
echo ""
echo "4. Проверьте статус:"
echo "   systemctl status bot-panel"
echo ""
echo "5. Панель будет доступна по адресу:"
echo "   http://ваш_IP:8000"
echo ""
echo "6. Просмотр логов:"
echo "   journalctl -u bot-panel -f"
echo ""

