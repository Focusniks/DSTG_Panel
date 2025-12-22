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

    // Обновляем статистику
    updateStats(bots);

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
                        
                        ${bot.start_file ? `
                            <div class="bot-card-new-info">
                                <i class="fas fa-file-code"></i>
                                <span>${escapeHtml(bot.start_file)}</span>
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
                        
                        ${bot.status === 'running' ? `
                            <div class="bot-card-new-progress">
                                <div class="progress-label">Использование CPU</div>
                                <div class="progress-bar-wrapper">
                                    <div class="progress-bar-fill" id="cpu-progress-${bot.id}" style="width: 0%"></div>
                                </div>
                            </div>
                        ` : ''}
                    </div>
                    
                    <div class="bot-card-new-footer" onclick="event.stopPropagation()">
                        <button class="bot-card-new-btn btn-manage" onclick="editBot(${bot.id})" title="Управление">
                            <i class="fas fa-cog"></i>
                            <span>Управление</span>
                        </button>
                        ${bot.status === 'running' 
                            ? `<button class="bot-card-new-btn btn-restart" onclick="restartBot(${bot.id})" title="Перезагрузить">
                                 <i class="fas fa-redo"></i>
                                 <span>Перезагрузить</span>
                               </button>
                               <button class="bot-card-new-btn btn-stop" onclick="stopBot(${bot.id})" title="Остановить">
                                 <i class="fas fa-stop"></i>
                                 <span>Остановить</span>
                               </button>`
                            : ['starting', 'restarting', 'installing'].includes(bot.status)
                                ? `<button class="bot-card-new-btn btn-installing" disabled title="${getStatusText(bot.status)}">
                                     <i class="fas fa-spinner fa-spin"></i>
                                     <span>${getStatusText(bot.status)}</span>
                                   </button>`
                                : `<button class="bot-card-new-btn btn-start" onclick="startBot(${bot.id})" title="Запустить">
                                     <i class="fas fa-play"></i>
                                     <span>Запустить</span>
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
    });
    
    // Обновляем статусы ботов периодически (особенно для installing)
    bots.forEach(bot => {
        if (bot.status === 'installing') {
            setTimeout(() => loadBots(), 2000);
        }
    });
}

// Обновление статистики
function updateStats(bots) {
    const statsContainer = document.getElementById('stats-overview');
    if (!statsContainer) return;
    
    const total = bots.length;
    const running = bots.filter(b => b.status === 'running').length;
    const stopped = bots.filter(b => b.status === 'stopped').length;
    const errors = bots.filter(b => b.status === 'error').length;
    
    document.getElementById('total-bots').textContent = total;
    document.getElementById('running-bots').textContent = running;
    document.getElementById('stopped-bots').textContent = stopped;
    document.getElementById('error-bots').textContent = errors;
    
    if (total > 0) {
        statsContainer.style.display = 'block';
    }
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
                cpuEl.textContent = status.cpu_percent.toFixed(1) + '%';
                cpuEl.className = 'stat-value';
                if (status.cpu_percent > 80) {
                    cpuEl.style.color = 'var(--neon-pink)';
                } else if (status.cpu_percent > 50) {
                    cpuEl.style.color = 'var(--neon-orange)';
                } else {
                    cpuEl.style.color = 'var(--neon-cyan)';
                }
                
                // Обновляем прогресс-бар
                const progressBar = document.getElementById(`cpu-progress-${botId}`);
                if (progressBar) {
                    progressBar.style.width = Math.min(status.cpu_percent, 100) + '%';
                }
            } else {
                cpuEl.textContent = '-';
                cpuEl.className = 'stat-value text-muted';
            }
        }
        
        const ramEl = document.getElementById(`ram-${botId}`);
        if (ramEl) {
            if (status.running && status.memory_mb !== null && status.memory_mb !== undefined) {
                ramEl.textContent = Math.round(status.memory_mb) + ' MB';
                ramEl.className = 'stat-value';
                ramEl.style.color = 'var(--neon-cyan)';
            } else {
                ramEl.textContent = '-';
                ramEl.className = 'stat-value text-muted';
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
    
    try {
        const response = await fetch(`${API_BASE}/bots/${botId}/restart`, {
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
            showAlert('Ошибка перезапуска бота: ' + errorMsg, 'danger');
            return;
        }
        
        showAlert('Бот перезагружается...', 'info');
        setTimeout(() => loadBots(), 2000);
    } catch (error) {
        console.error('Restart bot error:', error);
        showAlert('Ошибка перезапуска бота', 'danger');
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
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Обновление метрик для всех запущенных ботов
function startMetricsUpdate() {
    setInterval(async () => {
        const bots = await loadBots();
        bots.forEach(bot => {
            if (bot.status === 'running') {
                loadBotMetrics(bot.id);
            }
        });
    }, 5000);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', async () => {
    if (window.location.pathname !== '/login') {
        const auth = await checkAuth();
        if (!auth) return;
    }
    
    if (document.getElementById('bots-list')) {
        await loadBots();
        startMetricsUpdate();
    }
});
