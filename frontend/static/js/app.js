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

// Отрисовка списка ботов в компактном виде (таблица)
function renderBotsList(bots) {
    const container = document.getElementById('bots-list');
    if (!container) return;

    if (bots.length === 0) {
        container.innerHTML = `
            <div class="card">
                <div class="card-body text-center py-5">
                    <i class="fas fa-robot fa-3x text-muted mb-3"></i>
                    <h4 class="text-white mb-3">Боты не созданы</h4>
                    <p class="text-muted">Создайте первого бота, чтобы начать работу</p>
                    <button class="btn btn-primary mt-3" data-bs-toggle="modal" data-bs-target="#createBotModal">
                        <i class="fas fa-plus"></i> Создать бота
                    </button>
                </div>
            </div>
        `;
        return;
    }

    // Компактная таблица ботов
    container.innerHTML = `
        <div class="card">
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover table-dark mb-0">
                        <thead>
                            <tr>
                                <th style="width: 40px;"></th>
                                <th>Название</th>
                                <th style="width: 120px;">Тип</th>
                                <th style="width: 130px;">Статус</th>
                                <th style="width: 100px;">CPU</th>
                                <th style="width: 100px;">RAM</th>
                                <th style="width: 80px;">PID</th>
                                <th style="width: 200px;">Действия</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${bots.map(bot => `
                                <tr>
                                    <td>
                                        <span class="bot-status ${bot.status}"></span>
                                    </td>
                                    <td>
                                        <strong>${escapeHtml(bot.name)}</strong>
                                        ${bot.start_file ? `<br><small class="text-muted">${escapeHtml(bot.start_file)}</small>` : ''}
                                    </td>
                                    <td>
                                        <span class="badge bg-secondary">${bot.bot_type === 'discord' ? 'Discord' : 'Telegram'}</span>
                                    </td>
                                    <td>
                                        ${bot.status === 'running' 
                                            ? '<span class="badge bg-success">Запущен</span>'
                                            : bot.status === 'installing'
                                                ? '<span class="badge bg-warning"><i class="fas fa-spinner fa-spin"></i> Установка</span>'
                                                : bot.status === 'error'
                                                    ? '<span class="badge bg-danger">Ошибка</span>'
                                                    : '<span class="badge bg-secondary">Остановлен</span>'
                                        }
                                    </td>
                                    <td>
                                        <span id="cpu-${bot.id}" class="text-nowrap">-</span>
                                    </td>
                                    <td>
                                        <span id="ram-${bot.id}" class="text-nowrap">-</span>
                                    </td>
                                    <td>
                                        <span class="text-muted">${bot.pid || '-'}</span>
                                    </td>
                                    <td>
                                        <div class="d-flex gap-1 flex-wrap">
                                            <button class="btn btn-sm btn-primary" onclick="editBot(${bot.id})" title="Управление">
                                                <i class="fas fa-cog"></i>
                                            </button>
                                            ${bot.status === 'running' 
                                                ? `<button class="btn btn-sm btn-warning" onclick="stopBot(${bot.id})" title="Остановить">
                                                     <i class="fas fa-stop"></i>
                                                   </button>`
                                                : bot.status === 'installing'
                                                    ? `<button class="btn btn-sm btn-secondary" disabled title="Установка зависимостей">
                                                         <i class="fas fa-spinner fa-spin"></i>
                                                       </button>`
                                                    : `<button class="btn btn-sm btn-success" onclick="startBot(${bot.id})" title="Запустить">
                                                         <i class="fas fa-play"></i>
                                                       </button>`
                                            }
                                            <button class="btn btn-sm btn-danger" onclick="deleteBot(${bot.id})" title="Удалить">
                                                <i class="fas fa-trash"></i>
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
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
            // Периодически проверяем статус ботов в состоянии установки
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
                cpuEl.textContent = status.cpu_percent.toFixed(1) + '%';
            } else {
                cpuEl.textContent = '-';
            }
        }
        
        const ramEl = document.getElementById(`ram-${botId}`);
        if (ramEl) {
            if (status.running && status.memory_mb !== null && status.memory_mb !== undefined) {
                ramEl.textContent = Math.round(status.memory_mb) + ' MB';
            } else {
                ramEl.textContent = '-';
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
