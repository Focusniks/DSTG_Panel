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

# Шаг 0: Настройка часового пояса
log_info "Шаг 0/9: Настройка часового пояса..."
echo ""
echo "Введите смещение часового пояса относительно UTC (например: +3, -2, +0)"
echo "Популярные значения:"
echo "  +0  - UTC (Лондон)"
echo "  +1  - Центральная Европа (Париж, Берлин)"
echo "  +2  - Восточная Европа (Киев, Хельсинки)"
echo "  +3  - Москва, Минск"
echo "  +4  - Самара"
echo "  +5  - Екатеринбург"
echo "  +6  - Омск"
echo "  +7  - Красноярск"
echo "  +8  - Иркутск"
echo "  +9  - Якутск"
echo "  +10 - Владивосток"
echo "  +11 - Магадан"
echo "  +12 - Камчатка"
echo "  -1  - Азорские острова, Кабо-Верде"
echo "  -2  - Среднеатлантическое время"
echo "  -3  - Бразилия (Сан-Паулу), Аргентина"
echo "  -4  - Атлантическое время (Канада)"
echo "  -5  - Восточное время (Нью-Йорк, Торонто)"
echo "  -6  - Центральное время (Чикаго, Мехико)"
echo "  -7  - Горное время (Денвер, Финикс)"
echo "  -8  - Тихоокеанское время (Лос-Анджелес, Ванкувер)"
echo "  -9  - Аляска"
echo "  -10 - Гавайи"
echo ""
echo "Или введите название часового пояса напрямую (например: Europe/Moscow, America/New_York)"
echo ""
read -p "Смещение или название часового пояса (по умолчанию +0): " timezone_input
timezone_input=${timezone_input:-+0}

# Функция для преобразования смещения в часовой пояс
get_timezone_from_input() {
    local input=$1
    
    # Если введено название часового пояса напрямую (содержит /), используем его
    if [[ "$input" == *"/"* ]]; then
        echo "$input"
        return
    fi
    
    # Иначе обрабатываем как смещение
    case "$input" in
        +0) echo "UTC" ;;
        +1) echo "Europe/Paris" ;;
        +2) echo "Europe/Kiev" ;;
        +3) echo "Europe/Moscow" ;;
        +4) echo "Europe/Samara" ;;
        +5) echo "Asia/Yekaterinburg" ;;
        +6) echo "Asia/Omsk" ;;
        +7) echo "Asia/Krasnoyarsk" ;;
        +8) echo "Asia/Irkutsk" ;;
        +9) echo "Asia/Yakutsk" ;;
        +10) echo "Asia/Vladivostok" ;;
        +11) echo "Asia/Magadan" ;;
        +12) echo "Asia/Kamchatka" ;;
        -1) echo "Atlantic/Azores" ;;
        -2) echo "Atlantic/South_Georgia" ;;
        -3) echo "America/Sao_Paulo" ;;
        -4) echo "America/Halifax" ;;
        -5) echo "America/New_York" ;;
        -6) echo "America/Chicago" ;;
        -7) echo "America/Denver" ;;
        -8) echo "America/Los_Angeles" ;;
        -9) echo "America/Anchorage" ;;
        -10) echo "Pacific/Honolulu" ;;
        *)
            # Проверяем, является ли ввод числовым смещением
            if [[ "$input" =~ ^[+-]?[0-9]+$ ]]; then
                log_warning "Смещение $input не в списке популярных. Ищем подходящий часовой пояс..."
                # Пытаемся найти часовой пояс по смещению через timedatectl
                if command -v timedatectl &> /dev/null; then
                    # Получаем список всех часовых поясов и ищем подходящий
                    # Это упрощенный подход - просто предлагаем ввести название
                    echo ""
                    echo "Для смещения $input доступны следующие часовые пояса (примеры):"
                    if [ "$input" -lt 0 ]; then
                        echo "  America/..."
                        echo "  Atlantic/..."
                        echo "  Pacific/..."
                    else
                        echo "  Europe/..."
                        echo "  Asia/..."
                        echo "  Africa/..."
                    fi
                    echo ""
                    read -p "Введите название часового пояса (например, Europe/London) или нажмите Enter для UTC: " custom_tz
                    if [ -z "$custom_tz" ]; then
                        echo "UTC"
                    else
                        echo "$custom_tz"
                    fi
                else
                    log_warning "Неизвестное смещение: $input"
                    echo ""
                    echo "Доступные часовые пояса (первые 20):"
                    if [ -d "/usr/share/zoneinfo" ]; then
                        find /usr/share/zoneinfo -type f ! -name "*.tab" ! -name "*.list" | head -20 | sed 's|/usr/share/zoneinfo/||'
                        echo "... (всего много, используйте find /usr/share/zoneinfo для полного списка)"
                    fi
                    echo ""
                    read -p "Введите название часового пояса (например, Europe/Moscow) или нажмите Enter для UTC: " custom_tz
                    if [ -z "$custom_tz" ]; then
                        echo "UTC"
                    else
                        echo "$custom_tz"
                    fi
                fi
            else
                log_warning "Неизвестное смещение: $input"
                echo ""
                echo "Доступные часовые пояса (первые 20):"
                if command -v timedatectl &> /dev/null; then
                    timedatectl list-timezones | head -20
                    echo "... (всего много, используйте timedatectl list-timezones для полного списка)"
                elif [ -d "/usr/share/zoneinfo" ]; then
                    find /usr/share/zoneinfo -type f ! -name "*.tab" ! -name "*.list" | head -20 | sed 's|/usr/share/zoneinfo/||'
                    echo "... (всего много, используйте find /usr/share/zoneinfo для полного списка)"
                fi
                echo ""
                read -p "Введите название часового пояса (например, Europe/Moscow) или нажмите Enter для UTC: " custom_tz
                if [ -z "$custom_tz" ]; then
                    echo "UTC"
                else
                    echo "$custom_tz"
                fi
            fi
            ;;
    esac
}

TIMEZONE=$(get_timezone_from_input "$timezone_input")

# Устанавливаем часовой пояс
if command -v timedatectl &> /dev/null; then
    if timedatectl set-timezone "$TIMEZONE" 2>/dev/null; then
        log_success "Часовой пояс установлен: $TIMEZONE"
        timedatectl status | grep "Time zone" || true
    else
        log_warning "Не удалось установить часовой пояс через timedatectl. Попробуем альтернативный метод..."
        # Альтернативный метод для старых систем
        if [ -f "/usr/share/zoneinfo/$TIMEZONE" ]; then
            ln -sf "/usr/share/zoneinfo/$TIMEZONE" /etc/localtime 2>/dev/null || true
            # Обновляем /etc/timezone для Debian/Ubuntu
            if [ -f "/etc/timezone" ]; then
                echo "$TIMEZONE" > /etc/timezone 2>/dev/null || true
            fi
            log_success "Часовой пояс установлен: $TIMEZONE (альтернативный метод)"
        else
            log_warning "Часовой пояс $TIMEZONE не найден. Оставляем текущий."
        fi
    fi
else
    log_warning "timedatectl не найден. Устанавливаем часовой пояс вручную..."
    if [ -f "/usr/share/zoneinfo/$TIMEZONE" ]; then
        ln -sf "/usr/share/zoneinfo/$TIMEZONE" /etc/localtime 2>/dev/null || true
        # Обновляем /etc/timezone для Debian/Ubuntu
        if [ -f "/etc/timezone" ]; then
            echo "$TIMEZONE" > /etc/timezone 2>/dev/null || true
        fi
        log_success "Часовой пояс установлен: $TIMEZONE"
    else
        log_warning "Часовой пояс $TIMEZONE не найден. Оставляем текущий."
        log_info "Проверьте доступные часовые пояса: ls /usr/share/zoneinfo/"
    fi
fi

# Показываем текущее время для проверки
log_info "Текущее системное время:"
date
echo ""

# Шаг 1: Создание пользователя
log_info "Шаг 1/9: Создание системного пользователя..."
if ! id "$SYSTEM_USER" &>/dev/null; then
    useradd -r -s /bin/bash -d "$INSTALL_DIR" -m "$SYSTEM_USER" 2>/dev/null || true
    log_success "Пользователь $SYSTEM_USER создан"
else
    log_success "Пользователь $SYSTEM_USER уже существует"
fi
echo ""

# Шаг 2: Проверка Python
log_info "Шаг 2/9: Проверка Python..."
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

# Шаг 3: Обновление системы и установка системных зависимостей
log_info "Шаг 3/9: Обновление системы и установка системных зависимостей..."
if command -v apt-get &> /dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    log_info "Обновление списка пакетов..."
    apt-get update -qq
    log_info "Обновление установленных пакетов..."
    apt-get upgrade -y -qq > /dev/null 2>&1
    log_info "Установка системных зависимостей..."
    apt-get install -y -qq python3-pip python3-venv git openssh-client curl wget tzdata > /dev/null 2>&1
    log_success "Системные зависимости установлены (Debian/Ubuntu)"
elif command -v yum &> /dev/null; then
    log_info "Обновление системы..."
    yum update -y -q > /dev/null 2>&1
    log_info "Установка системных зависимостей..."
    yum install -y -q python3-pip python3-devel git openssh-clients curl wget tzdata > /dev/null 2>&1
    log_success "Системные зависимости установлены (RHEL/CentOS)"
elif command -v dnf &> /dev/null; then
    log_info "Обновление системы..."
    dnf update -y -q > /dev/null 2>&1
    log_info "Установка системных зависимостей..."
    dnf install -y -q python3-pip python3-devel git openssh-clients curl wget tzdata > /dev/null 2>&1
    log_success "Системные зависимости установлены (Fedora)"
else
    log_warning "Не удалось определить менеджер пакетов. Установите вручную:"
    echo "  - python3-pip"
    echo "  - python3-venv (python3-devel на RHEL/CentOS)"
    echo "  - git"
    echo "  - openssh-client"
    echo "  - curl"
    echo "  - wget"
fi
echo ""

# Шаг 4: Копирование файлов
log_info "Шаг 4/9: Копирование файлов панели..."
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
log_info "Шаг 5/9: Создание виртуального окружения Python..."
sudo -u "$SYSTEM_USER" python3 -m venv "$INSTALL_DIR/venv" 2>/dev/null || {
    log_error "Не удалось создать виртуальное окружение"
    exit 1
}
log_success "Виртуальное окружение создано"
echo ""

# Шаг 6: Установка Python зависимостей
log_info "Шаг 6/9: Установка Python зависимостей (это может занять несколько минут)..."
sudo -u "$SYSTEM_USER" "$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet > /dev/null 2>&1
sudo -u "$SYSTEM_USER" "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet > /dev/null 2>&1 || {
    log_error "Не удалось установить Python зависимости"
    exit 1
}
log_success "Python зависимости установлены"
echo ""

# Шаг 7: Создание директорий и файлов
log_info "Шаг 7/9: Создание необходимых директорий..."
sudo -u "$SYSTEM_USER" mkdir -p "$INSTALL_DIR/bots" "$INSTALL_DIR/data" "$INSTALL_DIR/data/ssh" 2>/dev/null || true
chmod 700 "$INSTALL_DIR/data/ssh" 2>/dev/null || true
log_success "Директории созданы"
echo ""

# Шаг 8: Настройка systemd service
log_info "Шаг 8/9: Настройка systemd service..."
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
