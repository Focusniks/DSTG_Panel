// Главная страница - список ботов

const API_BASE = '/api';

// Проверка авторизации
async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/auth/check`);
        if (response.ok) {
            return true;
        }
        window.location.href = '/login';
        return false;
    } catch (error) {
        window.location.href = '/login';
        return false;
    }
}

// Функция для получения текста статуса
function getStatusText(status) {
    switch (status) {
        case 'running': return 'Запущен';
        case 'starting': return 'Запускается...';
        case 'restarting': return 'Перезагружается...';
        case 'installing': return 'Установка зависимостей...';
        case 'stopped': return 'Остановлен';
        case 'error': return 'Ошибка';
        case 'error_startup': return 'Ошибка запуска';
        default: return 'Неизвестно';
    }
}

// Загрузка списка ботов
async function loadBots() {
    try {
        const response = await fetch(`${API_BASE}/bots`);
        if (!response.ok) throw new Error('Failed to load bots');
        const bots = await response.json();
        renderBotsList(bots);
        return bots;
    } catch (error) {
        console.error('Error loading bots:', error);
        showAlert('Ошибка загрузки ботов', 'danger');
        return [];
    }
}

// Отрисовка списка ботов в виде карточек
function renderBotsList(bots) {
    const container = document.getElementById('bots-list');
    if (!container) return;

    if (bots.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <i class="fas fa-robot"></i>
                </div>
                <h3 class="empty-state-title">Боты не созданы</h3>
                <p class="empty-state-text">Создайте первого бота для Discord или Telegram, чтобы начать работу</p>
                <button class="btn-create-bot-empty" data-bs-toggle="modal" data-bs-target="#createBotModal">
                    <i class="fas fa-plus"></i>
                    <span>Создать первого бота</span>
                </button>
            </div>
        `;
        return;
    }

    // Новый дизайн карточек ботов
    container.innerHTML = `
        <div class="bots-grid-new">
            ${bots.map(bot => `
                <div class="bot-card-new" data-bot-id="${bot.id}" onclick="editBot(${bot.id})">
                    <div class="bot-card-new-header">
                        <div class="bot-card-new-status-indicator ${bot.status}"></div>
                        <div class="bot-card-new-type-badge ${bot.bot_type}">
                            <i class="fab fa-${bot.bot_type === 'discord' ? 'discord' : 'telegram'}"></i>
                        </div>
                    </div>
                    
                    <div class="bot-card-new-body">
                        <h3 class="bot-card-new-title">${escapeHtml(bot.name)}</h3>
                        
                        <div class="bot-card-new-status">
                            <span class="status-indicator-dot ${bot.status}"></span>
                            <span class="status-text">${getStatusText(bot.status || 'stopped')}</span>
                        </div>
                        
                        ${bot.uptime ? `
                            <div class="bot-card-new-info">
                                <i class="fas fa-clock"></i>
                                <span>Работает: ${bot.uptime}</span>
                            </div>
                        ` : ''}
                        
                        ${bot.last_started_at ? `
                            <div class="bot-card-new-info" style="font-size: 0.75rem; color: var(--text-secondary);">
                                <i class="fas fa-play-circle"></i>
                                <span>Запущен: ${formatDate(bot.last_started_at)}</span>
                            </div>
                        ` : ''}
                        
                        ${bot.last_crashed_at ? `
                            <div class="bot-card-new-info" style="font-size: 0.75rem; color: var(--text-danger, #dc3545);">
                                <i class="fas fa-exclamation-triangle"></i>
                                <span>Упал: ${formatDate(bot.last_crashed_at)}</span>
                            </div>
                        ` : ''}
                        
                        <div class="bot-card-new-metrics">
                            <div class="metric-box">
                                <div class="metric-icon">
                                    <i class="fas fa-microchip"></i>
                                </div>
                                <div class="metric-content">
                                    <div class="metric-value" id="cpu-${bot.id}">-</div>
                                    <div class="metric-label">CPU</div>
                                </div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-icon">
                                    <i class="fas fa-memory"></i>
                                </div>
                                <div class="metric-content">
                                    <div class="metric-value" id="ram-${bot.id}">-</div>
                                    <div class="metric-label">RAM</div>
                                </div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-icon">
                                    <i class="fas fa-hashtag"></i>
                                </div>
                                <div class="metric-content">
                                    <div class="metric-value-small">${bot.pid || '-'}</div>
                                    <div class="metric-label">PID</div>
                                </div>
                            </div>
                        </div>
                        
                    </div>
                    
                    <div class="bot-card-new-footer" onclick="event.stopPropagation()">
                        <button class="bot-card-new-btn btn-manage" onclick="editBot(${bot.id})" title="Управление">
                            <i class="fas fa-cog"></i>
                        </button>
                        ${bot.status === 'running' 
                            ? `<button class="bot-card-new-btn btn-restart" onclick="restartBot(${bot.id})" title="Перезагрузить">
                                 <i class="fas fa-redo"></i>
                               </button>
                               <button class="bot-card-new-btn btn-stop" onclick="stopBot(${bot.id})" title="Остановить">
                                 <i class="fas fa-stop"></i>
                               </button>`
                            : ['starting', 'restarting', 'installing'].includes(bot.status)
                                ? `<button class="bot-card-new-btn btn-installing" disabled title="${getStatusText(bot.status)}">
                                     <i class="fas fa-spinner fa-spin"></i>
                                   </button>`
                                : `<button class="bot-card-new-btn btn-start" onclick="startBot(${bot.id})" title="Запустить">
                                     <i class="fas fa-play"></i>
                                   </button>`
                        }
                        <button class="bot-card-new-btn btn-delete" onclick="deleteBot(${bot.id})" title="Удалить">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `).join('')}
        </div>
    `;

    // Загружаем метрики для запущенных ботов
    bots.forEach(bot => {
        if (bot.status === 'running') {
            loadBotMetrics(bot.id);
        }
        // Обновляем кэш статусов
        botStatusCache.set(bot.id, bot.status);
    });
    
    // Обновляем статусы ботов периодически (особенно для installing)
    bots.forEach(bot => {
        if (bot.status === 'installing') {
            setTimeout(() => loadBots(), 2000);
        }
    });
}

// Загрузка метрик бота
async function loadBotMetrics(botId) {
    try {
        const response = await fetch(`${API_BASE}/bots/${botId}/status`);
        if (!response.ok) return;
        const status = await response.json();
        
        const cpuEl = document.getElementById(`cpu-${botId}`);
        if (cpuEl) {
            if (status.running && status.cpu_percent !== null && status.cpu_percent !== undefined) {
                const newValue = status.cpu_percent.toFixed(1) + '%';
                // Плавное обновление только если значение изменилось
                if (cpuEl.textContent !== newValue) {
                    cpuEl.style.transition = 'opacity 0.2s ease';
                    cpuEl.style.opacity = '0.6';
                    setTimeout(() => {
                        cpuEl.textContent = newValue;
                        cpuEl.className = 'metric-value';
                        if (status.cpu_percent > 80) {
                            cpuEl.style.color = 'var(--neon-pink)';
                        } else if (status.cpu_percent > 50) {
                            cpuEl.style.color = 'var(--neon-orange)';
                        } else {
                            cpuEl.style.color = 'var(--neon-cyan)';
                        }
                        cpuEl.style.opacity = '1';
                    }, 100);
                }
            } else {
                if (cpuEl.textContent !== '-') {
                    cpuEl.style.transition = 'opacity 0.2s ease';
                    cpuEl.style.opacity = '0.6';
                    setTimeout(() => {
                        cpuEl.textContent = '-';
                        cpuEl.className = 'metric-value';
                        cpuEl.style.color = '';
                        cpuEl.style.opacity = '1';
                    }, 100);
                }
            }
        }
        
        const ramEl = document.getElementById(`ram-${botId}`);
        if (ramEl) {
            if (status.running && status.memory_mb !== null && status.memory_mb !== undefined) {
                const newValue = Math.round(status.memory_mb) + ' MB';
                // Плавное обновление только если значение изменилось
                if (ramEl.textContent !== newValue) {
                    ramEl.style.transition = 'opacity 0.2s ease';
                    ramEl.style.opacity = '0.6';
                    setTimeout(() => {
                        ramEl.textContent = newValue;
                        ramEl.className = 'metric-value';
                        ramEl.style.color = 'var(--neon-cyan)';
                        ramEl.style.opacity = '1';
                    }, 100);
                }
            } else {
                if (ramEl.textContent !== '-') {
                    ramEl.style.transition = 'opacity 0.2s ease';
                    ramEl.style.opacity = '0.6';
                    setTimeout(() => {
                        ramEl.textContent = '-';
                        ramEl.className = 'metric-value';
                        ramEl.style.color = '';
                        ramEl.style.opacity = '1';
                    }, 100);
                }
            }
        }
        
        // Обновляем PID если он изменился
        const pidEl = document.querySelector(`.bot-card-new[data-bot-id="${botId}"] .metric-value-small`);
        if (pidEl && status.pid) {
            const newPid = status.pid.toString();
            if (pidEl.textContent !== newPid && pidEl.textContent !== '-') {
                pidEl.style.transition = 'opacity 0.2s ease';
                pidEl.style.opacity = '0.6';
                setTimeout(() => {
                    pidEl.textContent = newPid;
                    pidEl.style.opacity = '1';
                }, 100);
            }
        }
    } catch (error) {
        console.error(`Error loading metrics for bot ${botId}:`, error);
    }
}

// Универсальная функция подтверждения
function showConfirm(title, message, onConfirm, confirmBtnClass = 'btn-danger') {
    return new Promise((resolve) => {
        const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
        document.getElementById('confirmModalTitle').textContent = title;
        document.getElementById('confirmModalMessage').textContent = message;
        const confirmBtn = document.getElementById('confirmModalBtn');
        confirmBtn.className = 'btn ' + confirmBtnClass;
        
        const handleConfirm = () => {
            modal.hide();
            confirmBtn.removeEventListener('click', handleConfirm);
            resolve(true);
        };
        
        const handleCancel = () => {
            confirmBtn.removeEventListener('click', handleConfirm);
            resolve(false);
        };
        
        confirmBtn.onclick = handleConfirm;
        document.getElementById('confirmModal').addEventListener('hidden.bs.modal', handleCancel, { once: true });
        
        modal.show();
    });
}

// Перезапуск бота
async function restartBot(botId) {
    const confirmed = await showConfirm('Перезапуск бота', 'Вы уверены, что хотите перезагрузить этого бота?', null, 'btn-info');
    if (!confirmed) return;
    
    // Сразу обновляем статус на "перезагрузка" для визуальной обратной связи
    updateBotStatusOnly(botId, 'restarting');
    showAlert('Перезагрузка бота...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/bots/${botId}/restart`, {
            method: 'POST'
        });
        
        let result;
        try {
            result = await response.json();
        } catch (e) {
            console.error('Error parsing restart response:', e);
            result = {};
        }
        
        if (!response.ok) {
            const errorMsg = result.detail || result.error || `Ошибка ${response.status}: ${response.statusText}`;
            console.error('Restart bot error:', errorMsg);
            updateBotStatusOnly(botId, 'error');
            showAlert('Ошибка перезапуска бота: ' + errorMsg, 'danger');
            return;
        }
        
        if (result.success) {
            showAlert('Бот успешно перезагружается', 'success');
            // Обновляем статус сразу, затем обновим список ботов
            updateBotStatusOnly(botId, 'restarting');
            botStatusCache.set(botId, 'restarting');
            // Обновляем список ботов через небольшую задержку, чтобы сервер успел обновить статус
            setTimeout(() => {
                loadBots();
                // Повторно обновляем через еще немного времени для финального статуса
                setTimeout(() => loadBots(), 3000);
            }, 1000);
        } else {
            const errorMsg = result.error || result.message || 'Неизвестная ошибка';
            updateBotStatusOnly(botId, 'error');
            botStatusCache.set(botId, 'error');
            showAlert('Ошибка перезапуска: ' + errorMsg, 'danger');
        }
    } catch (error) {
        console.error('Restart bot error:', error);
        updateBotStatusOnly(botId, 'error');
        botStatusCache.set(botId, 'error');
        const errorMessage = error.message || 'Ошибка соединения с сервером';
        showAlert('Ошибка перезапуска бота: ' + errorMessage, 'danger');
    }
}

// Запуск бота
async function startBot(botId) {
    const confirmed = await showConfirm('Запуск бота', 'Вы уверены, что хотите запустить этого бота?', null, 'btn-success');
    if (!confirmed) return;
    
    try {
        const response = await fetch(`${API_BASE}/bots/${botId}/start`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            let errorMsg = 'Неизвестная ошибка';
            try {
                const errorData = await response.json();
                errorMsg = errorData.detail || errorData.error || errorMsg;
                
                // Парсим специфичные ошибки
                if (errorMsg.includes('ModuleNotFoundError') || errorMsg.includes('No module named')) {
                    errorMsg = 'Отсутствуют необходимые модули. Проверьте файл requirements.txt и убедитесь, что все зависимости установлены.';
                } else if (errorMsg.includes('FileNotFoundError') || errorMsg.includes('not found')) {
                    errorMsg = 'Не найден стартовый файл. Проверьте путь к файлу в настройках бота.';
                } else if (errorMsg.includes('PermissionError')) {
                    errorMsg = 'Недостаточно прав для запуска бота. Проверьте права доступа к файлам.';
                } else if (errorMsg.includes('ConnectionError') || errorMsg.includes('ConnectError')) {
                    errorMsg = 'Ошибка подключения. Проверьте сетевые настройки и доступность сервисов.';
                }
            } catch (e) {
                errorMsg = 'Ошибка соединения с сервером';
            }
            showAlert('Ошибка запуска бота: ' + errorMsg, 'danger');
            return;
        }
        
        const result = await response.json();
        if (result.success) {
            showAlert('Бот успешно запущен', 'success');
            botStatusCache.set(botId, 'starting');
            setTimeout(() => loadBots(), 1000);
        } else {
            showAlert('Ошибка запуска бота: ' + (result.error || 'Неизвестная ошибка'), 'danger');
        }
    } catch (error) {
        console.error('Error starting bot:', error);
        let errorMsg = 'Неизвестная ошибка';
        if (error.message.includes('fetch')) {
            errorMsg = 'Не удалось подключиться к серверу. Проверьте соединение.';
        } else {
            errorMsg = error.message || 'Произошла ошибка при запуске бота';
        }
        showAlert('Ошибка запуска бота: ' + errorMsg, 'danger');
    }
}

// Остановка бота
async function stopBot(botId) {
    const confirmed = await showConfirm('Остановка бота', 'Вы уверены, что хотите остановить этого бота?', null, 'btn-warning');
    if (!confirmed) return;
    
    try {
        const response = await fetch(`${API_BASE}/bots/${botId}/stop`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            let errorMsg = 'Неизвестная ошибка';
            try {
                const errorData = await response.json();
                errorMsg = errorData.detail || errorData.error || errorMsg;
            } catch (e) {
                errorMsg = 'Ошибка соединения с сервером';
            }
            showAlert('Ошибка остановки бота: ' + errorMsg, 'danger');
            return;
        }
        
        const result = await response.json();
        if (result.success) {
            showAlert('Бот успешно остановлен', 'success');
            botStatusCache.set(botId, 'stopped');
            setTimeout(() => loadBots(), 1000);
        } else {
            showAlert('Ошибка остановки бота: ' + (result.error || 'Неизвестная ошибка'), 'danger');
        }
    } catch (error) {
        console.error('Error stopping bot:', error);
        let errorMsg = 'Неизвестная ошибка';
        if (error.message.includes('fetch')) {
            errorMsg = 'Не удалось подключиться к серверу. Проверьте соединение.';
        } else {
            errorMsg = error.message || 'Произошла ошибка при остановке бота';
        }
        showAlert('Ошибка остановки бота: ' + errorMsg, 'danger');
    }
}

// Удаление бота
async function deleteBot(botId) {
    const confirmed = await showConfirm('Удаление бота', 'Вы уверены, что хотите удалить этого бота? Это действие нельзя отменить. Все файлы и данные бота будут удалены безвозвратно.', null, 'btn-danger');
    if (!confirmed) return;
    
    try {
        const response = await fetch(`${API_BASE}/bots/${botId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            let errorMsg = 'Неизвестная ошибка';
            try {
                const errorData = await response.json();
                errorMsg = errorData.detail || errorData.error || errorMsg;
            } catch (e) {
                errorMsg = 'Ошибка соединения с сервером';
            }
            showAlert('Ошибка удаления бота: ' + errorMsg, 'danger');
            return;
        }
        
        const result = await response.json();
        if (result.success) {
            showAlert('Бот успешно удален', 'success');
            loadBots();
        } else {
            showAlert('Ошибка удаления бота: ' + (result.error || 'Неизвестная ошибка'), 'danger');
        }
    } catch (error) {
        console.error('Error deleting bot:', error);
        let errorMsg = 'Неизвестная ошибка';
        if (error.message.includes('fetch')) {
            errorMsg = 'Не удалось подключиться к серверу. Проверьте соединение.';
        } else {
            errorMsg = error.message || 'Произошла ошибка при удалении бота';
        }
        showAlert('Ошибка удаления бота: ' + errorMsg, 'danger');
    }
}

// Редактирование бота
function editBot(botId) {
    window.location.href = `/bot/${botId}`;
}

// Показ сообщений
function showAlert(message, type) {
    const container = document.getElementById('alerts-container');
    if (!container) {
        const newContainer = document.createElement('div');
        newContainer.id = 'alerts-container';
        newContainer.className = 'mb-3';
        document.querySelector('.container.mt-5').insertBefore(newContainer, document.querySelector('.container.mt-5').firstChild);
    }
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.role = 'alert';
    alert.innerHTML = `
        ${escapeHtml(message)}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    document.getElementById('alerts-container').appendChild(alert);
    
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}

// Экранирование HTML
function formatDate(dateString) {
    if (!dateString) return '';
    try {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (minutes < 1) return 'только что';
        if (minutes < 60) return `${minutes} мин назад`;
        if (hours < 24) return `${hours} ч назад`;
        if (days < 7) return `${days} дн назад`;
        
        // Форматируем дату
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();
        const hoursStr = String(date.getHours()).padStart(2, '0');
        const minutesStr = String(date.getMinutes()).padStart(2, '0');
        return `${day}.${month}.${year} ${hoursStr}:${minutesStr}`;
    } catch (e) {
        return dateString;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Хранилище предыдущих статусов ботов
const botStatusCache = new Map();

// Обновление только метрик без перерисовки карточек
function startMetricsUpdate() {
    setInterval(async () => {
        // Получаем список ботов без перерисовки
        try {
            const response = await fetch(`${API_BASE}/bots`);
            if (!response.ok) return;
            const bots = await response.json();
            
            // Обновляем только метрики для запущенных ботов
            bots.forEach(bot => {
                if (bot.status === 'running') {
                    loadBotMetrics(bot.id);
                    // Обновляем время работы
                    updateBotUptime(bot.id, bot.uptime);
                }
            });
            
            // Обновляем только статусы ботов без перерисовки карточек
            bots.forEach(bot => {
                const previousStatus = botStatusCache.get(bot.id);
                // Обновляем только если статус изменился
                if (previousStatus !== bot.status) {
                    updateBotStatusOnly(bot.id, bot.status);
                    botStatusCache.set(bot.id, bot.status);
                } else {
                    // Обновляем только визуальные индикаторы, но не кнопки
                    updateBotStatusIndicatorsOnly(bot.id, bot.status);
                }
            });
        } catch (error) {
            console.error('Error updating metrics:', error);
        }
    }, 5000);
}

// Обновление времени работы бота
function updateBotUptime(botId, uptime) {
    const botCard = document.querySelector(`.bot-card-new[data-bot-id="${botId}"]`);
    if (!botCard) return;
    
    const uptimeElement = botCard.querySelector('.bot-card-new-info i.fa-clock');
    if (uptimeElement && uptimeElement.parentElement) {
        const span = uptimeElement.parentElement.querySelector('span');
        if (span && uptime) {
            span.textContent = `Работает: ${uptime}`;
        }
    }
}

// Обновление только визуальных индикаторов статуса (без кнопок)
function updateBotStatusIndicatorsOnly(botId, status) {
    const botCard = document.querySelector(`.bot-card-new[data-bot-id="${botId}"]`);
    if (!botCard) return;
    
    // Обновляем индикатор статуса
    const statusIndicator = botCard.querySelector('.bot-card-new-status-indicator');
    if (statusIndicator) {
        statusIndicator.className = `bot-card-new-status-indicator ${status}`;
    }
    
    // Обновляем точку статуса
    const statusDot = botCard.querySelector('.status-indicator-dot');
    if (statusDot) {
        statusDot.className = `status-indicator-dot ${status}`;
    }
}

// Обновление статуса бота с перерисовкой кнопок (только при изменении статуса)
function updateBotStatusOnly(botId, status) {
    const botCard = document.querySelector(`.bot-card-new[data-bot-id="${botId}"]`);
    if (!botCard) return;
    
    // Обновляем индикатор статуса
    const statusIndicator = botCard.querySelector('.bot-card-new-status-indicator');
    if (statusIndicator) {
        statusIndicator.className = `bot-card-new-status-indicator ${status}`;
    }
    
    // Обновляем текст статуса с плавным переходом
    const statusText = botCard.querySelector('.status-text');
    if (statusText) {
        const newStatusText = getStatusText(status || 'stopped');
        if (statusText.textContent !== newStatusText) {
            statusText.style.transition = 'opacity 0.2s ease';
            statusText.style.opacity = '0.6';
            setTimeout(() => {
                statusText.textContent = newStatusText;
                statusText.style.opacity = '1';
            }, 100);
        }
    }
    
    // Обновляем точку статуса
    const statusDot = botCard.querySelector('.status-indicator-dot');
    if (statusDot) {
        statusDot.className = `status-indicator-dot ${status}`;
    }
    
    // Обновляем кнопки в зависимости от статуса
    const footer = botCard.querySelector('.bot-card-new-footer');
    if (!footer) return;
    
    // Проверяем, какие кнопки уже есть
    const existingButtons = footer.querySelectorAll('.bot-card-new-btn:not(.btn-manage):not(.btn-delete)');
    const hasStartBtn = Array.from(existingButtons).some(btn => btn.classList.contains('btn-start'));
    const hasRestartBtn = Array.from(existingButtons).some(btn => btn.classList.contains('btn-restart'));
    const hasStopBtn = Array.from(existingButtons).some(btn => btn.classList.contains('btn-stop'));
    const hasInstallingBtn = Array.from(existingButtons).some(btn => btn.classList.contains('btn-installing'));
    
    // Определяем, какие кнопки должны быть
    let shouldHaveStart = false;
    let shouldHaveRestart = false;
    let shouldHaveStop = false;
    let shouldHaveInstalling = false;
    
    if (status === 'running') {
        shouldHaveRestart = true;
        shouldHaveStop = true;
    } else if (['starting', 'restarting', 'installing'].includes(status)) {
        shouldHaveInstalling = true;
    } else {
        shouldHaveStart = true;
    }
    
    // Проверяем, нужно ли обновлять кнопки
    const needsUpdate = 
        (shouldHaveStart && !hasStartBtn) ||
        (shouldHaveRestart && !hasRestartBtn) ||
        (shouldHaveStop && !hasStopBtn) ||
        (shouldHaveInstalling && !hasInstallingBtn) ||
        (!shouldHaveStart && hasStartBtn) ||
        (!shouldHaveRestart && hasRestartBtn) ||
        (!shouldHaveStop && hasStopBtn) ||
        (!shouldHaveInstalling && hasInstallingBtn);
    
    // Обновляем кнопки только если нужно
    if (needsUpdate) {
        // Сохраняем текущие обработчики событий
        const manageBtn = footer.querySelector('.btn-manage');
        const deleteBtn = footer.querySelector('.btn-delete');
        
        // Удаляем все кнопки кроме manage и delete с плавным исчезновением
        existingButtons.forEach(btn => {
            btn.style.transition = 'opacity 0.2s ease';
            btn.style.opacity = '0';
            setTimeout(() => btn.remove(), 200);
        });
        
        // Добавляем нужные кнопки в зависимости от статуса с плавным появлением
        setTimeout(() => {
            if (status === 'running') {
                const restartBtn = document.createElement('button');
                restartBtn.className = 'bot-card-new-btn btn-restart';
                restartBtn.setAttribute('onclick', `restartBot(${botId})`);
                restartBtn.setAttribute('title', 'Перезагрузить');
                restartBtn.innerHTML = '<i class="fas fa-redo"></i>';
                restartBtn.style.opacity = '0';
                
                const stopBtn = document.createElement('button');
                stopBtn.className = 'bot-card-new-btn btn-stop';
                stopBtn.setAttribute('onclick', `stopBot(${botId})`);
                stopBtn.setAttribute('title', 'Остановить');
                stopBtn.innerHTML = '<i class="fas fa-stop"></i>';
                stopBtn.style.opacity = '0';
                
                if (manageBtn && manageBtn.nextSibling) {
                    footer.insertBefore(restartBtn, manageBtn.nextSibling);
                    footer.insertBefore(stopBtn, restartBtn.nextSibling);
                } else {
                    footer.insertBefore(restartBtn, deleteBtn);
                    footer.insertBefore(stopBtn, restartBtn);
                }
                
                setTimeout(() => {
                    restartBtn.style.transition = 'opacity 0.3s ease';
                    stopBtn.style.transition = 'opacity 0.3s ease';
                    restartBtn.style.opacity = '1';
                    stopBtn.style.opacity = '1';
                }, 50);
            } else if (['starting', 'restarting', 'installing'].includes(status)) {
                const installingBtn = document.createElement('button');
                installingBtn.className = 'bot-card-new-btn btn-installing';
                installingBtn.disabled = true;
                installingBtn.setAttribute('title', getStatusText(status));
                installingBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i>`;
                installingBtn.style.opacity = '0';
                
                if (manageBtn && manageBtn.nextSibling) {
                    footer.insertBefore(installingBtn, manageBtn.nextSibling);
                } else {
                    footer.insertBefore(installingBtn, deleteBtn);
                }
                
                setTimeout(() => {
                    installingBtn.style.transition = 'opacity 0.3s ease';
                    installingBtn.style.opacity = '1';
                }, 50);
            } else {
                const startBtn = document.createElement('button');
                startBtn.className = 'bot-card-new-btn btn-start';
                startBtn.setAttribute('onclick', `startBot(${botId})`);
                startBtn.setAttribute('title', 'Запустить');
                startBtn.innerHTML = '<i class="fas fa-play"></i>';
                startBtn.style.opacity = '0';
                
                if (manageBtn && manageBtn.nextSibling) {
                    footer.insertBefore(startBtn, manageBtn.nextSibling);
                } else {
                    footer.insertBefore(startBtn, deleteBtn);
                }
                
                setTimeout(() => {
                    startBtn.style.transition = 'opacity 0.3s ease';
                    startBtn.style.opacity = '1';
                }, 50);
            }
        }, 200);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', async () => {
    if (window.location.pathname !== '/login') {
        const auth = await checkAuth();
        if (!auth) return;
    }
    
    if (document.getElementById('bots-list')) {
        // Загружаем ботов и инициализируем кэш статусов
        const bots = await loadBots();
        bots.forEach(bot => {
            botStatusCache.set(bot.id, bot.status);
        });
        startMetricsUpdate();
    }
});
