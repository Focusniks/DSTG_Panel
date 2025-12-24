// Панель управления ботом - Упрощенная версия

(function() {
    'use strict';
    
    // Глобальные переменные
    let botId = null;
    let codeEditor = null;
    let currentFile = null;
    let updateInterval = null;
    let cpuChart = null;
    let memoryChart = null;
    let currentMetricsPeriod = 24; // По умолчанию 24 часа
    
    // Инициализация при загрузке страницы
    window.addEventListener('DOMContentLoaded', function() {
        init();
    });
    
    function init() {
        // Получаем ID бота из URL
        const path = window.location.pathname;
        const match = path.match(/\/bot\/(\d+)/);
        if (!match || !match[1]) {
            showError('Ошибка', 'Неверный ID бота');
            return;
        }
        
        botId = parseInt(match[1]);
        
        // Настраиваем обработчики событий
        setupEventListeners();
        
        // Загружаем данные бота
        loadBot();
        
        // Инициализируем графики
        initCharts();
        
        // Загружаем метрики
        loadMetrics(currentMetricsPeriod);
        
        // Показываем dashboard по умолчанию
        showSection('dashboard');
    }
    
    function setupEventListeners() {
        // Меню навигации
        document.querySelectorAll('.sidebar-menu-link[data-section]').forEach(function(link) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const section = this.getAttribute('data-section');
                if (section) {
                    showSection(section);
                }
            });
        });
        
        // Кнопки управления ботом
        const startBtn = document.getElementById('start-bot-btn');
        if (startBtn) {
            startBtn.addEventListener('click', handleStartBot);
        }
        
        const stopBtn = document.getElementById('stop-bot-btn');
        if (stopBtn) {
            stopBtn.addEventListener('click', handleStopBot);
        }
        
        const restartBtn = document.getElementById('restart-bot-btn');
        if (restartBtn) {
            restartBtn.addEventListener('click', handleRestartBot);
        }
        
        // Форма настроек
        const settingsForm = document.getElementById('bot-settings-form');
        if (settingsForm) {
            settingsForm.addEventListener('submit', handleSaveSettings);
        }
        
        // Кнопки файлов
        const saveFileBtn = document.getElementById('save-btn');
        if (saveFileBtn) {
            saveFileBtn.addEventListener('click', handleSaveFile);
        }
        
        const createFileBtn = document.getElementById('create-file-btn');
        if (createFileBtn) {
            createFileBtn.addEventListener('click', showCreateFileDialog);
        }
        
        const confirmCreateBtn = document.getElementById('confirm-create-file-btn');
        if (confirmCreateBtn) {
            confirmCreateBtn.addEventListener('click', handleCreateFile);
        }
        
        // Кнопки базы данных
        const createDbBtn = document.getElementById('create-db-btn');
        const newDbNameInput = document.getElementById('new-db-name');
        if (createDbBtn) {
            createDbBtn.addEventListener('click', handleCreateDatabase);
        }
        
        // Обработчики для импорта БД (в модальном окне)
        const importModeRadios = document.querySelectorAll('input[name="import-mode"]');
        importModeRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                const importNewNameGroup = document.getElementById('import-new-name-group');
                const importExistingNameGroup = document.getElementById('import-existing-name-group');
                if (this.value === 'new') {
                    if (importNewNameGroup) importNewNameGroup.style.display = 'block';
                    if (importExistingNameGroup) importExistingNameGroup.style.display = 'none';
                } else {
                    if (importNewNameGroup) importNewNameGroup.style.display = 'none';
                    if (importExistingNameGroup) importExistingNameGroup.style.display = 'block';
                    // Загружаем список БД для выбора
                    updateImportDbSelect();
                }
            });
        });
        
        const importDbBtn = document.getElementById('import-db-btn');
        if (importDbBtn) {
            importDbBtn.addEventListener('click', handleImportDatabase);
        }
        
        // Обработчик открытия модального окна импорта - загружаем список БД если нужно
        const importDatabaseModal = document.getElementById('importDatabaseModal');
        if (importDatabaseModal) {
            importDatabaseModal.addEventListener('show.bs.modal', function() {
                // Если выбран режим "existing", загружаем список БД
                const importModeExisting = document.getElementById('import-mode-existing');
                if (importModeExisting && importModeExisting.checked) {
                    updateImportDbSelect();
                }
            });
            
            // Очистка формы при закрытии модального окна
            importDatabaseModal.addEventListener('hidden.bs.modal', function() {
                const fileInput = document.getElementById('import-db-file');
                if (fileInput) fileInput.value = '';
                const importNewNameInput = document.getElementById('import-new-db-name');
                if (importNewNameInput) importNewNameInput.value = '';
                // Возвращаем к режиму "new"
                const importModeNew = document.getElementById('import-mode-new');
                if (importModeNew) importModeNew.checked = true;
                const importNewNameGroup = document.getElementById('import-new-name-group');
                const importExistingNameGroup = document.getElementById('import-existing-name-group');
                if (importNewNameGroup) importNewNameGroup.style.display = 'block';
                if (importExistingNameGroup) importExistingNameGroup.style.display = 'none';
            });
        }
        
        
        // Кнопка обновления из Git
        const updateGitBtn = document.getElementById('update-git-btn');
        if (updateGitBtn) {
            updateGitBtn.addEventListener('click', handleUpdateFromGit);
        }
        
        // Кнопка клонирования репозитория
        const cloneGitBtn = document.getElementById('clone-git-btn');
        if (cloneGitBtn) {
            cloneGitBtn.addEventListener('click', handleCloneRepository);
        }
        
        // Кнопка тестирования SSH
        const testSshBtn = document.getElementById('test-ssh-btn');
        if (testSshBtn) {
            testSshBtn.addEventListener('click', handleTestSshConnection);
        }
        
        // Кнопки для работы с файлами
        const downloadArchiveBtn = document.getElementById('download-archive-btn');
        if (downloadArchiveBtn) {
            downloadArchiveBtn.addEventListener('click', handleDownloadArchive);
        }
        
        const uploadFileBtn = document.getElementById('upload-file-btn');
        if (uploadFileBtn) {
            uploadFileBtn.addEventListener('click', window.showUploadFileDialog);
        }
        
        const createFolderBtn = document.getElementById('create-folder-btn');
        if (createFolderBtn) {
            createFolderBtn.addEventListener('click', window.showCreateFolderDialog);
        }
        
        const refreshFilesBtn = document.getElementById('refresh-files-btn');
        if (refreshFilesBtn) {
            refreshFilesBtn.addEventListener('click', loadFiles);
        }
        
        const confirmUploadBtn = document.getElementById('confirm-upload-file-btn');
        if (confirmUploadBtn) {
            confirmUploadBtn.addEventListener('click', window.handleUploadFile);
        }
        
        const confirmCreateFolderBtn = document.getElementById('confirm-create-folder-btn');
        if (confirmCreateFolderBtn) {
            confirmCreateFolderBtn.addEventListener('click', window.handleCreateFolder);
        }
        
        // Кнопка удаления файла
        const deleteFileBtn = document.getElementById('delete-file-btn');
        if (deleteFileBtn) {
            deleteFileBtn.addEventListener('click', handleDeleteFile);
        }
        
        // Кнопка скачивания файла
        const downloadFileBtn = document.getElementById('download-file-btn');
        if (downloadFileBtn) {
            downloadFileBtn.addEventListener('click', handleDownloadFile);
        }
        
        // Кнопка переименования файла
        const renameFileBtn = document.getElementById('rename-file-btn');
        if (renameFileBtn) {
            renameFileBtn.addEventListener('click', showRenameFileDialog);
        }
        
        const confirmRenameBtn = document.getElementById('confirm-rename-file-btn');
        if (confirmRenameBtn) {
            confirmRenameBtn.addEventListener('click', handleRenameFile);
        }
        
        // Кнопки для работы с логами
        const refreshLogsBtn = document.getElementById('refresh-logs-btn');
        if (refreshLogsBtn) {
            refreshLogsBtn.addEventListener('click', loadLogs);
        }
        
        const autoRefreshLogsBtn = document.getElementById('auto-refresh-logs-btn');
        if (autoRefreshLogsBtn) {
            autoRefreshLogsBtn.addEventListener('click', toggleLogsAutoRefresh);
        }
    }
    
    // Загрузка данных бота
    async function loadBot() {
        if (!botId) return;
        
        try {
            const response = await fetch('/api/bots/' + botId);
            if (!response.ok) {
                throw new Error('Ошибка загрузки данных бота');
            }
            
            const bot = await response.json();
            updateUI(bot);
            
            // Запускаем обновление статуса
            startStatusUpdate();
            
            // Загружаем Git статус
            loadGitStatus();
            
        } catch (error) {
            console.error('Error loading bot:', error);
            showError('Ошибка загрузки', 'Не удалось загрузить данные бота. См. консоль (F12).', error.message);
        }
    }
    
    // Обновление UI данными бота
    function updateUI(bot) {
        // Sidebar
        const nameEl = document.getElementById('bot-name-sidebar');
        if (nameEl) nameEl.textContent = bot.name || 'Неизвестный бот';
        
        const typeEl = document.getElementById('bot-type-sidebar');
        if (typeEl) {
            typeEl.textContent = bot.bot_type === 'discord' ? 'Discord Bot' : 'Telegram Bot';
        }
        
        // Форма настроек
        const nameInput = document.getElementById('bot-name');
        if (nameInput) nameInput.value = bot.name || '';
        
        const typeSelect = document.getElementById('bot-type');
        if (typeSelect) typeSelect.value = bot.bot_type || 'discord';
        
        const startFileInput = document.getElementById('start-file');
        if (startFileInput) startFileInput.value = bot.start_file || '';
        
        const cpuLimitInput = document.getElementById('cpu-limit');
        if (cpuLimitInput) cpuLimitInput.value = bot.cpu_limit || 50;
        
        const memoryLimitInput = document.getElementById('memory-limit');
        if (memoryLimitInput) memoryLimitInput.value = bot.memory_limit || 512;
        
        // Git репозиторий
        const useGitCheckbox = document.getElementById('use-git');
        const gitFields = document.getElementById('edit-git-fields');
        const gitInfo = document.getElementById('edit-git-info');
        const gitRepoInput = document.getElementById('git-repo-url');
        const gitBranchInput = document.getElementById('git-branch');
        
        if (useGitCheckbox && gitFields) {
            const hasGitRepo = bot.git_repo_url && bot.git_repo_url.trim() !== '';
            useGitCheckbox.checked = hasGitRepo;
            if (hasGitRepo) {
                gitFields.style.display = 'block';
                if (gitInfo) gitInfo.style.display = 'block';
            } else {
                gitFields.style.display = 'none';
                if (gitInfo) gitInfo.style.display = 'none';
            }
        }
        
        if (gitRepoInput) gitRepoInput.value = bot.git_repo_url || '';
        if (gitBranchInput) gitBranchInput.value = bot.git_branch || 'main';
        
        const autoStartCheckbox = document.getElementById('auto-start');
        if (autoStartCheckbox) {
            autoStartCheckbox.checked = bot.auto_start === 1 || bot.auto_start === true;
        }
        
        // Dashboard информация
        const typeInfo = document.getElementById('bot-type-info');
        if (typeInfo) typeInfo.textContent = bot.bot_type === 'discord' ? 'Discord' : 'Telegram';
        
        const startFileInfo = document.getElementById('start-file-info');
        if (startFileInfo) startFileInfo.textContent = bot.start_file || 'Не указан';
        
        const cpuLimitInfo = document.getElementById('cpu-limit-info');
        if (cpuLimitInfo) cpuLimitInfo.textContent = bot.cpu_limit || 50;
        
        const memoryLimitInfo = document.getElementById('memory-limit-info');
        if (memoryLimitInfo) memoryLimitInfo.textContent = bot.memory_limit || 512;
        
        // Информация о времени работы
        if (bot.status === 'running' && bot.started_at) {
            botStartedAt = bot.started_at;
            startUptimeUpdate();
        } else {
            botStartedAt = null;
            if (uptimeUpdateInterval) {
                clearInterval(uptimeUpdateInterval);
                uptimeUpdateInterval = null;
            }
            const uptimeEl = document.getElementById('bot-uptime');
            if (uptimeEl) {
                uptimeEl.textContent = 'Не запущен';
                uptimeEl.style.color = 'var(--text-secondary)';
            }
        }
        
        const lastStartedEl = document.getElementById('bot-last-started');
        if (lastStartedEl) {
            if (bot.last_started_at) {
                lastStartedEl.textContent = formatDate(bot.last_started_at);
            } else {
                lastStartedEl.textContent = 'Никогда';
            }
        }
        
        const lastCrashedEl = document.getElementById('bot-last-crashed');
        if (lastCrashedEl) {
            if (bot.last_crashed_at) {
                lastCrashedEl.textContent = formatDate(bot.last_crashed_at);
            } else {
                lastCrashedEl.textContent = 'Не было';
                lastCrashedEl.style.color = 'var(--text-secondary)';
            }
        }
        
        // Загружаем README если есть
        loadReadme();
    }
    
    // Функция форматирования даты (аналогичная той, что в app.js)
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
    
    // Загрузка и отображение README.md
    async function loadReadme() {
        if (!botId) return;
        
        const readmeSection = document.getElementById('readme-section');
        const readmeContent = document.getElementById('readme-content');
        
        if (!readmeSection || !readmeContent) return;
        
        try {
            // Показываем индикатор загрузки
            readmeContent.innerHTML = '<div class="text-center p-4 text-muted"><i class="fas fa-spinner fa-spin fa-2x mb-3"></i><p>Загрузка README...</p></div>';
            readmeSection.style.display = 'block';
            
            const response = await fetch(`/api/bots/${botId}/file?path=README.md`);
            
            if (!response.ok) {
                if (response.status === 404) {
                    // README не найден, скрываем секцию
                    readmeSection.style.display = 'none';
                    return;
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            const readmeText = result.content || '';
            
            if (!readmeText.trim()) {
                readmeSection.style.display = 'none';
                return;
            }
            
            // Проверяем наличие marked.js
            if (typeof marked === 'undefined') {
                // Если marked.js не загружен, показываем как plain text
                readmeContent.innerHTML = '<pre class="readme-text">' + escapeHtml(readmeText) + '</pre>';
            } else {
                // Рендерим Markdown
                marked.setOptions({
                    breaks: true,
                    gfm: true,
                    headerIds: false,
                    mangle: false
                });
                const html = marked.parse(readmeText);
                readmeContent.innerHTML = html;
            }
            
            // Показываем секцию
            readmeSection.style.display = 'block';
            
        } catch (error) {
            console.error('Ошибка загрузки README:', error);
            // Скрываем секцию при ошибке
            readmeSection.style.display = 'none';
        }
    }
    
    // Переключение секций
    function showSection(sectionName) {
        // Скрываем все секции
        document.querySelectorAll('.content-section').forEach(function(section) {
            section.style.display = 'none';
            section.classList.add('d-none');
        });
        
        // Показываем нужную секцию
        const targetSection = document.getElementById('section-' + sectionName);
        if (targetSection) {
            targetSection.classList.remove('d-none');
            targetSection.style.display = 'block';
        }
        
        // Обновляем активную ссылку в меню
        document.querySelectorAll('.sidebar-menu-link').forEach(function(link) {
            link.classList.remove('active');
            if (link.getAttribute('data-section') === sectionName) {
                link.classList.add('active');
            }
        });
        
        // Загружаем данные для секции
        if (sectionName === 'files') {
            loadFiles();
        } else if (sectionName === 'database') {
            loadDatabase();
        } else if (sectionName === 'logs') {
            loadLogs();
        } else if (sectionName === 'dashboard') {
            // Обновляем графики при переключении на dashboard
            loadMetrics(currentMetricsPeriod);
        }
    }
    
    // Хранилище даты запуска для расчета времени работы
    let botStartedAt = null;
    let uptimeUpdateInterval = null;
    
    // Обновление времени работы каждую секунду
    function startUptimeUpdate() {
        if (uptimeUpdateInterval) {
            clearInterval(uptimeUpdateInterval);
        }
        
        function updateUptime() {
            const uptimeEl = document.getElementById('bot-uptime');
            if (uptimeEl && botStartedAt) {
                const uptime = calculateUptimeClient(botStartedAt);
                if (uptime) {
                    uptimeEl.textContent = uptime;
                    uptimeEl.style.color = 'var(--neon-green, #39ff14)';
                }
            } else if (uptimeEl) {
                uptimeEl.textContent = 'Не запущен';
                uptimeEl.style.color = 'var(--text-secondary)';
            }
        }
        
        updateUptime();
        uptimeUpdateInterval = setInterval(updateUptime, 1000);
    }
    
    // Расчет времени работы на клиенте
    function calculateUptimeClient(startedAt) {
        if (!startedAt) return null;
        try {
            const startTime = new Date(startedAt);
            const now = new Date();
            const delta = now - startTime;
            
            const days = Math.floor(delta / (1000 * 60 * 60 * 24));
            const hours = Math.floor((delta % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((delta % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((delta % (1000 * 60)) / 1000);
            
            if (days > 0) {
                return `${days}д ${hours}ч ${minutes}м`;
            } else if (hours > 0) {
                return `${hours}ч ${minutes}м ${seconds}с`;
            } else if (minutes > 0) {
                return `${minutes}м ${seconds}с`;
            } else {
                return `${seconds}с`;
            }
        } catch (e) {
            return null;
        }
    }
    
    // Запуск обновления статуса
    function startStatusUpdate() {
        if (updateInterval) {
            clearInterval(updateInterval);
        }
        
        updateStatus();
        updateInterval = setInterval(updateStatus, 5000);
        
        // Обновляем графики каждые 30 секунд
        setInterval(() => {
            const dashboardSection = document.getElementById('section-dashboard');
            if (dashboardSection && dashboardSection.style.display !== 'none') {
                loadMetrics(currentMetricsPeriod);
            }
        }, 30000);
    }
    
    // Обновление статуса
    async function updateStatus() {
        if (!botId) return;
        
        try {
            // Получаем полную информацию о боте для обновления времени работы
            const botResponse = await fetch('/api/bots/' + botId);
            if (botResponse.ok) {
                const bot = await botResponse.json();
                // Сохраняем дату запуска для расчета времени работы
                if (bot.status === 'running' && bot.started_at) {
                    botStartedAt = bot.started_at;
                    startUptimeUpdate();
                } else {
                    botStartedAt = null;
                    if (uptimeUpdateInterval) {
                        clearInterval(uptimeUpdateInterval);
                        uptimeUpdateInterval = null;
                    }
                    const uptimeEl = document.getElementById('bot-uptime');
                    if (uptimeEl) {
                        uptimeEl.textContent = 'Не запущен';
                        uptimeEl.style.color = 'var(--text-secondary)';
                    }
                }
            }
            
            const response = await fetch('/api/bots/' + botId + '/status');
            if (!response.ok) return;
            
            const status = await response.json();
            
            // Определяем статус бота из API - используем статус из status
            let botStatus = status.status || 'stopped';
            // Если бот запущен, но статус не установлен, устанавливаем running
            if (status.running && !['starting', 'restarting', 'installing', 'error', 'error_startup'].includes(botStatus)) {
                botStatus = 'running';
            }
            
            // Функция для получения текста статуса
            function getStatusText(status) {
                const statusMap = {
                    'running': 'Запущен',
                    'stopped': 'Остановлен',
                    'starting': 'Запускается...',
                    'restarting': 'Перезагружается...',
                    'installing': 'Установка зависимостей...',
                    'error': 'Ошибка',
                    'error_startup': 'Ошибка запуска'
                };
                return statusMap[status] || 'Неизвестно';
            }
            
            // Статус
            const statusText = document.getElementById('bot-status-text');
            if (statusText) {
                statusText.textContent = getStatusText(botStatus);
            }
            
            const statusIndicator = document.getElementById('bot-status-indicator');
            if (statusIndicator) {
                statusIndicator.className = 'bot-status ' + botStatus;
            }
            
            // Кнопки
            const startBtn = document.getElementById('start-bot-btn');
            const stopBtn = document.getElementById('stop-bot-btn');
            const restartBtn = document.getElementById('restart-bot-btn');
            
            const isBusy = ['starting', 'restarting', 'installing'].includes(botStatus);
            
            if (startBtn) {
                const shouldShow = !status.running && !isBusy;
                const currentDisplay = startBtn.style.display || window.getComputedStyle(startBtn).display;
                const isCurrentlyVisible = currentDisplay !== 'none';
                
                // Меняем только если состояние действительно изменилось
                if (shouldShow !== isCurrentlyVisible) {
                    startBtn.disabled = status.running || isBusy;
                    startBtn.style.display = shouldShow ? 'inline-block' : 'none';
                } else {
                    // Обновляем только disabled, не меняя display
                    startBtn.disabled = status.running || isBusy;
                }
            }
            
            if (restartBtn) {
                const shouldShow = status.running && !isBusy;
                const currentDisplay = restartBtn.style.display || window.getComputedStyle(restartBtn).display;
                const isCurrentlyVisible = currentDisplay !== 'none';
                
                if (shouldShow !== isCurrentlyVisible) {
                    restartBtn.disabled = !status.running || isBusy;
                    restartBtn.style.display = shouldShow ? 'inline-block' : 'none';
                } else {
                    restartBtn.disabled = !status.running || isBusy;
                }
            }
            
            if (stopBtn) {
                const shouldShow = status.running && !isBusy;
                const currentDisplay = stopBtn.style.display || window.getComputedStyle(stopBtn).display;
                const isCurrentlyVisible = currentDisplay !== 'none';
                
                if (shouldShow !== isCurrentlyVisible) {
                    stopBtn.disabled = !status.running || isBusy;
                    stopBtn.style.display = shouldShow ? 'inline-block' : 'none';
                } else {
                    stopBtn.disabled = !status.running || isBusy;
                }
            }
            
            // Метрики
            const cpuEl = document.getElementById('cpu-usage');
            if (cpuEl) {
                if (status.running && status.cpu_percent !== null && status.cpu_percent !== undefined) {
                    cpuEl.textContent = status.cpu_percent.toFixed(1);
                } else {
                    cpuEl.textContent = '-';
                }
            }
            
            const memoryEl = document.getElementById('memory-usage');
            if (memoryEl) {
                if (status.running && status.memory_mb !== null && status.memory_mb !== undefined) {
                    memoryEl.textContent = status.memory_mb.toFixed(1);
                } else {
                    memoryEl.textContent = '-';
                }
            }
            
            const pidEl = document.getElementById('bot-pid');
            if (pidEl) {
                pidEl.textContent = status.pid || '-';
            }
            
        } catch (error) {
            console.error('Error updating status:', error);
        }
    }
    
    // Универсальная функция подтверждения
    function showConfirm(title, message, confirmBtnClass = 'btn-danger') {
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
    
    // Обработчик скачивания архива
    async function handleDownloadArchive() {
        if (!botId) return;
        
        const btn = document.getElementById('download-archive-btn');
        if (!btn) return;
        
        // Сохраняем оригинальный текст и иконку
        const originalHTML = btn.innerHTML;
        
        try {
            // Показываем индикатор загрузки
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Создание архива...';
            
            // Скачиваем архив
            const response = await fetch(`/api/bots/${botId}/download`);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Ошибка скачивания архива' }));
                throw new Error(errorData.detail || 'Ошибка скачивания архива');
            }
            
            // Получаем имя файла из заголовков
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = `bot_${botId}.zip`;
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?(.+?)"?$/);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            }
            
            // Создаем blob и скачиваем
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showSuccess('Архив создан', `Архив "${filename}" успешно скачан`);
        } catch (error) {
            console.error('Error downloading archive:', error);
            showError('Ошибка скачивания', error.message || 'Не удалось скачать архив. См. консоль (F12).');
        } finally {
            // Восстанавливаем кнопку
            btn.disabled = false;
            btn.innerHTML = originalHTML;
        }
    }
    
    // Запуск бота
    async function handleStartBot() {
        if (!botId) {
            showError('Ошибка', 'Не указан ID бота');
            return;
        }
        
        const confirmed = await showConfirm('Запуск бота', 'Вы уверены, что хотите запустить этого бота?', 'btn-success');
        if (!confirmed) return;
        
        const btn = document.getElementById('start-bot-btn');
        if (btn) btn.disabled = true;
        
        try {
            const response = await fetch('/api/bots/' + botId + '/start', {
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
                showError('Ошибка запуска бота: ' + errorMsg);
                return;
            }
            
            const result = await response.json();
            
            if (result.success) {
                showSuccess('Бот запущен', 'Бот успешно запущен');
            } else {
                showError('Ошибка запуска', result.error || 'Неизвестная ошибка', result.error);
            }
        } catch (error) {
            console.error('Start bot error:', error);
            let errorMsg = 'Неизвестная ошибка';
            if (error.message && error.message.includes('fetch')) {
                errorMsg = 'Не удалось подключиться к серверу';
            } else {
                errorMsg = 'Ошибка при запуске';
            }
            showError('Ошибка запуска', errorMsg, error.message || error.toString());
        } finally {
            if (btn) btn.disabled = false;
            setTimeout(updateStatus, 1000);
        }
    }
    
    // Перезагрузка бота
    async function handleRestartBot() {
        if (!botId) {
            showError('Ошибка', 'Не указан ID бота');
            return;
        }
        
        const confirmed = await showConfirm('Перезагрузка бота', 'Вы уверены, что хотите перезагрузить этого бота?', 'btn-info');
        if (!confirmed) return;
        
        const btn = document.getElementById('restart-bot-btn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }
        
        // Обновляем статус сразу для визуальной обратной связи
        const statusText = document.getElementById('bot-status-text');
        const statusIndicator = document.getElementById('bot-status-indicator');
        if (statusText) statusText.textContent = 'Перезагружается...';
        if (statusIndicator) {
            statusIndicator.className = 'bot-status restarting';
            // Не устанавливаем textContent, так как это визуальный индикатор (точка)
        }
        
        try {
            const response = await fetch(`/api/bots/${botId}/restart`, {
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
                showError('Ошибка перезагрузки бота: ' + errorMsg);
                if (statusText) statusText.textContent = 'Ошибка';
                if (statusIndicator) {
                    statusIndicator.className = 'bot-status error';
                }
                return;
            }
            
            if (result.success) {
                showSuccess('Бот перезагружается', 'Бот успешно перезагружается');
                // Обновляем статус через небольшую задержку
                setTimeout(() => {
                    updateStatus();
                    // Повторно обновляем через еще немного времени для финального статуса
                    setTimeout(() => updateStatus(), 3000);
                }, 1000);
            } else {
                const errorMsg = result.error || result.message || 'Неизвестная ошибка';
                showError('Ошибка перезагрузки: ' + errorMsg);
                if (statusText) statusText.textContent = 'Ошибка';
                if (statusIndicator) {
                    statusIndicator.className = 'bot-status error';
                }
            }
        } catch (error) {
            console.error('Restart bot error:', error);
            const errorMessage = error.message || 'Ошибка соединения с сервером';
            showError('Ошибка перезагрузки бота: ' + errorMessage);
            if (statusText) statusText.textContent = 'Ошибка';
            if (statusIndicator) {
                statusIndicator.className = 'bot-status error';
            }
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-redo"></i>';
            }
        }
    }
    
    // Остановка бота
    async function handleStopBot() {
        if (!botId) {
            showError('Ошибка', 'Не указан ID бота');
            return;
        }
        
        const confirmed = await showConfirm('Остановка бота', 'Вы уверены, что хотите остановить этого бота?', 'btn-warning');
        if (!confirmed) return;
        
        const btn = document.getElementById('stop-bot-btn');
        if (btn) btn.disabled = true;
        
        try {
            const response = await fetch('/api/bots/' + botId + '/stop', {
                method: 'POST'
            });
            
            if (!response.ok) {
                let errorMsg = 'Неизвестная ошибка';
                let fullError = null;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.detail || errorData.error || errorMsg;
                    fullError = errorMsg;
                } catch (e) {
                    errorMsg = 'Ошибка соединения с сервером';
                    fullError = e.toString();
                }
                showError('Ошибка остановки', errorMsg, fullError);
                return;
            }
            
            const result = await response.json();
            
            if (result.success) {
                showSuccess('Бот остановлен', 'Бот успешно остановлен');
            } else {
                showError('Ошибка остановки', result.error || 'Неизвестная ошибка', result.error);
            }
        } catch (error) {
            console.error('Stop bot error:', error);
            let errorMsg = 'Неизвестная ошибка';
            if (error.message && error.message.includes('fetch')) {
                errorMsg = 'Не удалось подключиться к серверу';
            } else {
                errorMsg = 'Ошибка при остановке';
            }
            showError('Ошибка остановки', errorMsg, error.message || error.toString());
        } finally {
            if (btn) btn.disabled = false;
            setTimeout(updateStatus, 1000);
        }
    }
    
    // Сохранение настроек
    async function handleSaveSettings(e) {
        e.preventDefault();
        if (!botId) return;
        
        const autoStartCheckbox = document.getElementById('auto-start');
        const formData = {
            name: document.getElementById('bot-name').value,
            start_file: document.getElementById('start-file').value || null,
            cpu_limit: parseFloat(document.getElementById('cpu-limit').value) || 50,
            memory_limit: parseInt(document.getElementById('memory-limit').value) || 512,
            git_repo_url: document.getElementById('use-git').checked ? (document.getElementById('git-repo-url').value || null) : null,
            git_branch: document.getElementById('use-git').checked ? (document.getElementById('git-branch').value || 'main') : 'main',
            auto_start: autoStartCheckbox ? autoStartCheckbox.checked : false
        };
        
        try {
            const response = await fetch('/api/bots/' + botId, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(formData)
            });
            
            if (!response.ok) {
                let errorMsg = 'Неизвестная ошибка';
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.detail || errorData.error || errorMsg;
                } catch (e) {
                    errorMsg = 'Ошибка соединения с сервером';
                }
                showError('Ошибка сохранения', errorMsg, errorMsg);
                return;
            }
            
            const result = await response.json();
            
            if (result.success) {
                showSuccess('Настройки сохранены', 'Настройки успешно сохранены');
                loadBot();
            } else {
                showError('Ошибка сохранения', result.error || 'Неизвестная ошибка', result.error);
            }
        } catch (error) {
            console.error('Save settings error:', error);
            let errorMsg = 'Неизвестная ошибка';
            if (error.message && error.message.includes('fetch')) {
                errorMsg = 'Не удалось подключиться к серверу';
            } else {
                errorMsg = 'Ошибка при сохранении';
            }
            showError('Ошибка сохранения', errorMsg, error.message || error.toString());
        }
    }
    
    // Загрузка файлов
    async function loadFiles() {
        if (!botId) {
            return;
        }
        
        const container = document.getElementById('file-tree');
        if (container) {
            container.innerHTML = '<div class="text-muted">Загрузка файлов...</div>';
        }
        
        try {
            const response = await fetch('/api/bots/' + botId + '/files');
            if (!response.ok) {
                console.error('Failed to load files:', response.status);
                if (container) {
                    container.innerHTML = '<div class="text-danger">Ошибка загрузки файлов</div>';
                }
                return;
            }
            
            const files = await response.json();
            renderFileTree(files);
        } catch (error) {
            console.error('Error loading files:', error);
            const container = document.getElementById('file-tree');
            if (container) {
                container.innerHTML = '<div class="text-danger">Ошибка загрузки файлов: ' + error.message + '</div>';
            }
        }
    }
    
    // Состояние раскрытых папок
    const expandedFolders = new Set();
    
    // Отрисовка дерева файлов
    function renderFileTree(files) {
        const container = document.getElementById('file-tree');
        if (!container) {
            console.error('File tree container not found');
            return;
        }
        
        if (!files || files.length === 0) {
            container.innerHTML = '<div class="text-muted p-3">Файлы не найдены. Создайте файл или загрузите их из Git репозитория.</div>';
            return;
        }
        
        function renderItem(item, level) {
            let html = '';
            const padding = level * 15;
            const isExpanded = expandedFolders.has(item.path);
            
            if (item.type === 'directory') {
                const folderIcon = isExpanded ? 'fa-folder-open' : 'fa-folder';
                const chevronIcon = isExpanded ? 'fa-chevron-down' : 'fa-chevron-right';
                const hasChildren = item.children && item.children.length > 0;
                
                html += '<div class="file-item directory" data-path="' + escapeHtml(item.path) + '" data-type="directory" style="padding-left: ' + padding + 'px; cursor: pointer;">';
                html += '<i class="fas ' + chevronIcon + ' folder-toggle" style="width: 12px; margin-right: 5px; font-size: 0.8em;"></i>';
                html += '<i class="fas ' + folderIcon + '"></i> <span>' + escapeHtml(item.name) + '</span>';
                html += '</div>';
                
                // Содержимое папки (скрыто, если папка свернута)
                if (hasChildren) {
                    html += '<div class="folder-content" data-parent="' + escapeHtml(item.path) + '" style="' + (isExpanded ? '' : 'display: none;') + '">';
                    item.children.forEach(function(child) {
                        html += renderItem(child, level + 1);
                    });
                    html += '</div>';
                }
            } else {
                const filePath = escapeHtml(item.path).replace(/'/g, "\\'");
                html += '<div class="file-item" data-path="' + escapeHtml(item.path) + '" data-type="file" style="padding-left: ' + padding + 'px; cursor: pointer;">';
                html += '<span style="width: 12px; display: inline-block; margin-right: 5px;"></span>'; // Отступ для выравнивания с папками
                html += '<i class="fas fa-file"></i> <span>' + escapeHtml(item.name) + '</span>';
                html += '</div>';
            }
            
            return html;
        }
        
        let html = '';
        try {
            files.forEach(function(file) {
                html += renderItem(file, 0);
            });
            container.innerHTML = html;
            
            // Добавляем обработчики событий для папок и файлов
            // Используем делегирование событий, поэтому обработчики не нужно пересоздавать
            if (!fileTreeClickHandler) {
                setupFileTreeEventListeners();
            }
        } catch (error) {
            console.error('Error rendering file tree:', error);
            container.innerHTML = '<div class="text-danger p-3">Ошибка отображения файлов</div>';
        }
    }
    
    // Настройка обработчиков событий для дерева файлов (используем делегирование событий)
    let fileTreeClickHandler = null;
    
    function setupFileTreeEventListeners() {
        const container = document.getElementById('file-tree');
        if (!container) return;
        
        // Удаляем старый обработчик, если он есть
        if (fileTreeClickHandler) {
            container.removeEventListener('click', fileTreeClickHandler);
        }
        
        // Создаем новый обработчик с делегированием событий
        fileTreeClickHandler = function(e) {
            // Находим ближайший элемент .file-item
            const fileItem = e.target.closest('.file-item');
            if (!fileItem) {
                // Клик вне элементов - снимаем выделение
                clearSelection();
                return;
            }
            
            e.stopPropagation();
            
            const itemPath = fileItem.getAttribute('data-path');
            const itemType = fileItem.getAttribute('data-type');
            
            if (itemType === 'directory') {
                // Обработка папки
                const folderPath = itemPath;
                const folderContent = container.querySelector('.folder-content[data-parent="' + escapeHtml(folderPath).replace(/"/g, '\\"') + '"]');
                
                // Проверяем, не является ли эта папка уже выделенной
                const isCurrentlyActive = fileItem.classList.contains('active');
                
                if (folderContent) {
                    const isExpanded = expandedFolders.has(folderPath);
                    const chevronIcon = fileItem.querySelector('.folder-toggle');
                    const folderIcons = fileItem.querySelectorAll('i.fas');
                    // Вторая иконка - это иконка папки (первая - chevron)
                    const folderIcon = folderIcons.length > 1 ? folderIcons[1] : null;
                    
                    if (isExpanded) {
                        expandedFolders.delete(folderPath);
                        folderContent.style.display = 'none';
                        if (chevronIcon) {
                            chevronIcon.classList.remove('fa-chevron-down');
                            chevronIcon.classList.add('fa-chevron-right');
                        }
                        if (folderIcon) {
                            folderIcon.classList.remove('fa-folder-open');
                            folderIcon.classList.add('fa-folder');
                        }
                    } else {
                        expandedFolders.add(folderPath);
                        folderContent.style.display = '';
                        if (chevronIcon) {
                            chevronIcon.classList.remove('fa-chevron-right');
                            chevronIcon.classList.add('fa-chevron-down');
                        }
                        if (folderIcon) {
                            folderIcon.classList.remove('fa-folder');
                            folderIcon.classList.add('fa-folder-open');
                        }
                    }
                }
                
                // Переключаем выделение: если папка уже выделена, снимаем выделение, иначе выделяем
                if (isCurrentlyActive) {
                    clearSelection();
                } else {
                    selectFileOrFolder(folderPath, 'directory');
                }
            } else if (itemType === 'file') {
                // Обработка файла
                const filePath = itemPath;
                
                // Проверяем, является ли файл базой данных в папке data
                if (isDatabaseFile(filePath)) {
                    const dbName = extractDatabaseName(filePath);
                    if (dbName) {
                        // Перенаправляем на SQL редактор с выбранной БД
                        window.location.href = `/bot/${botId}/sql-editor?db=${encodeURIComponent(dbName)}`;
                        return;
                    }
                }
                
                loadFileInEditor(filePath);
                selectFileOrFolder(filePath, 'file');
            }
        };
        
        // Добавляем обработчик на контейнер (делегирование событий)
        container.addEventListener('click', fileTreeClickHandler);
    }
    
    // Функция для снятия выделения
    function clearSelection() {
        document.querySelectorAll('.file-item.active').forEach(function(item) {
            item.classList.remove('active');
        });
        currentFile = null;
        
        // Скрываем кнопки удаления, скачивания и переименования
        const deleteBtn = document.getElementById('delete-file-btn');
        const downloadBtn = document.getElementById('download-file-btn');
        const renameBtn = document.getElementById('rename-file-btn');
        if (deleteBtn) deleteBtn.style.display = 'none';
        if (downloadBtn) downloadBtn.style.display = 'none';
        if (renameBtn) renameBtn.style.display = 'none';
    }
    
    // Выбор файла или папки
    function selectFileOrFolder(path, type) {
        // Убираем предыдущее выделение
        document.querySelectorAll('.file-item.active').forEach(function(item) {
            item.classList.remove('active');
        });
        
        // Выделяем выбранный элемент
        const selectedItem = document.querySelector('.file-item[data-path="' + escapeHtml(path).replace(/"/g, '\\"') + '"]');
        if (selectedItem) {
            selectedItem.classList.add('active');
        }
        
        // Обновляем текущий выбранный элемент
        if (type === 'file') {
            currentFile = path;
            // Показываем кнопки удаления, скачивания и переименования для файлов
            const deleteBtn = document.getElementById('delete-file-btn');
            const downloadBtn = document.getElementById('download-file-btn');
            const renameBtn = document.getElementById('rename-file-btn');
            if (deleteBtn) deleteBtn.style.display = 'inline-block';
            if (downloadBtn) downloadBtn.style.display = 'inline-block';
            if (renameBtn) renameBtn.style.display = 'inline-block';
        } else {
            // Для папок сохраняем путь в currentFile для удаления
            currentFile = path;
            // Показываем только кнопку удаления для папок
            const deleteBtn = document.getElementById('delete-file-btn');
            const downloadBtn = document.getElementById('download-file-btn');
            const renameBtn = document.getElementById('rename-file-btn');
            if (deleteBtn) deleteBtn.style.display = 'inline-block';
            if (downloadBtn) downloadBtn.style.display = 'none'; // Скачивание только для файлов
            if (renameBtn) renameBtn.style.display = 'none'; // Переименование папок пока не поддерживаем
        }
    }
    
    // Выбор директории для загрузки
    window.selectDirectory = function(dirpath) {
        const currentPathEl = document.getElementById('current-path');
        if (currentPathEl) {
            currentPathEl.textContent = 'Текущая директория: ' + dirpath;
        }
        window.selectedUploadDirectory = dirpath;
    };
    
    // Глобальная переменная для выбранной директории
    window.selectedUploadDirectory = '';
    
    // Выбор директории для загрузки
    window.selectDirectory = function(dirpath) {
        const currentPathEl = document.getElementById('current-path');
        if (currentPathEl) {
            currentPathEl.textContent = 'Текущая директория: ' + dirpath;
        }
        window.selectedUploadDirectory = dirpath;
    };
    
    // Функция для проверки, является ли файл базой данных
    function isDatabaseFile(filepath) {
        const ext = filepath.split('.').pop().toLowerCase();
        const dbExtensions = ['db', 'sqlite', 'sqlite3'];
        return dbExtensions.includes(ext);
    }
    
    // Функция для извлечения имени базы данных из пути (если файл находится в папке data)
    function extractDatabaseName(filepath) {
        // Нормализуем путь (заменяем обратные слеши на прямые)
        const normalizedPath = filepath.replace(/\\/g, '/');
        const pathParts = normalizedPath.split('/');
        
        // Берем имя файла (последняя часть пути)
        const fileName = pathParts[pathParts.length - 1];
        
        // Проверяем, находится ли файл в папке data
        // Ищем папку "data" в пути (не чувствительно к регистру)
        const lowerPath = normalizedPath.toLowerCase();
        if (lowerPath.includes('/data/') || lowerPath.startsWith('data/') || 
            lowerPath.includes('\\data\\') || lowerPath.startsWith('data\\')) {
            return fileName;
        }
        
        // Если файл не в папке data, возвращаем null
        return null;
    }
    
    // Функция для определения типа медиа-файла
    function isMediaFile(filepath) {
        const ext = filepath.split('.').pop().toLowerCase();
        const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico', 
                                 'tiff', 'tif', 'avif', 'apng', 'heic', 'heif', 'jxl'];
        const videoExtensions = ['mp4', 'webm', 'ogg', 'ogv', 'mov', 'avi', 'mkv', 'flv', 'wmv',
                                 'm4v', 'mpeg', 'mpg', '3gp', '3g2', 'f4v', 'ts', 'm2ts', 'asf'];
        const audioExtensions = ['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac', 'wma', 'opus', 'oga', 'webm'];
        return {
            isImage: imageExtensions.includes(ext),
            isVideo: videoExtensions.includes(ext),
            isAudio: audioExtensions.includes(ext),
            isMedia: imageExtensions.includes(ext) || videoExtensions.includes(ext) || audioExtensions.includes(ext)
        };
    }
    
    // Загрузка файла в редактор
    window.loadFileInEditor = async function(filepath) {
        if (!botId) return;
        
        currentFile = filepath;
        
        try {
            // Определяем, является ли файл медиа-файлом
            const mediaInfo = isMediaFile(filepath);
            
            // Для медиа-файлов используем binary=true
            const url = '/api/bots/' + botId + '/file?path=' + encodeURIComponent(filepath) + 
                        (mediaInfo.isMedia ? '&binary=true' : '');
            const response = await fetch(url);
            if (!response.ok) throw new Error('Ошибка загрузки файла');
            
            const data = await response.json();
            
            // Получаем элементы интерфейса
            const editorWrapper = document.getElementById('editor-wrapper');
            const mediaWrapper = document.getElementById('media-wrapper');
            const editorPlaceholder = document.getElementById('editor-placeholder');
            const editorTitle = document.getElementById('editor-title');
            const saveBtn = document.getElementById('save-btn');
            
            // Подсветка активного файла
            document.querySelectorAll('.file-item').forEach(function(item) {
                item.classList.remove('active');
                if (item.getAttribute('data-path') === filepath) {
                    item.classList.add('active');
                }
            });
            
            // Показываем кнопки удаления, скачивания и переименования
            const deleteBtn = document.getElementById('delete-file-btn');
            const downloadBtn = document.getElementById('download-file-btn');
            const renameBtn = document.getElementById('rename-file-btn');
            if (deleteBtn) {
                deleteBtn.style.display = 'inline-block';
                deleteBtn.setAttribute('data-file-path', filepath);
            }
            if (downloadBtn) {
                downloadBtn.style.display = 'inline-block';
            }
            if (renameBtn) {
                renameBtn.style.display = 'inline-block';
            }
            
            // Обработка медиа-файлов (изображения, видео и аудио)
            if (data.binary && (data.is_image || data.is_video || data.is_audio)) {
                // Скрываем редактор кода
                if (editorWrapper) editorWrapper.style.display = 'none';
                if (editorPlaceholder) editorPlaceholder.style.display = 'none';
                if (mediaWrapper) mediaWrapper.style.display = 'block';
                
                // Отключаем кнопку сохранения для медиа-файлов
                if (saveBtn) saveBtn.disabled = true;
                
                const imageContainer = document.getElementById('image-container');
                const videoContainer = document.getElementById('video-container');
                const audioContainer = document.getElementById('audio-container');
                const mediaImage = document.getElementById('media-image');
                const mediaVideo = document.getElementById('media-video');
                const mediaAudio = document.getElementById('media-audio');
                
                // Скрываем все контейнеры сначала
                if (imageContainer) imageContainer.style.display = 'none';
                if (videoContainer) videoContainer.style.display = 'none';
                if (audioContainer) audioContainer.style.display = 'none';
                
                if (data.is_image && imageContainer && mediaImage) {
                    // Показываем изображение
                    imageContainer.style.display = 'block';
                    
                    // Создаем data URL из base64
                    const dataUrl = 'data:' + data.mime_type + ';base64,' + data.content;
                    mediaImage.src = dataUrl;
                    mediaImage.alt = filepath;
                } else if (data.is_video && videoContainer && mediaVideo) {
                    // Показываем видео
                    videoContainer.style.display = 'block';
                    
                    // Создаем blob URL из base64 для видео (более эффективно)
                    const binaryString = atob(data.content);
                    const bytes = new Uint8Array(binaryString.length);
                    for (let i = 0; i < binaryString.length; i++) {
                        bytes[i] = binaryString.charCodeAt(i);
                    }
                    const blob = new Blob([bytes], { type: data.mime_type });
                    const blobUrl = URL.createObjectURL(blob);
                    
                    // Очищаем предыдущий blob URL, если был
                    if (mediaVideo.src && mediaVideo.src.startsWith('blob:')) {
                        URL.revokeObjectURL(mediaVideo.src);
                    }
                    
                    mediaVideo.src = blobUrl;
                    mediaVideo.onloadedmetadata = function() {
                        if (editorTitle) editorTitle.textContent = 'Просмотр: ' + filepath + ' (' + 
                            Math.round(mediaVideo.videoWidth) + 'x' + Math.round(mediaVideo.videoHeight) + ')';
                    };
                } else if (data.is_audio && audioContainer && mediaAudio) {
                    // Показываем аудио
                    audioContainer.style.display = 'block';
                    
                    // Создаем blob URL из base64 для аудио (более эффективно)
                    const binaryString = atob(data.content);
                    const bytes = new Uint8Array(binaryString.length);
                    for (let i = 0; i < binaryString.length; i++) {
                        bytes[i] = binaryString.charCodeAt(i);
                    }
                    const blob = new Blob([bytes], { type: data.mime_type });
                    const blobUrl = URL.createObjectURL(blob);
                    
                    // Очищаем предыдущий blob URL, если был
                    if (mediaAudio.src && mediaAudio.src.startsWith('blob:')) {
                        URL.revokeObjectURL(mediaAudio.src);
                    }
                    
                    mediaAudio.src = blobUrl;
                }
                
                if (editorTitle && !(data.is_video && mediaVideo)) {
                    editorTitle.textContent = 'Просмотр: ' + filepath;
                }
            } else {
                // Обычный текстовый файл - используем CodeMirror
                if (mediaWrapper) mediaWrapper.style.display = 'none';
                if (editorPlaceholder) editorPlaceholder.style.display = 'none';
                if (editorWrapper) editorWrapper.style.display = 'block';
                if (saveBtn) saveBtn.disabled = false;
                
                initEditorIfNeeded();
                if (codeEditor) {
                    codeEditor.setValue(data.content || '');
                    
                    // Определяем режим
                    const ext = filepath.split('.').pop().toLowerCase();
                    const modes = {
                        'py': 'python',
                        'js': 'javascript',
                        'ts': 'typescript',
                        'json': 'javascript',
                        'html': 'htmlmixed',
                        'css': 'css',
                        'md': 'markdown',
                        'sql': 'sql'
                    };
                    codeEditor.setOption('mode', modes[ext] || 'text');
                    
                    // Обновляем редактор после загрузки контента
                    setTimeout(function() {
                        codeEditor.refresh();
                    }, 100);
                }
                
                if (editorTitle) editorTitle.textContent = 'Редактор: ' + filepath;
            }
            
        } catch (error) {
            showError('Ошибка загрузки файла', error.message, error);
        }
    };
    
    // Удаление файла или папки
    async function handleDeleteFile() {
        if (!botId || !currentFile) {
            showWarning('Внимание', 'Файл или папка не выбраны');
            return;
        }
        
        // Определяем тип элемента (сохраняем путь перед удалением)
        const pathToDelete = currentFile;
        const selectedItem = document.querySelector('.file-item.active[data-path="' + escapeHtml(pathToDelete).replace(/"/g, '\\"') + '"]');
        const isDirectory = selectedItem && selectedItem.getAttribute('data-type') === 'directory';
        const itemType = isDirectory ? 'папку' : 'файл';
        const itemTypeCap = isDirectory ? 'Папку' : 'Файл';
        
        const confirmed = await showConfirm(
            'Удаление ' + itemType,
            'Вы уверены, что хотите удалить ' + itemType + ' "' + escapeHtml(pathToDelete) + '"? ' + 
            (isDirectory ? 'Вся папка и её содержимое будут удалены. ' : '') + 
            'Это действие нельзя отменить.',
            'btn-danger'
        );
        if (!confirmed) return;
        
        try {
            const response = await fetch('/api/bots/' + botId + '/file?path=' + encodeURIComponent(pathToDelete), {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                let errorMsg = 'Неизвестная ошибка';
                let fullError = null;
                try {
                    const error = await response.json();
                    errorMsg = error.detail || error.error || 'Ошибка удаления ' + itemType;
                    fullError = errorMsg;
                    
                    // Обработка ошибки занятого файла
                    if (errorMsg.includes('WinError 32') || errorMsg.includes('locked by another process') || 
                        errorMsg.includes('file is locked') || errorMsg.includes('cannot access') ||
                        errorMsg.includes('занят другим процессом')) {
                        errorMsg = 'Файл занят процессом бота. Остановите бота перед удалением.';
                    } else if (errorMsg.includes('PermissionError') || errorMsg.includes('Permission denied') || errorMsg.includes('Access denied')) {
                        errorMsg = 'Недостаточно прав для удаления ' + itemType + '. Проверьте права доступа.';
                    } else if (errorMsg.includes('not found') || errorMsg.includes('не найден')) {
                        errorMsg = itemTypeCap + ' не найден. Возможно, он был уже удален.';
                    }
                } catch (e) {
                    errorMsg = 'Ошибка соединения с сервером';
                    fullError = e.toString();
                }
                showError('Ошибка удаления ' + itemType, errorMsg, fullError);
                return;
            }
            
            showSuccess(itemTypeCap + ' удален' + (isDirectory ? 'а' : ''), itemTypeCap + ' успешно удален' + (isDirectory ? 'а' : ''));
            
            // Очищаем редактор только если удаляли файл
            if (!isDirectory && codeEditor) {
                codeEditor.setValue('');
            }
            
            // Скрываем кнопки удаления, скачивания и переименования
            const deleteBtn = document.getElementById('delete-file-btn');
            const downloadBtn = document.getElementById('download-file-btn');
            const renameBtn = document.getElementById('rename-file-btn');
            if (deleteBtn) deleteBtn.style.display = 'none';
            if (downloadBtn) downloadBtn.style.display = 'none';
            if (renameBtn) renameBtn.style.display = 'none';
            
            const saveBtn = document.getElementById('save-btn');
            if (saveBtn) saveBtn.disabled = true;
            
            // Скрываем редактор/медиа и показываем placeholder только если удаляли файл
            if (!isDirectory) {
                const editorWrapper = document.getElementById('editor-wrapper');
                const mediaWrapper = document.getElementById('media-wrapper');
                const editorPlaceholder = document.getElementById('editor-placeholder');
                const editorTitle = document.getElementById('editor-title');
                
                if (editorWrapper) {
                    editorWrapper.style.display = 'none';
                }
                if (mediaWrapper) {
                    mediaWrapper.style.display = 'none';
                    // Очищаем blob URL для видео и аудио, если они были созданы
                    const mediaVideo = document.getElementById('media-video');
                    const mediaAudio = document.getElementById('media-audio');
                    if (mediaVideo && mediaVideo.src && mediaVideo.src.startsWith('blob:')) {
                        URL.revokeObjectURL(mediaVideo.src);
                        mediaVideo.src = '';
                    }
                    if (mediaAudio && mediaAudio.src && mediaAudio.src.startsWith('blob:')) {
                        URL.revokeObjectURL(mediaAudio.src);
                        mediaAudio.src = '';
                    }
                }
                if (editorPlaceholder) editorPlaceholder.style.display = 'block';
                if (editorTitle) editorTitle.textContent = 'Редактор кода';
            }
            
            // Удаляем папку из списка раскрытых, если она была там
            if (isDirectory && expandedFolders.has(pathToDelete)) {
                expandedFolders.delete(pathToDelete);
            }
            
            currentFile = null;
            
            // Перезагружаем дерево файлов
            loadFiles();
            
        } catch (error) {
            console.error('Delete file error:', error);
            let errorMsg = error.message || 'Неизвестная ошибка';
            if (!error.message || error.message.includes('fetch')) {
                errorMsg = 'Не удалось подключиться к серверу. Проверьте соединение.';
            }
            const selectedItem = document.querySelector('.file-item.active[data-path="' + escapeHtml(pathToDelete || '').replace(/"/g, '\\"') + '"]');
            const isDir = selectedItem && selectedItem.getAttribute('data-type') === 'directory';
            const itemTypeErr = isDir ? 'папки' : 'файла';
            showError('Ошибка удаления', errorMsg, error.toString());
        }
    }
    
    // Инициализация редактора
    function initEditorIfNeeded() {
        if (codeEditor) {
            // Редактор уже инициализирован, просто обновляем его
            return;
        }
        
        if (typeof CodeMirror === 'undefined') {
            console.error('CodeMirror is not loaded');
            return;
        }
        
        const editorEl = document.getElementById('code-editor');
        if (!editorEl) {
            console.error('Editor element not found');
            return;
        }
        
        // Проверяем, не инициализирован ли уже CodeMirror на этом элементе
        if (editorEl.cmInstance) {
            codeEditor = editorEl.cmInstance;
            return;
        }
        
        // CodeMirror сам скроет textarea, поэтому ничего не нужно делать
        
        codeEditor = CodeMirror.fromTextArea(editorEl, {
            lineNumbers: true,
            mode: 'python',
            theme: 'monokai',
            indentUnit: 4,
            lineWrapping: true,
            autoCloseBrackets: true,
            matchBrackets: true,
            indentWithTabs: false,
            tabSize: 4,
            extraKeys: {
                "Ctrl-S": function(cm) {
                    handleSaveFile();
                },
                "Ctrl-F": "findPersistent",
                "Ctrl-H": "replace",
                "Ctrl-/": "toggleComment"
            }
        });
        
        // Сохраняем ссылку на экземпляр
        editorEl.cmInstance = codeEditor;
        
        // Настраиваем размер редактора
        const editorWrapper = document.getElementById('editor-wrapper');
        if (editorWrapper) {
            // Обновляем размер редактора при изменении размера обертки
            const resizeObserver = new ResizeObserver(function() {
                if (codeEditor) {
                    setTimeout(function() {
                        codeEditor.refresh();
                    }, 10);
                }
            });
            resizeObserver.observe(editorWrapper);
        }
        
        // Обновляем размер редактора при изменении размера окна
        let resizeTimeout;
        window.addEventListener('resize', function() {
            if (codeEditor && resizeTimeout) {
                clearTimeout(resizeTimeout);
            }
            resizeTimeout = setTimeout(function() {
                if (codeEditor) {
                    codeEditor.refresh();
                }
            }, 100);
        });
    }
    
    // Скачивание файла
    async function handleDownloadFile() {
        if (!botId || !currentFile) {
            showWarning('Внимание', 'Файл не выбран');
            return;
        }
        
        try {
            // Определяем, что это файл (не папка)
            const selectedItem = document.querySelector('.file-item.active[data-path="' + escapeHtml(currentFile).replace(/"/g, '\\"') + '"]');
            if (!selectedItem || selectedItem.getAttribute('data-type') !== 'file') {
                showWarning('Внимание', 'Выберите файл для скачивания');
                return;
            }
            
            // Создаем ссылку для скачивания
            const downloadUrl = `/api/bots/${botId}/file/download?path=${encodeURIComponent(currentFile)}`;
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = currentFile.split('/').pop() || 'file';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (error) {
            console.error('Error downloading file:', error);
            showError('Ошибка', 'Не удалось скачать файл');
        }
    }
    
    // Сохранение файла
    async function handleSaveFile() {
        if (!botId || !currentFile || !codeEditor) {
            showWarning('Внимание', 'Файл не выбран');
            return;
        }
        
        try {
            const content = codeEditor.getValue();
            const response = await fetch('/api/bots/' + botId + '/file', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: currentFile, content: content})
            });
            
            const result = await response.json();
            
            if (result.success) {
                showSuccess('Файл сохранен', 'Файл успешно сохранен');
            } else {
                showError('Ошибка сохранения', result.error || 'Неизвестная ошибка', result.error);
            }
        } catch (error) {
            console.error('Save file error:', error);
            showError('Ошибка сохранения', 'Не удалось сохранить файл. См. консоль (F12).', error.message);
        }
    }
    
    // Показ диалога создания файла
    function showCreateFileDialog() {
        const modal = new bootstrap.Modal(document.getElementById('createFileModal'));
        modal.show();
    }
    
    // Создание файла
    async function handleCreateFile() {
        if (!botId) return;
        
        const filePath = document.getElementById('new-file-path')?.value.trim() || 
                        document.getElementById('new-file-name')?.value.trim();
        if (!filePath) {
            showWarning('Внимание', 'Введите путь к файлу');
            return;
        }
        
        try {
            const response = await fetch('/api/bots/' + botId + '/file', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: filePath, content: ''})
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ошибка создания файла');
            }
            
            const result = await response.json();
            
            if (result.success) {
                showSuccess('Файл создан', 'Файл успешно создан');
                const modal = bootstrap.Modal.getInstance(document.getElementById('createFileModal'));
                if (modal) modal.hide();
                const pathInput = document.getElementById('new-file-path');
                const nameInput = document.getElementById('new-file-name');
                if (pathInput) pathInput.value = '';
                if (nameInput) nameInput.value = '';
                loadFiles();
            } else {
                showError('Ошибка создания', result.error || 'Неизвестная ошибка', result.error);
            }
        } catch (error) {
            console.error('Create file error:', error);
            showError('Ошибка создания', 'Не удалось создать файл. См. консоль (F12).', error.message);
        }
    }
    
    // Загрузка информации о базе данных
    async function loadDatabase() {
        if (!botId) {
            return;
        }
        
        const container = document.getElementById('databases-list-container');
        if (!container) {
            console.error('Databases list container not found');
            return;
        }
        
        container.innerHTML = '<div class="text-center p-4 text-muted"><i class="fas fa-spinner fa-spin fa-2x mb-3"></i><p>Загрузка баз данных...</p></div>';
        
        try {
            const response = await fetch('/api/bots/' + botId + '/sqlite/databases');
            if (!response.ok) {
                console.error('Failed to load databases:', response.status);
                container.innerHTML = '<div class="database-item-empty"><i class="fas fa-exclamation-triangle"></i><p>Ошибка загрузки списка баз данных</p></div>';
                return;
            }
            
            const result = await response.json();
            const databases = result.databases || [];
            
            // Обновляем список БД в селекторе импорта (если открыт режим existing)
            const importModeExisting = document.getElementById('import-mode-existing');
            if (importModeExisting && importModeExisting.checked) {
                updateImportDbSelect();
            }
            
            if (databases.length === 0) {
                container.innerHTML = '<div class="database-item-empty"><i class="fas fa-database"></i><p>Базы данных не созданы</p><p class="text-muted">Создайте первую базу данных используя форму выше</p></div>';
                return;
            }
            
            let html = '';
            databases.forEach(db => {
                const dbName = escapeHtml(db.db_name);
                html += `
                    <div class="database-item" onclick="selectDatabase('${dbName}')" style="cursor: pointer;">
                        <div class="database-item-header">
                            <div class="database-item-name">
                                <i class="fas fa-database"></i>
                                <span>${dbName}</span>
                            </div>
                            <div class="database-item-actions">
                                <button class="database-item-btn btn-delete" onclick="event.stopPropagation(); deleteDatabase('${dbName}')" title="Удалить базу данных">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                        <div class="database-item-info">
                            <div class="database-item-info-item">
                                <span class="database-item-info-label">
                                    <i class="fas fa-table"></i> Таблиц
                                </span>
                                <span class="database-item-info-value">${db.table_count || 0}</span>
                            </div>
                            <div class="database-item-info-item">
                                <span class="database-item-info-label">
                                    <i class="fas fa-hdd"></i> Размер
                                </span>
                                <span class="database-item-info-value">${db.size_mb || 0} MB</span>
                            </div>
                            ${db.error ? `<div class="database-item-info-item" style="grid-column: 1 / -1;"><span class="text-danger"><i class="fas fa-exclamation-triangle"></i> Ошибка: ${escapeHtml(db.error)}</span></div>` : ''}
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        } catch (error) {
            console.error('Error loading databases:', error);
            container.innerHTML = '<div class="database-item-empty"><i class="fas fa-exclamation-triangle"></i><p>Ошибка загрузки списка баз данных: ' + escapeHtml(error.message) + '</p></div>';
        }
    }
    
    window.selectDatabase = function(dbName) {
        if (!dbName || !botId) return;
        
        // Открываем отдельную страницу SQL редактора с выбранной БД
        window.location.href = `/bot/${botId}/sql-editor?db=${encodeURIComponent(dbName)}`;
    };
    
    window.deleteDatabase = async function(dbName) {
        if (!botId || !dbName) return;
        
        if (!confirm(`Вы уверены, что хотите удалить базу данных "${dbName}"?\n\nЭто действие нельзя отменить!`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/bots/${botId}/sqlite/databases/${encodeURIComponent(dbName)}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                showSuccess('База данных удалена', `База данных "${dbName}" успешно удалена`);
                loadDatabase();
            } else {
                showError('Ошибка удаления', result.error || 'Неизвестная ошибка');
            }
        } catch (error) {
            console.error('Error deleting database:', error);
            showError('Ошибка удаления', 'Не удалось удалить базу данных. См. консоль (F12).', error.message);
        }
    }
    
    // Создание базы данных
    async function handleCreateDatabase() {
        if (!botId) return;
        
        const dbNameInput = document.getElementById('new-db-name');
        const dbName = dbNameInput ? dbNameInput.value.trim() : null;
        
        // Отключаем кнопку на время создания
        const btn = document.getElementById('create-db-btn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Создание...';
        }
        
        try {
            const response = await fetch('/api/bots/' + botId + '/sqlite/databases', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    db_name: dbName || ''
                })
            });
            
            // Проверяем Content-Type перед парсингом JSON
            const contentType = response.headers.get('content-type');
            let result;
            
            if (contentType && contentType.includes('application/json')) {
                result = await response.json();
            } else {
                // Если ответ не JSON, читаем как текст
                const text = await response.text();
                console.error('Non-JSON response from server:', text);
                console.error('Status:', response.status, response.statusText);
                showError('Ошибка создания', 'Сервер вернул не-JSON ответ. Проверьте консоль (F12).', text);
                return;
            }
            
            if (result.success) {
                showSuccess('База данных создана', 'База данных успешно создана');
                // Очищаем поле ввода
                if (dbNameInput) {
                    dbNameInput.value = '';
                }
                loadDatabase();
            } else {
                // Логируем детальную информацию об ошибке
                console.group('%c❌ ОШИБКА СОЗДАНИЯ БАЗЫ ДАННЫХ', 'color: red; font-weight: bold; font-size: 14px;');
                console.error('Ошибка:', result.error);
                console.error('Статус:', response.status);
                if (result.traceback) {
                    console.error('Traceback:', result.traceback);
                }
                console.groupEnd();
                
                showError('Ошибка создания', result.error || 'Неизвестная ошибка', result.traceback || result.error);
            }
        } catch (error) {
            console.group('%c❌ ОШИБКА СОЗДАНИЯ БАЗЫ ДАННЫХ', 'color: red; font-weight: bold; font-size: 14px;');
            console.error('Exception:', error);
            console.error('Message:', error.message);
            console.error('Stack:', error.stack);
            console.groupEnd();
            
            showError('Ошибка создания', 'Не удалось создать базу данных. См. консоль (F12).', error.message);
        } finally {
            // Включаем кнопку обратно
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-plus"></i> Создать';
            }
        }
    }
    
    // Обновление списка БД в селекторе импорта
    async function updateImportDbSelect() {
        if (!botId) return;
        
        const importDbSelect = document.getElementById('import-existing-db-name');
        if (!importDbSelect) return;
        
        try {
            const response = await fetch('/api/bots/' + botId + '/sqlite/databases');
            if (!response.ok) return;
            
            const result = await response.json();
            const databases = result.databases || [];
            
            importDbSelect.innerHTML = '<option value="">Выберите базу данных...</option>';
            databases.forEach(db => {
                const option = document.createElement('option');
                option.value = db.db_name;
                option.textContent = db.db_name;
                importDbSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading databases for import:', error);
        }
    }
    
    // Импорт базы данных
    async function handleImportDatabase() {
        if (!botId) return;
        
        const fileInput = document.getElementById('import-db-file');
        if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            showWarning('Внимание', 'Выберите файл базы данных для импорта');
            return;
        }
        
        const file = fileInput.files[0];
        const importModeRadio = document.querySelector('input[name="import-mode"]:checked');
        const importMode = importModeRadio ? importModeRadio.value : 'new';
        
        let dbName = null;
        if (importMode === 'new') {
            const dbNameInput = document.getElementById('import-new-db-name');
            dbName = dbNameInput ? dbNameInput.value.trim() || null : null;
        } else {
            const dbNameSelect = document.getElementById('import-existing-db-name');
            dbName = dbNameSelect ? dbNameSelect.value || null : null;
            if (!dbName) {
                showWarning('Внимание', 'Выберите базу данных для импорта');
                return;
            }
        }
        
        const btn = document.getElementById('import-db-btn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Импорт...';
        }
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('import_mode', importMode);
            if (dbName) {
                formData.append('db_name', dbName);
            }
            
            const response = await fetch('/api/bots/' + botId + '/sqlite/databases/import', {
                method: 'POST',
                body: formData
            });
            
            const contentType = response.headers.get('content-type');
            let result;
            
            if (contentType && contentType.includes('application/json')) {
                result = await response.json();
            } else {
                const text = await response.text();
                console.error('Non-JSON response from server:', text);
                showError('Ошибка импорта', 'Сервер вернул не-JSON ответ. Проверьте консоль (F12).', text);
                return;
            }
            
            if (result.success) {
                showSuccess('Успех', result.message || 'База данных успешно импортирована');
                
                // Закрываем модальное окно
                const modal = bootstrap.Modal.getInstance(document.getElementById('importDatabaseModal'));
                if (modal) modal.hide();
                
                // Очищаем форму
                if (fileInput) fileInput.value = '';
                const importNewNameInput = document.getElementById('import-new-db-name');
                if (importNewNameInput) importNewNameInput.value = '';
                
                // Обновляем списки БД
                loadDatabase();
            } else {
                showError('Ошибка импорта', result.error || 'Не удалось импортировать базу данных');
            }
        } catch (error) {
            console.error('Error importing database:', error);
            showError('Ошибка импорта', 'Не удалось импортировать базу данных: ' + error.message);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-file-import"></i> Импортировать';
            }
        }
    }
    
    // Загрузка Git статуса
    async function loadGitStatus() {
        if (!botId) return;
        
        try {
            const response = await fetch('/api/bots/' + botId + '/git-status');
            if (!response.ok) return;
            
            const status = await response.json();
            const container = document.getElementById('git-status-info');
            const updateBtn = document.getElementById('update-git-btn');
            const cloneBtn = document.getElementById('clone-git-btn');
            const testSshBtn = document.getElementById('test-ssh-btn');
            
            if (container) {
                if (status.is_repo) {
                    let html = '<div class="alert alert-info">';
                    html += '<div class="d-flex justify-content-between align-items-start mb-2">';
                    html += '<div>';
                    html += '<h6 class="mb-2"><i class="fab fa-github"></i> Git репозиторий</h6>';
                    html += '<p class="mb-1"><strong>URL:</strong> <code>' + escapeHtml(status.remote || status.repo_url || 'Локальный') + '</code></p>';
                    html += '<p class="mb-1"><strong>Ветка:</strong> <span class="badge bg-secondary">' + escapeHtml(status.current_branch || 'N/A') + '</span></p>';
                    
                    if (status.last_commit) {
                        html += '<p class="mb-1"><strong>Последний коммит:</strong> ' + escapeHtml(status.last_commit.hash) + ' - ' + escapeHtml(status.last_commit.message) + '</p>';
                        html += '<p class="mb-1 text-muted"><small>' + escapeHtml(status.last_commit.date) + '</small></p>';
                    }
                    
                    html += '</div>';
                    html += '<div class="text-end">';
                    if (status.using_ssh !== undefined) {
                        if (status.using_ssh) {
                            html += '<span class="badge bg-success mb-2"><i class="fas fa-key"></i> SSH</span><br>';
                        } else {
                            html += '<span class="badge bg-info mb-2"><i class="fas fa-lock"></i> HTTPS</span><br>';
                        }
                    }
                    if (status.ssh_available === false && status.ssh_error) {
                        html += '<span class="badge bg-warning"><i class="fas fa-exclamation-triangle"></i> SSH недоступен</span>';
                    }
                    html += '</div>';
                    html += '</div>';
                    
                    if (status.has_updates) {
                        html += '<div class="alert alert-success mt-2 mb-0">';
                        html += '<i class="fas fa-arrow-down"></i> <strong>Доступны обновления!</strong> Нажмите "Обновить из репозитория"';
                        html += '</div>';
                    } else {
                        html += '<div class="alert alert-success mt-2 mb-0">';
                        html += '<i class="fas fa-check-circle"></i> Репозиторий синхронизирован';
                        html += '</div>';
                    }
                    
                    html += '</div>';
                    container.innerHTML = html;
                    
                    // Показываем кнопки
                    if (updateBtn) updateBtn.style.display = 'inline-block';
                    if (cloneBtn) cloneBtn.style.display = 'none';
                    if (testSshBtn && status.using_ssh) {
                        testSshBtn.style.display = 'inline-block';
                    } else if (testSshBtn) {
                        testSshBtn.style.display = 'none';
                    }
                } else {
                    // Проверяем, указан ли URL репозитория в настройках бота
                    const botInfo = await fetch('/api/bots/' + botId).then(r => r.ok ? r.json() : null).catch(() => null);
                    const repoUrl = botInfo?.git_repo_url || status.repo_url;
                    
                    if (repoUrl) {
                        const normalizedUrl = status.normalized_url || repoUrl;
                        const isSsh = normalizedUrl.startsWith('git@');
                        
                        container.innerHTML = `
                            <div class="alert alert-warning">
                                <h6><i class="fas fa-exclamation-triangle"></i> Git репозиторий не клонирован</h6>
                                <p class="mb-2">Репозиторий указан в настройках, но не клонирован в директорию бота.</p>
                                <p class="mb-2"><strong>URL:</strong> <code>${escapeHtml(repoUrl)}</code></p>
                                ${normalizedUrl !== repoUrl ? `<p class="mb-2 text-muted"><small>Будет использован: <code>${escapeHtml(normalizedUrl)}</code></small></p>` : ''}
                                ${status.ssh_error ? `<div class="alert alert-danger mt-2 mb-0"><i class="fas fa-exclamation-circle"></i> ${escapeHtml(status.ssh_error)}</div>` : ''}
                            </div>
                        `;
                        
                        // Показываем кнопки
                        if (updateBtn) updateBtn.style.display = 'none';
                        if (cloneBtn) cloneBtn.style.display = 'inline-block';
                        if (testSshBtn && isSsh) {
                            testSshBtn.style.display = 'inline-block';
                        } else if (testSshBtn) {
                            testSshBtn.style.display = 'none';
                        }
                    } else {
                        // Показываем сообщение только если чекбокс Git включен
                        const useGitCheckbox = document.getElementById('use-git');
                        if (useGitCheckbox && useGitCheckbox.checked) {
                            container.innerHTML = '<div class="alert alert-secondary"><i class="fas fa-info-circle"></i> Git репозиторий не настроен. Укажите URL репозитория выше.</div>';
                        } else {
                            container.innerHTML = '';
                        }
                        if (updateBtn) updateBtn.style.display = 'none';
                        if (cloneBtn) cloneBtn.style.display = 'none';
                        if (testSshBtn) testSshBtn.style.display = 'none';
                    }
                }
            }
        } catch (error) {
            console.error('Error loading git status:', error);
            const container = document.getElementById('git-status-info');
            if (container) {
                container.innerHTML = '<div class="alert alert-danger">Ошибка загрузки статуса Git репозитория</div>';
            }
        }
    }
    
    // Клонирование репозитория
    async function handleCloneRepository() {
        if (!botId) return;
        
        const confirmed = await showConfirm(
            'Клонирование репозитория',
            'Клонировать репозиторий? Все файлы в директории бота (кроме config.json) будут заменены файлами из репозитория.',
            'btn-warning'
        );
        if (!confirmed) {
            return;
        }
        
        const container = document.getElementById('git-status-info');
        const cloneBtn = document.getElementById('clone-git-btn');
        
        if (container) {
            container.innerHTML = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> Клонирование репозитория...</div>';
        }
        if (cloneBtn) cloneBtn.disabled = true;
        
        try {
            // Получаем информацию о боте
            const botResponse = await fetch('/api/bots/' + botId);
            if (!botResponse.ok) {
                throw new Error('Не удалось получить информацию о боте');
            }
            const bot = await botResponse.json();
            
            if (!bot.git_repo_url) {
                showError('Ошибка', 'URL репозитория не указан в настройках бота');
                loadGitStatus();
                return;
            }
            
            // Используем endpoint клонирования
            const response = await fetch('/api/bots/' + botId + '/clone', {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    showSuccess('Репозиторий клонирован', result.message || 'Репозиторий успешно клонирован в директорию бота');
                    // Перезагружаем файлы и статус
                    setTimeout(() => {
                        loadGitStatus();
                        if (window.loadFiles) loadFiles();
                    }, 1000);
                } else {
                    showError('Ошибка клонирования', result.message || 'Не удалось клонировать репозиторий');
                    loadGitStatus();
                }
            } else {
                let errorDetail = 'Неизвестная ошибка';
                try {
                    const error = await response.json();
                    errorDetail = error.detail || error.message || errorDetail;
                    console.error('Clone error response:', error);
                } catch (e) {
                    errorDetail = `HTTP ${response.status}: ${response.statusText}`;
                    console.error('Failed to parse error response:', e);
                }
                showError('Ошибка клонирования', errorDetail);
                loadGitStatus();
            }
        } catch (error) {
            console.error('Error cloning repository:', error);
            showError('Ошибка клонирования', error.message || 'Неизвестная ошибка');
            loadGitStatus();
        } finally {
            if (cloneBtn) cloneBtn.disabled = false;
        }
    }
    
    // Экспортируем для глобального доступа
    window.handleCloneRepository = handleCloneRepository;
    
    // Тестирование SSH подключения
    async function handleTestSshConnection() {
        if (!botId) return;
        
        const testBtn = document.getElementById('test-ssh-btn');
        if (testBtn) testBtn.disabled = true;
        
        try {
            // Получаем информацию о боте для определения хоста
            const botResponse = await fetch('/api/bots/' + botId);
            if (!botResponse.ok) {
                throw new Error('Не удалось получить информацию о боте');
            }
            const bot = await botResponse.json();
            
            if (!bot.git_repo_url) {
                showError('Ошибка', 'URL репозитория не указан');
                if (testBtn) testBtn.disabled = false;
                return;
            }
            
            // Извлекаем хост из URL
            let host = 'github.com';
            if (bot.git_repo_url.includes('github.com')) {
                host = 'github.com';
            } else if (bot.git_repo_url.includes('gitlab.com')) {
                host = 'gitlab.com';
            } else if (bot.git_repo_url.includes('bitbucket.org')) {
                host = 'bitbucket.org';
            }
            
            // Тестируем SSH подключение
            const response = await fetch(`/api/panel/ssh-key/test?host=${encodeURIComponent(host)}`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    showSuccess('SSH подключение успешно', result.message || `SSH подключение к ${host} работает корректно`);
                } else {
                    showError('Ошибка SSH подключения', result.message || 'Не удалось подключиться через SSH');
                }
            } else {
                const error = await response.json().catch(() => ({ detail: 'Неизвестная ошибка' }));
                showError('Ошибка SSH подключения', error.detail || 'Не удалось протестировать SSH подключение');
            }
        } catch (error) {
            console.error('Error testing SSH connection:', error);
            showError('Ошибка тестирования SSH', error.message || 'Неизвестная ошибка');
        } finally {
            if (testBtn) testBtn.disabled = false;
        }
    }
    
    // Обновление из Git
    async function handleUpdateFromGit() {
        if (!botId) return;
        
        const confirmed = await showConfirm(
            'Обновление из репозитория',
            'Обновить бота из Git репозитория? Локальные изменения будут сохранены (stash).',
            'btn-primary'
        );
        if (!confirmed) return;
        
        const btn = document.getElementById('update-git-btn');
        const container = document.getElementById('git-status-info');
        
        if (btn) btn.disabled = true;
        if (container) {
            container.innerHTML = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> Обновление из репозитория...</div>';
        }
        
        try {
            const response = await fetch('/api/bots/' + botId + '/update', {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    showSuccess('Бот обновлен', result.message || 'Бот успешно обновлен из репозитория');
                    // Перезагружаем файлы и статус
                    setTimeout(() => {
                        loadGitStatus();
                        if (window.loadFiles) loadFiles();
                    }, 1000);
                } else {
                    showError('Ошибка обновления', result.message || result.error || 'Неизвестная ошибка');
                    loadGitStatus();
                }
            } else {
                const error = await response.json().catch(() => ({ detail: 'Неизвестная ошибка' }));
                showError('Ошибка обновления', error.detail || error.message || 'Не удалось обновить бота');
                loadGitStatus();
            }
        } catch (error) {
            console.error('Update bot error:', error);
            showError('Ошибка обновления', 'Не удалось обновить бота. См. консоль (F12).', error.message);
            loadGitStatus();
        } finally {
            if (btn) btn.disabled = false;
        }
    }
    
    // Загрузка логов
    let logsAutoRefresh = false;
    let logsInterval = null;
    
    async function loadLogs() {
        if (!botId) return;
        
        const container = document.getElementById('bot-logs');
        if (!container) return;
        
        try {
            const response = await fetch(`/api/bots/${botId}/logs?lines=1000`);
            if (!response.ok) {
                container.innerHTML = '<div class="text-danger p-3">Ошибка загрузки логов</div>';
                return;
            }
            
            const data = await response.json();
            
            if (!data.logs || data.logs.length === 0) {
                container.innerHTML = '<div class="text-center p-5 text-muted"><i class="fas fa-info-circle fa-2x mb-3"></i><p>Логи пусты</p></div>';
                return;
            }
            
            let html = '';
            data.logs.forEach((line, index) => {
                if (!line) return;
                
                // Парсинг строки лога
                const parsed = parseLogLine(line);
                
                let className = 'log-line ' + parsed.type;
                let icon = parsed.icon;
                let timestamp = parsed.timestamp;
                let content = parsed.content;
                
                html += `<div class="${className}" data-line="${index}">`;
                if (timestamp) {
                    html += `<span class="log-timestamp">${escapeHtml(timestamp)}</span>`;
                }
                if (icon) {
                    html += `<span class="log-icon"><i class="fas ${icon}"></i></span>`;
                }
                html += `<span class="log-content">${formatLogContent(content)}</span>`;
                html += `</div>`;
            });
            
            container.innerHTML = html;
            
            // Автопрокрутка вниз
            container.scrollTop = container.scrollHeight;
            
        } catch (error) {
            console.error('Error loading logs:', error);
            container.innerHTML = '<div class="text-danger p-3">Ошибка загрузки логов: ' + escapeHtml(error.message) + '</div>';
        }
    }
    
    // Автообновление логов
    function toggleLogsAutoRefresh() {
        const btn = document.getElementById('auto-refresh-logs-btn');
        if (!btn) return;
        
        logsAutoRefresh = !logsAutoRefresh;
        
        if (logsAutoRefresh) {
            btn.innerHTML = '<i class="fas fa-pause"></i> Остановить';
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-warning');
            logsInterval = setInterval(loadLogs, 2000);
        } else {
            btn.innerHTML = '<i class="fas fa-play"></i> Автообновление';
            btn.classList.remove('btn-warning');
            btn.classList.add('btn-primary');
            if (logsInterval) {
                clearInterval(logsInterval);
                logsInterval = null;
            }
        }
    }
    
    // Показ toast-уведомлений (новый формат)
    function showToast(title, message, type = 'info', fullError = null) {
        // Выводим полный лог в консоль, если это ошибка
        if (fullError && type === 'error') {
            console.error('[' + title + ']', fullError);
            console.error('Полный лог ошибки смотрите в консоли браузера (F12)');
        }
        
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
        
        const toast = document.createElement('div');
        toast.className = 'toast-notification ' + type;
        
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle',
            danger: 'fa-exclamation-circle'
        };
        
        const icon = icons[type] || icons.info;
        
        toast.innerHTML = `
            <div class="toast-icon">
                <i class="fas ${icon}"></i>
            </div>
            <div class="toast-content">
                <div class="toast-title">${escapeHtml(title)}</div>
                ${message ? '<div class="toast-message">' + escapeHtml(message) + '</div>' : ''}
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        container.appendChild(toast);
        
        // Автоматическое удаление через 5 секунд
        setTimeout(function() {
            if (toast.parentNode) {
                toast.classList.add('hiding');
                setTimeout(function() {
                    if (toast.parentNode) {
                        toast.remove();
                    }
                }, 300);
            }
        }, 5000);
    }
    
    // Обертки для обратной совместимости (устаревшие функции - использовать не рекомендуется)
    function showSuccess(title, message = '') {
        if (typeof title === 'string' && !message) {
            // Старый формат: showSuccess('Сообщение')
            showToast(title, '', 'success');
        } else {
            showToast(title, message, 'success');
        }
    }
    
    function showError(title, message = '', fullError = null) {
        if (typeof title === 'string' && !message && !fullError) {
            // Старый формат: showError('Сообщение')
            showToast(title, '', 'error', title);
        } else {
            if (!message && fullError) {
                // Пытаемся извлечь короткое сообщение из ошибки
                const errorStr = fullError.toString();
                if (errorStr.includes('WinError 32') || errorStr.includes('locked by another process') || 
                    errorStr.includes('file is locked') || errorStr.includes('cannot access') ||
                    errorStr.includes('занят другим процессом')) {
                    message = 'Файл занят другим процессом. Остановите бота перед удалением.';
                } else if (errorStr.includes('Permission denied') || errorStr.includes('Access denied')) {
                    message = 'Недостаточно прав для выполнения операции';
                } else if (errorStr.includes('Connection') || errorStr.includes('fetch')) {
                    message = 'Ошибка соединения с сервером';
                } else {
                    message = 'Произошла ошибка. См. консоль (F12) для подробностей.';
                }
            }
            showToast(title, message, 'error', fullError);
        }
    }
    
    function showWarning(title, message = '') {
        if (typeof title === 'string' && !message) {
            // Старый формат: showWarning('Сообщение')
            showToast(title, '', 'warning');
        } else {
            showToast(title, message, 'warning');
        }
    }
    
    // Парсинг строки лога
    function parseLogLine(line) {
        let type = 'log-default';
        let icon = null;
        let timestamp = null;
        let content = line;
        
        // Извлечение временной метки (форматы: YYYY-MM-DD HH:MM:SS, HH:MM:SS, [timestamp])
        const timestampRegex = /(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}|\d{2}:\d{2}:\d{2}|\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]|\[\d{2}:\d{2}:\d{2}\])/;
        const timestampMatch = line.match(timestampRegex);
        if (timestampMatch) {
            timestamp = timestampMatch[1].replace(/[\[\]]/g, '');
            content = line.replace(timestampRegex, '').trim();
        }
        
        // Определение типа и иконки
        const upperLine = line.toUpperCase();
        
        if (upperLine.includes('ERROR') || upperLine.includes('EXCEPTION') || 
            upperLine.includes('TRACEBACK') || upperLine.includes('FAILED') ||
            upperLine.includes('CRITICAL') || upperLine.includes('FATAL')) {
            type = 'log-error';
            icon = 'fa-exclamation-circle';
        } else if (upperLine.includes('WARNING') || upperLine.includes('WARN') ||
                   upperLine.includes('DEPRECATED') || upperLine.includes('CAUTION')) {
            type = 'log-warning';
            icon = 'fa-exclamation-triangle';
        } else if (upperLine.includes('INFO') || upperLine.includes('INFORMATION') ||
                   upperLine.includes('LOG') || upperLine.includes('MESSAGE')) {
            type = 'log-info';
            icon = 'fa-info-circle';
        } else if (upperLine.includes('SUCCESS') || upperLine.includes('COMPLETED') ||
                   upperLine.includes('DONE') || upperLine.includes('OK') ||
                   upperLine.includes('STARTED') || upperLine.includes('RUNNING')) {
            type = 'log-success';
            icon = 'fa-check-circle';
        } else if (upperLine.includes('DEBUG') || upperLine.includes('TRACE')) {
            type = 'log-debug';
            icon = 'fa-bug';
        }
        
        return { type, icon, timestamp, content };
    }
    
    // Форматирование содержимого лога с подсветкой синтаксиса
    function formatLogContent(text) {
        if (!text) return '';
        
        // Просто экранируем HTML для безопасности
        // CSS white-space: pre-wrap сохранит переносы строк автоматически
        return escapeHtml(text);
    }
    
    // Экранирование HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Экспорт функции showSection для глобального доступа
    window.showSection = showSection;
    
    // Функции для загрузки файлов и создания папок
    window.showUploadFileDialog = function() {
        document.getElementById('file-upload-input').value = '';
        const destinationPathInput = document.getElementById('upload-destination-path');
        if (destinationPathInput) {
            destinationPathInput.value = window.selectedUploadDirectory || '';
        }
        const modal = new bootstrap.Modal(document.getElementById('uploadFileModal'));
        modal.show();
    };
    
    window.handleUploadFile = async function() {
        if (!botId) return;
        
        const fileInput = document.getElementById('file-upload-input');
        const destinationPath = document.getElementById('upload-destination-path')?.value.trim() || window.selectedUploadDirectory || '';
        
        if (!fileInput.files || fileInput.files.length === 0) {
            showWarning('Внимание', 'Выберите файл(ы) для загрузки');
            return;
        }
        
        try {
            const formData = new FormData();
            formData.append('path', destinationPath);
            for (let i = 0; i < fileInput.files.length; i++) {
                formData.append('files', fileInput.files[i]);
            }
            
            const response = await fetch('/api/bots/' + botId + '/file/upload', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ошибка загрузки файла');
            }
            
            const result = await response.json();
            
            if (result.success) {
                showSuccess('Файлы загружены', `Загружено файлов: ${result.uploaded_files.length}`);
                const modal = bootstrap.Modal.getInstance(document.getElementById('uploadFileModal'));
                if (modal) modal.hide();
                fileInput.value = '';
                const destinationPathInput = document.getElementById('upload-destination-path');
                if (destinationPathInput) destinationPathInput.value = '';
                window.selectedUploadDirectory = '';
                loadFiles();
            } else {
                showError('Ошибка загрузки', result.error || 'Неизвестная ошибка', result.error);
            }
        } catch (error) {
            console.error('Upload file error:', error);
            showError('Ошибка загрузки', 'Не удалось загрузить файл(ы). См. консоль (F12).', error.message);
        }
    };
    
    window.showCreateFolderDialog = function() {
        document.getElementById('new-folder-path').value = window.selectedUploadDirectory || '';
        const modal = new bootstrap.Modal(document.getElementById('createFolderModal'));
        modal.show();
    };
    
    window.handleCreateFolder = async function() {
        if (!botId) return;
        
        const folderPath = document.getElementById('new-folder-path').value.trim();
        if (!folderPath) {
            showWarning('Внимание', 'Введите путь к папке');
            return;
        }
        
        try {
            const response = await fetch('/api/bots/' + botId + '/file/directory', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: folderPath})
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ошибка создания папки');
            }
            
            const result = await response.json();
            
            if (result.success) {
                showSuccess('Папка создана', 'Папка успешно создана');
                const modal = bootstrap.Modal.getInstance(document.getElementById('createFolderModal'));
                if (modal) modal.hide();
                document.getElementById('new-folder-path').value = '';
                loadFiles();
            } else {
                showError('Ошибка создания', result.error || 'Неизвестная ошибка', result.error);
            }
        } catch (error) {
            console.error('Create folder error:', error);
            showError('Ошибка создания', 'Не удалось создать папку. См. консоль (F12).', error.message);
        }
    };
    
    // Переименование файла
    function showRenameFileDialog() {
        if (!currentFile) {
            showWarning('Внимание', 'Файл не выбран');
            return;
        }
        
        const fileName = currentFile.split('/').pop();
        document.getElementById('current-file-name').value = currentFile;
        document.getElementById('new-file-name-rename').value = fileName;
        
        const modal = new bootstrap.Modal(document.getElementById('renameFileModal'));
        modal.show();
    }
    
    async function handleRenameFile() {
        if (!botId || !currentFile) {
            showWarning('Внимание', 'Файл не выбран');
            return;
        }
        
        const newFileNameInput = document.getElementById('new-file-name-rename');
        if (!newFileNameInput) {
            showError('Ошибка', 'Элемент формы не найден');
            return;
        }
        
        const newFileName = newFileNameInput.value.trim();
        if (!newFileName) {
            showWarning('Внимание', 'Введите новое имя файла');
            return;
        }
        
        // Формируем новый путь
        const oldPath = currentFile;
        const pathParts = oldPath.split('/');
        pathParts[pathParts.length - 1] = newFileName;
        const newPath = pathParts.join('/');
        
        try {
            const response = await fetch('/api/bots/' + botId + '/file/rename', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    old_path: oldPath,
                    new_path: newPath
                })
            });
            
            if (!response.ok) {
                let errorMsg = 'Неизвестная ошибка';
                try {
                    const error = await response.json();
                    errorMsg = error.detail || error.error || 'Ошибка переименования файла';
                    
                    if (errorMsg.includes('already exists') || errorMsg.includes('уже существует')) {
                        errorMsg = 'Файл с таким именем уже существует. Выберите другое имя.';
                    } else if (errorMsg.includes('not found') || errorMsg.includes('не найден')) {
                        errorMsg = 'Файл не найден. Возможно, он был удален.';
                    } else if (errorMsg.includes('PermissionError') || errorMsg.includes('Access denied')) {
                        errorMsg = 'Недостаточно прав для переименования файла. Проверьте права доступа.';
                    } else if (errorMsg.includes('config.json')) {
                        errorMsg = 'Невозможно переименовать config.json. Этот файл защищен системой.';
                    }
                } catch (e) {
                    errorMsg = 'Ошибка соединения с сервером';
                }
                throw new Error(errorMsg);
            }
            
            const result = await response.json();
            
            if (result.success) {
                showSuccess('Файл переименован', 'Файл успешно переименован');
                const modal = bootstrap.Modal.getInstance(document.getElementById('renameFileModal'));
                if (modal) modal.hide();
                
                // Обновляем текущий файл
                currentFile = result.new_path || newPath;
                
                // Перезагружаем файлы
                loadFiles();
            } else {
                showError('Ошибка переименования', result.error || 'Неизвестная ошибка', result.error);
            }
        } catch (error) {
            console.error('Rename file error:', error);
            showError('Ошибка переименования', 'Не удалось переименовать файл. См. консоль (F12).', error.message);
        }
    }
    
    // Инициализация графиков
    function initCharts() {
        const cpuCtx = document.getElementById('cpu-chart');
        const memoryCtx = document.getElementById('memory-chart');
        
        if (!cpuCtx || !memoryCtx) return;
        
        // Получаем цвета из CSS переменных
        const rootStyle = getComputedStyle(document.documentElement);
        const textColor = rootStyle.getPropertyValue('--text-primary').trim() || '#ffffff';
        const textSecondary = rootStyle.getPropertyValue('--text-secondary').trim() || '#b4b9d1';
        const borderColor = rootStyle.getPropertyValue('--border-color').trim() || '#2a2f47';
        let neonCyan = rootStyle.getPropertyValue('--neon-cyan').trim() || '#00f3ff';
        let neonGreen = rootStyle.getPropertyValue('--neon-green').trim() || '#39ff14';
        
        // Конвертируем hex в rgb для rgba
        function hexToRgb(hex) {
            const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
            return result ? {
                r: parseInt(result[1], 16),
                g: parseInt(result[2], 16),
                b: parseInt(result[3], 16)
            } : null;
        }
        
        const neonCyanRgb = hexToRgb(neonCyan);
        const neonGreenRgb = hexToRgb(neonGreen);
        const neonCyanRgba = neonCyanRgb ? `rgba(${neonCyanRgb.r}, ${neonCyanRgb.g}, ${neonCyanRgb.b}, 0.1)` : 'rgba(0, 243, 255, 0.1)';
        const neonGreenRgba = neonGreenRgb ? `rgba(${neonGreenRgb.r}, ${neonGreenRgb.g}, ${neonGreenRgb.b}, 0.1)` : 'rgba(57, 255, 20, 0.1)';
        
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: textColor,
                    bodyColor: textColor,
                    borderColor: borderColor,
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: textSecondary,
                        maxRotation: 45,
                        minRotation: 0,
                        font: {
                            size: 11
                        }
                    },
                    grid: {
                        color: borderColor
                    }
                },
                y: {
                    ticks: {
                        color: textSecondary,
                        font: {
                            size: 11
                        }
                    },
                    grid: {
                        color: borderColor
                    },
                    beginAtZero: true
                }
            }
        };
        
        // График CPU
        cpuChart = new Chart(cpuCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'CPU %',
                    data: [],
                    borderColor: neonCyan,
                    backgroundColor: neonCyanRgba,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 4
                }]
            },
            options: chartOptions
        });
        
        // График памяти
        memoryChart = new Chart(memoryCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Memory MB',
                    data: [],
                    borderColor: neonGreen,
                    backgroundColor: neonGreenRgba,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 4
                }]
            },
            options: chartOptions
        });
    }
    
    // Загрузка метрик
    async function loadMetrics(hours) {
        if (!botId) return;
        
        try {
            const response = await fetch(`/api/bots/${botId}/metrics?hours=${hours}`);
            if (!response.ok) {
                console.error('Ошибка загрузки метрик:', response.statusText);
                return;
            }
            
            const result = await response.json();
            if (result.success && result.metrics) {
                updateCharts(result.metrics);
            }
        } catch (error) {
            console.error('Ошибка загрузки метрик:', error);
        }
    }
    
    // Обновление графиков
    function updateCharts(metrics) {
        if (!cpuChart || !memoryChart || !metrics || metrics.length === 0) {
            // Если нет данных, показываем пустые графики
            if (cpuChart) {
                cpuChart.data.labels = [];
                cpuChart.data.datasets[0].data = [];
                cpuChart.update();
            }
            if (memoryChart) {
                memoryChart.data.labels = [];
                memoryChart.data.datasets[0].data = [];
                memoryChart.update();
            }
            return;
        }
        
        const labels = [];
        const cpuData = [];
        const memoryData = [];
        
        metrics.forEach(metric => {
            const date = new Date(metric.timestamp);
            // Форматируем время в зависимости от периода
            let timeLabel;
            if (currentMetricsPeriod <= 6) {
                timeLabel = date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
            } else if (currentMetricsPeriod <= 24) {
                timeLabel = date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
            } else {
                timeLabel = date.toLocaleString('ru-RU', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            }
            
            labels.push(timeLabel);
            cpuData.push(metric.cpu_percent || 0);
            memoryData.push(metric.memory_mb || 0);
        });
        
        // Обновляем график CPU
        cpuChart.data.labels = labels;
        cpuChart.data.datasets[0].data = cpuData;
        cpuChart.update('none'); // 'none' для плавного обновления
        
        // Обновляем график памяти
        memoryChart.data.labels = labels;
        memoryChart.data.datasets[0].data = memoryData;
        memoryChart.update('none');
    }
    
    // Изменение периода метрик
    window.changeMetricsPeriod = function(hours) {
        currentMetricsPeriod = hours;
        
        // Обновляем активную кнопку
        document.querySelectorAll('[data-period]').forEach(btn => {
            if (parseInt(btn.getAttribute('data-period')) === hours) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        // Загружаем новые метрики
        loadMetrics(hours);
    };
    
})();
