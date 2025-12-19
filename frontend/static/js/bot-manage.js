// Панель управления ботом - Упрощенная версия

(function() {
    'use strict';
    
    // Глобальные переменные
    let botId = null;
    let codeEditor = null;
    let currentFile = null;
    let updateInterval = null;
    
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
        if (createDbBtn) {
            createDbBtn.addEventListener('click', handleCreateDatabase);
        }
        
        const phpmyadminBtn = document.getElementById('phpmyadmin-btn');
        if (phpmyadminBtn) {
            phpmyadminBtn.addEventListener('click', handleOpenPhpMyAdmin);
        }
        
        const executeQueryBtn = document.getElementById('execute-query-btn');
        if (executeQueryBtn) {
            executeQueryBtn.addEventListener('click', handleExecuteQuery);
        }
        
        // Кнопка обновления из Git
        const updateGitBtn = document.getElementById('update-git-btn');
        if (updateGitBtn) {
            updateGitBtn.addEventListener('click', handleUpdateFromGit);
        }
        
        // Кнопки для работы с файлами
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
        const deleteFileBtnHeader = document.getElementById('delete-file-btn-header');
        if (deleteFileBtn) {
            deleteFileBtn.addEventListener('click', handleDeleteFile);
        }
        if (deleteFileBtnHeader) {
            deleteFileBtnHeader.addEventListener('click', handleDeleteFile);
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
        
        const gitRepoInput = document.getElementById('git-repo-url');
        if (gitRepoInput) gitRepoInput.value = bot.git_repo_url || '';
        
        const gitBranchInput = document.getElementById('git-branch');
        if (gitBranchInput) gitBranchInput.value = bot.git_branch || 'main';
        
        // Dashboard информация
        const typeInfo = document.getElementById('bot-type-info');
        if (typeInfo) typeInfo.textContent = bot.bot_type === 'discord' ? 'Discord' : 'Telegram';
        
        const startFileInfo = document.getElementById('start-file-info');
        if (startFileInfo) startFileInfo.textContent = bot.start_file || 'Не указан';
        
        const cpuLimitInfo = document.getElementById('cpu-limit-info');
        if (cpuLimitInfo) cpuLimitInfo.textContent = bot.cpu_limit || 50;
        
        const memoryLimitInfo = document.getElementById('memory-limit-info');
        if (memoryLimitInfo) memoryLimitInfo.textContent = bot.memory_limit || 512;
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
        }
    }
    
    // Запуск обновления статуса
    function startStatusUpdate() {
        if (updateInterval) {
            clearInterval(updateInterval);
        }
        
        updateStatus();
        updateInterval = setInterval(updateStatus, 5000);
    }
    
    // Обновление статуса
    async function updateStatus() {
        if (!botId) return;
        
        try {
            const response = await fetch('/api/bots/' + botId + '/status');
            if (!response.ok) return;
            
            const status = await response.json();
            
            // Определяем статус бота
            let botStatus = 'stopped';
            if (status.running) {
                botStatus = 'running';
            } else if (status.status === 'installing') {
                botStatus = 'installing';
            }
            
            // Статус
            const statusText = document.getElementById('bot-status-text');
            if (statusText) {
                if (botStatus === 'running') {
                    statusText.textContent = 'Запущен';
                } else if (botStatus === 'installing') {
                    statusText.textContent = 'Установка зависимостей...';
                } else {
                    statusText.textContent = 'Остановлен';
                }
            }
            
            const statusIndicator = document.getElementById('bot-status-indicator');
            if (statusIndicator) {
                statusIndicator.className = 'bot-status ' + botStatus;
            }
            
            // Кнопки
            const startBtn = document.getElementById('start-bot-btn');
            const stopBtn = document.getElementById('stop-bot-btn');
            
            if (startBtn) {
                startBtn.disabled = status.running || botStatus === 'installing';
                startBtn.style.display = (status.running || botStatus === 'installing') ? 'none' : 'inline-block';
            }
            
            if (stopBtn) {
                stopBtn.disabled = !status.running || botStatus === 'installing';
                stopBtn.style.display = (status.running && botStatus !== 'installing') ? 'inline-block' : 'none';
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
        
        const formData = {
            name: document.getElementById('bot-name').value,
            start_file: document.getElementById('start-file').value || null,
            cpu_limit: parseFloat(document.getElementById('cpu-limit').value) || 50,
            memory_limit: parseInt(document.getElementById('memory-limit').value) || 512,
            git_repo_url: document.getElementById('git-repo-url').value || null,
            git_branch: document.getElementById('git-branch').value || 'main'
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
        
        // Скрываем кнопки удаления и переименования
        const deleteBtn = document.getElementById('delete-file-btn');
        const deleteBtnHeader = document.getElementById('delete-file-btn-header');
        const renameBtn = document.getElementById('rename-file-btn');
        if (deleteBtn) deleteBtn.style.display = 'none';
        if (deleteBtnHeader) deleteBtnHeader.style.display = 'none';
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
            // Показываем кнопки удаления и переименования для файлов
            const deleteBtn = document.getElementById('delete-file-btn');
            const deleteBtnHeader = document.getElementById('delete-file-btn-header');
            const renameBtn = document.getElementById('rename-file-btn');
            if (deleteBtn) deleteBtn.style.display = 'inline-block';
            if (deleteBtnHeader) deleteBtnHeader.style.display = 'inline-block';
            if (renameBtn) renameBtn.style.display = 'inline-block';
        } else {
            // Для папок сохраняем путь в currentFile для удаления
            currentFile = path;
            // Показываем только кнопку удаления для папок
            const deleteBtn = document.getElementById('delete-file-btn');
            const deleteBtnHeader = document.getElementById('delete-file-btn-header');
            const renameBtn = document.getElementById('rename-file-btn');
            if (deleteBtn) deleteBtn.style.display = 'inline-block';
            if (deleteBtnHeader) deleteBtnHeader.style.display = 'inline-block';
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
            
            // Показываем кнопки удаления и переименования
            const deleteBtn = document.getElementById('delete-file-btn');
            const deleteBtnHeader = document.getElementById('delete-file-btn-header');
            const renameBtn = document.getElementById('rename-file-btn');
            if (deleteBtn) {
                deleteBtn.style.display = 'inline-block';
                deleteBtn.setAttribute('data-file-path', filepath);
            }
            if (deleteBtnHeader) {
                deleteBtnHeader.style.display = 'inline-block';
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
            
            // Скрываем кнопки удаления и переименования
            const deleteBtn = document.getElementById('delete-file-btn');
            const deleteBtnHeader = document.getElementById('delete-file-btn-header');
            const renameBtn = document.getElementById('rename-file-btn');
            if (deleteBtn) deleteBtn.style.display = 'none';
            if (deleteBtnHeader) deleteBtnHeader.style.display = 'none';
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
        
        const container = document.getElementById('db-info');
        if (!container) {
            console.error('Database info container not found');
            return;
        }
        
        container.innerHTML = '<div class="text-muted">Загрузка информации о базе данных...</div>';
        
        try {
            const response = await fetch('/api/bots/' + botId + '/db');
            if (!response.ok) {
                console.error('Failed to load database info:', response.status);
                container.innerHTML = '<div class="alert alert-danger">Ошибка загрузки информации о базе данных</div>';
                return;
            }
            
            const dbInfo = await response.json();
            
            if (dbInfo.exists) {
                let html = '<div class="alert alert-success">';
                html += '<strong>База данных:</strong> ' + escapeHtml(dbInfo.db_name) + '<br>';
                html += '<strong>Пользователь:</strong> ' + escapeHtml(dbInfo.db_user) + '<br>';
                html += '<strong>Пароль:</strong> ' + escapeHtml(dbInfo.db_password);
                html += '</div>';
                container.innerHTML = html;
            } else {
                container.innerHTML = '<div class="alert alert-secondary">База данных не создана<br><button class="btn btn-primary mt-2" id="create-db-btn"><i class="fas fa-plus"></i> Создать базу данных</button></div>';
                // Переподключаем обработчик для кнопки в сообщении
                const btn = document.getElementById('create-db-btn');
                if (btn) {
                    btn.addEventListener('click', handleCreateDatabase);
                }
            }
        } catch (error) {
            console.error('Error loading database:', error);
            container.innerHTML = '<div class="alert alert-danger">Ошибка загрузки информации о базе данных: ' + escapeHtml(error.message) + '</div>';
        }
    }
    
    // Создание базы данных
    async function handleCreateDatabase() {
        if (!botId) return;
        
        try {
            const response = await fetch('/api/bots/' + botId + '/db', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                showSuccess('База данных создана', 'База данных успешно создана');
                loadDatabase();
            } else {
                showError('Ошибка создания', result.error || 'Неизвестная ошибка', result.error);
            }
        } catch (error) {
            console.error('Create database error:', error);
            showError('Ошибка создания', 'Не удалось создать базу данных. См. консоль (F12).', error.message);
        }
    }
    
    // Открытие phpMyAdmin
    async function handleOpenPhpMyAdmin() {
        if (!botId) return;
        
        try {
            const response = await fetch('/api/bots/' + botId + '/db/phpmyadmin');
            if (!response.ok) return;
            
            const result = await response.json();
            if (result.url) {
                window.open(result.url, '_blank');
            }
        } catch (error) {
            console.error('Error opening phpMyAdmin:', error);
        }
    }
    
    // Выполнение SQL запроса
    async function handleExecuteQuery() {
        if (!botId) return;
        
        const query = document.getElementById('sql-query').value.trim();
        if (!query) {
            showWarning('Внимание', 'Введите SQL запрос');
            return;
        }
        
        try {
            const response = await fetch('/api/bots/' + botId + '/db/query', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: query})
            });
            
            const result = await response.json();
            const container = document.getElementById('query-result');
            
            if (!container) return;
            
            if (result.success) {
                if (result.type === 'select') {
                    let html = '<div class="alert alert-success">Запрос выполнен успешно. Найдено строк: ' + result.row_count + '</div>';
                    
                    if (result.rows && result.rows.length > 0) {
                        html += '<table class="table table-striped table-bordered"><thead><tr>';
                        result.columns.forEach(function(col) {
                            html += '<th>' + escapeHtml(col) + '</th>';
                        });
                        html += '</tr></thead><tbody>';
                        
                        result.rows.forEach(function(row) {
                            html += '<tr>';
                            result.columns.forEach(function(col) {
                                html += '<td>' + escapeHtml(String(row[col] || '')) + '</td>';
                            });
                            html += '</tr>';
                        });
                        
                        html += '</tbody></table>';
                    }
                    
                    container.innerHTML = html;
                } else {
                    container.innerHTML = '<div class="alert alert-success">Запрос выполнен. Затронуто строк: ' + result.affected_rows + '</div>';
                }
            } else {
                container.innerHTML = '<div class="alert alert-danger">Ошибка: ' + escapeHtml(result.error) + '</div>';
            }
        } catch (error) {
            console.error('Execute query error:', error);
            const container = document.getElementById('query-result');
            if (container) {
                container.innerHTML = '<div class="alert alert-danger">Ошибка выполнения запроса. См. консоль (F12) для подробностей.</div>';
            }
            showError('Ошибка запроса', 'Не удалось выполнить SQL запрос. См. консоль (F12).', error.message);
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
            
            if (container) {
                if (status.is_repo) {
                    let html = '<div class="alert alert-info">';
                    html += '<strong>Репозиторий:</strong> ' + escapeHtml(status.remote || 'Локальный') + '<br>';
                    html += '<strong>Ветка:</strong> ' + escapeHtml(status.current_branch || status.branch || 'N/A') + '<br>';
                    if (status.has_changes) {
                        html += '<span class="text-warning">Есть несохраненные изменения</span>';
                    } else {
                        html += '<span class="text-success">Ветка синхронизирована</span>';
                    }
                    html += '</div>';
                    container.innerHTML = html;
                } else {
                    // Проверяем, указан ли URL репозитория в настройках бота
                    const botInfo = await fetch('/api/bots/' + botId).then(r => r.ok ? r.json() : null).catch(() => null);
                    const repoUrl = botInfo?.git_repo_url;
                    
                    if (repoUrl) {
                        container.innerHTML = `
                            <div class="alert alert-warning">
                                <h6><i class="fas fa-exclamation-triangle"></i> Git репозиторий не клонирован</h6>
                                <p class="mb-2">Репозиторий указан в настройках, но не клонирован в директорию бота.</p>
                                <p class="mb-2"><strong>URL:</strong> ${escapeHtml(repoUrl)}</p>
                                <button class="btn btn-primary btn-sm" onclick="handleCloneRepository()">
                                    <i class="fas fa-download"></i> Клонировать репозиторий
                                </button>
                            </div>
                        `;
                    } else {
                        container.innerHTML = '<div class="alert alert-secondary">Git репозиторий не найден</div>';
                    }
                }
            }
        } catch (error) {
            console.error('Error loading git status:', error);
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
        if (container) {
            container.innerHTML = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> Клонирование репозитория...</div>';
        }
        
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
                    showSuccess('Репозиторий клонирован', 'Репозиторий успешно клонирован в директорию бота');
                    setTimeout(() => {
                        loadGitStatus();
                    }, 1000);
                } else {
                    const error = await response.json().catch(() => ({ detail: 'Неизвестная ошибка' }));
                    showError('Ошибка клонирования', error.detail || 'Не удалось клонировать репозиторий');
                    loadGitStatus();
                }
            } else {
                const error = await response.json().catch(() => ({ detail: 'Неизвестная ошибка' }));
                showError('Ошибка клонирования', error.detail || 'Не удалось клонировать репозиторий');
                loadGitStatus();
            }
        } catch (error) {
            console.error('Error cloning repository:', error);
            showError('Ошибка клонирования', error.message || 'Неизвестная ошибка');
            loadGitStatus();
        }
    }
    
    // Обновление из Git
    async function handleUpdateFromGit() {
        if (!botId) return;
        
        const btn = document.getElementById('update-git-btn');
        if (btn) btn.disabled = true;
        
        try {
            const response = await fetch('/api/bots/' + botId + '/update', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                showSuccess('Бот обновлен', 'Бот успешно обновлен из Git');
                loadGitStatus();
            } else {
                showError('Ошибка обновления', result.error || 'Неизвестная ошибка', result.error);
            }
        } catch (error) {
            console.error('Update bot error:', error);
            showError('Ошибка обновления', 'Не удалось обновить бота. См. консоль (F12).', error.message);
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
            info: 'fa-info-circle'
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
    
})();
