#!/bin/bash
# Скрипт автоматической установки панели управления ботами на VDS (Linux)
# Полностью автоматическая установка - не требует ручного вмешательства

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Панель управления ботами Discord и Telegram             ║"
echo "║   Автоматическая установка на VDS                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    log_error "Запустите скрипт с правами root: sudo ./install_panel.sh"
    exit 1
fi

# Определяем путь установки
INSTALL_DIR="/opt/bot-panel"
SYSTEM_USER="bot-panel"
CURRENT_DIR=$(pwd)

log_info "Начинаем установку панели управления ботами..."
echo ""

# Шаг 1: Создание пользователя
log_info "Шаг 1/8: Создание системного пользователя..."
if ! id "$SYSTEM_USER" &>/dev/null; then
    useradd -r -s /bin/bash -d "$INSTALL_DIR" -m "$SYSTEM_USER" 2>/dev/null || true
    log_success "Пользователь $SYSTEM_USER создан"
else
    log_success "Пользователь $SYSTEM_USER уже существует"
fi
echo ""

# Шаг 2: Проверка Python
log_info "Шаг 2/8: Проверка Python..."
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 не установлен. Установите Python 3.8 или выше."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    log_error "Требуется Python 3.8 или выше. Установлен: $PYTHON_VERSION"
    exit 1
fi
log_success "Python $PYTHON_VERSION установлен"
echo ""

# Шаг 3: Установка системных зависимостей
log_info "Шаг 3/8: Установка системных зависимостей..."
if command -v apt-get &> /dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq python3-pip python3-venv git openssh-client > /dev/null 2>&1
    log_success "Системные зависимости установлены (Debian/Ubuntu)"
elif command -v yum &> /dev/null; then
    yum install -y -q python3-pip python3-devel git openssh-clients > /dev/null 2>&1
    log_success "Системные зависимости установлены (RHEL/CentOS)"
elif command -v dnf &> /dev/null; then
    dnf install -y -q python3-pip python3-devel git openssh-clients > /dev/null 2>&1
    log_success "Системные зависимости установлены (Fedora)"
else
    log_warning "Не удалось определить менеджер пакетов. Установите вручную:"
    echo "  - python3-pip"
    echo "  - python3-venv (python3-devel на RHEL/CentOS)"
    echo "  - git"
    echo "  - openssh-client"
fi
echo ""

# Шаг 4: Копирование файлов
log_info "Шаг 4/8: Копирование файлов панели..."
if [ -d "$INSTALL_DIR" ]; then
    log_warning "Директория $INSTALL_DIR уже существует"
    read -p "Перезаписать? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_error "Установка отменена"
        exit 1
    fi
    rm -rf "$INSTALL_DIR"
fi

# Копируем файлы
cp -r "$CURRENT_DIR" "$INSTALL_DIR" 2>/dev/null || {
    log_error "Не удалось скопировать файлы. Убедитесь, что у вас есть права на чтение текущей директории."
    exit 1
}

# Удаляем служебные файлы и директории
rm -rf "$INSTALL_DIR/.git" 2>/dev/null || true
rm -rf "$INSTALL_DIR/__pycache__" 2>/dev/null || true
find "$INSTALL_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

chown -R "$SYSTEM_USER:$SYSTEM_USER" "$INSTALL_DIR"
log_success "Файлы скопированы в $INSTALL_DIR"
echo ""

# Шаг 5: Создание виртуального окружения
log_info "Шаг 5/8: Создание виртуального окружения Python..."
sudo -u "$SYSTEM_USER" python3 -m venv "$INSTALL_DIR/venv" 2>/dev/null || {
    log_error "Не удалось создать виртуальное окружение"
    exit 1
}
log_success "Виртуальное окружение создано"
echo ""

# Шаг 6: Установка Python зависимостей
log_info "Шаг 6/8: Установка Python зависимостей (это может занять несколько минут)..."
sudo -u "$SYSTEM_USER" "$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet > /dev/null 2>&1
sudo -u "$SYSTEM_USER" "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet > /dev/null 2>&1 || {
    log_error "Не удалось установить Python зависимости"
    exit 1
}
log_success "Python зависимости установлены"
echo ""

# Шаг 7: Создание директорий и файлов
log_info "Шаг 7/8: Создание необходимых директорий..."
sudo -u "$SYSTEM_USER" mkdir -p "$INSTALL_DIR/bots" "$INSTALL_DIR/data" "$INSTALL_DIR/data/ssh" 2>/dev/null || true
chmod 700 "$INSTALL_DIR/data/ssh" 2>/dev/null || true
log_success "Директории созданы"
echo ""

# Шаг 8: Настройка systemd service
log_info "Шаг 8/8: Настройка systemd service..."
cat > /etc/systemd/system/bot-panel.service << EOF
[Unit]
Description=Bot Panel - Discord and Telegram Bot Management Panel
After=network.target

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

systemctl daemon-reload > /dev/null 2>&1
systemctl enable bot-panel.service > /dev/null 2>&1
log_success "Systemd service создан и включен"
echo ""

# Завершение установки
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              Установка успешно завершена!                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
log_success "Панель установлена в: $INSTALL_DIR"
log_success "Пользователь системы: $SYSTEM_USER"
log_success "Service включен для автозапуска"
echo ""
log_info "Следующие шаги:"
echo ""
echo "1. Запустите панель:"
echo "   ${GREEN}sudo systemctl start bot-panel${NC}"
echo ""
echo "2. Проверьте статус:"
echo "   ${GREEN}sudo systemctl status bot-panel${NC}"
echo ""
echo "3. Просмотр логов:"
echo "   ${GREEN}sudo journalctl -u bot-panel -f${NC}"
echo ""
echo "4. Панель будет доступна по адресу:"
echo "   ${GREEN}http://ваш_IP:8000${NC}"
echo ""
echo "5. Пароль по умолчанию: ${YELLOW}admin${NC}"
echo "   ${YELLOW}⚠ ВАЖНО: Смените пароль после первого входа!${NC}"
echo ""
log_info "Настройка файрвола (если используется UFW):"
echo "   ${GREEN}sudo ufw allow 8000/tcp${NC}"
echo ""
log_info "Для CentOS/RHEL/Fedora (firewalld):"
echo "   ${GREEN}sudo firewall-cmd --permanent --add-port=8000/tcp${NC}"
echo "   ${GREEN}sudo firewall-cmd --reload${NC}"
echo ""
