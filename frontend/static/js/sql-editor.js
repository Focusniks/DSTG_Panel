// SQL Editor JavaScript - Полностью переписан
let botId = null;
let currentDbName = null;
let currentTableName = null;
let currentTableStructure = null;
let currentTableData = null;
let editingRowId = null;
let primaryKeyColumn = 'id';
let sqlEditor = null;

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    // Получаем bot_id из URL
    const pathParts = window.location.pathname.split('/');
    const botIndex = pathParts.indexOf('sql-editor');
    if (botIndex > 0) {
        botId = parseInt(pathParts[botIndex - 1]);
    }
    
    if (!botId) {
        showError('Ошибка', 'Не удалось определить ID бота');
        return;
    }
    
    // Обновляем ссылки и отображение
    const botIdDisplay = document.getElementById('bot-id-display');
    if (botIdDisplay) {
        botIdDisplay.textContent = botId;
    }
    
    if (document.title.includes('...')) {
        document.title = document.title.replace('...', botId);
    }
    
    const backToBotLink = document.getElementById('back-to-bot-link');
    if (backToBotLink) {
        backToBotLink.href = `/bot/${botId}`;
    }
    
    // Инициализация CodeMirror для SQL запросов
    const sqlQueryTextarea = document.getElementById('sql-query');
    if (sqlQueryTextarea) {
        sqlEditor = CodeMirror.fromTextArea(sqlQueryTextarea, {
            mode: 'text/x-sql',
            theme: 'monokai',
            lineNumbers: true,
            indentWithTabs: true,
            smartIndent: true,
            lineWrapping: true,
            autoCloseBrackets: true,
            matchBrackets: true,
            extraKeys: {
                "Ctrl-Enter": function(cm) {
                    executeQuery();
                },
                "Ctrl-/": "toggleComment",
                "Ctrl-F": "findPersistent"
            }
        });
        window.sqlEditor = sqlEditor;
    }
    
    // Читаем параметр db из URL заранее
    const urlParams = new URLSearchParams(window.location.search);
    const dbParam = urlParams.get('db');
    if (dbParam) {
        currentDbName = decodeURIComponent(dbParam);
    }
    
    // Загрузка данных
    loadBotInfo();
    loadDatabases();
    
    // Обработчик выбора базы данных в шапке
    const dbSelector = document.getElementById('sql-db-selector');
    if (dbSelector) {
        dbSelector.addEventListener('change', function() {
            if (this.value) {
                selectDatabase(this.value, true);
            } else {
                currentDbName = null;
                const tablesList = document.getElementById('tables-list');
                if (tablesList) {
                    tablesList.innerHTML = '<div style="color: var(--text-muted); padding: 1rem; text-align: center;">Выберите базу данных</div>';
                }
                const createTableBtn = document.getElementById('create-table-btn');
                if (createTableBtn) {
                    createTableBtn.style.display = 'none';
                }
            }
        });
    }
    
    // Обработчики событий для вкладок
    document.querySelectorAll('.sql-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
    
    // Обработчики кнопок
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            if (currentDbName) {
                loadDatabases();
                if (currentTableName) {
                    loadTableData();
                    loadStructure();
                }
            } else {
                loadDatabases();
            }
        });
    }
    
    const createTableBtn = document.getElementById('create-table-btn');
    if (createTableBtn) {
        createTableBtn.addEventListener('click', function() {
            showCreateTableModal();
        });
    }
    
    const addColumnFormBtn = document.getElementById('add-column-form-btn');
    if (addColumnFormBtn) {
        addColumnFormBtn.addEventListener('click', function() {
            addColumnToForm();
        });
    }
    
    const saveCreateTableBtn = document.getElementById('save-create-table-btn');
    if (saveCreateTableBtn) {
        saveCreateTableBtn.addEventListener('click', function() {
            createTable();
        });
    }
    
    const saveAddColumnBtn = document.getElementById('save-add-column-btn');
    if (saveAddColumnBtn) {
        saveAddColumnBtn.addEventListener('click', function() {
            addColumnToTable();
        });
    }
    
    const addRowBtn = document.getElementById('add-row-btn');
    if (addRowBtn) {
        addRowBtn.addEventListener('click', function() {
            showAddRowModal();
        });
    }
    
    const saveNewRowBtn = document.getElementById('save-new-row-btn');
    if (saveNewRowBtn) {
        saveNewRowBtn.addEventListener('click', function() {
            saveNewRow();
        });
    }
    
    const saveEditRowBtn = document.getElementById('save-edit-row-btn');
    if (saveEditRowBtn) {
        saveEditRowBtn.addEventListener('click', function() {
            saveEditRow();
        });
    }
    
    
    const addColumnBtn = document.getElementById('add-column-btn');
    if (addColumnBtn) {
        addColumnBtn.addEventListener('click', function() {
            showAddColumnModal();
        });
    }
    
    const executeQueryBtn = document.getElementById('execute-query-btn');
    if (executeQueryBtn) {
        executeQueryBtn.addEventListener('click', function() {
            executeQuery();
        });
    }
    
    const clearQueryBtn = document.getElementById('clear-query-btn');
    if (clearQueryBtn) {
        clearQueryBtn.addEventListener('click', function() {
            if (sqlEditor) {
                sqlEditor.setValue('');
                sqlEditor.focus();
            }
            const queryResultsSection = document.getElementById('query-results-section');
            if (queryResultsSection) {
                queryResultsSection.style.display = 'none';
            }
        });
    }
});

// Переключение вкладок
function switchTab(tabName) {
    // Скрываем все вкладки
    document.querySelectorAll('.sql-tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Убираем активный класс со всех кнопок вкладок
    document.querySelectorAll('.sql-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Показываем выбранную вкладку
    const selectedTab = document.getElementById(`tab-${tabName}`);
    const selectedTabButton = document.querySelector(`.sql-tab[data-tab="${tabName}"]`);
    
    if (selectedTab) {
        selectedTab.classList.add('active');
    }
    
    if (selectedTabButton) {
        selectedTabButton.classList.add('active');
    }
    
    // Если переключаемся на структуру, загружаем её
    if (tabName === 'structure' && currentTableName) {
        loadStructure();
    }
}

// Загрузка информации о боте
async function loadBotInfo() {
    const botNameHeader = document.getElementById('bot-name-header');
    if (!botNameHeader) return;
    
    try {
        const response = await fetch(`/api/bots/${botId}`);
        if (response.ok) {
            const bot = await response.json();
            const botName = bot.name || `Бот #${botId}`;
            botNameHeader.textContent = botName;
            document.title = `SQL Редактор - ${botName}`;
        } else {
            botNameHeader.textContent = `Бот #${botId}`;
        }
    } catch (error) {
        console.error('Error loading bot info:', error);
        botNameHeader.textContent = `Бот #${botId}`;
    }
}

// Загрузка списка баз данных
async function loadDatabases() {
    try {
        const response = await fetch(`/api/bots/${botId}/sqlite/databases`);
        if (!response.ok) throw new Error('Failed to load databases');
        
        const result = await response.json();
        const databases = result.databases || result;
        const dbSelector = document.getElementById('sql-db-selector');
        if (!dbSelector) {
            console.error('sql-db-selector element not found');
            return;
        }
        
        // Сохраняем текущее выбранное значение
        const currentValue = dbSelector.value;
        
        // Очищаем селектор (кроме первого опциона)
        dbSelector.innerHTML = '<option value="">Выберите базу данных...</option>';
        
        if (!databases || databases.length === 0) {
            return;
        }
        
        databases.forEach(db => {
            const dbName = db.db_name || db;
            const option = document.createElement('option');
            option.value = dbName;
            option.textContent = dbName;
            dbSelector.appendChild(option);
        });
        
        // Восстанавливаем выбранное значение или устанавливаем из URL/currentDbName
        if (currentDbName && Array.from(dbSelector.options).find(opt => opt.value === currentDbName)) {
            dbSelector.value = currentDbName;
        } else if (currentValue && Array.from(dbSelector.options).find(opt => opt.value === currentValue)) {
            dbSelector.value = currentValue;
        }
        
        // Если была установлена текущая БД, выбираем её
        if (currentDbName && dbSelector.value !== currentDbName) {
            selectDatabase(currentDbName, false);
        } else if (dbSelector.value && !currentDbName) {
            selectDatabase(dbSelector.value, false);
        }
    } catch (error) {
        console.error('Error loading databases:', error);
        showError('Ошибка', 'Не удалось загрузить список баз данных');
    }
}

// Выбор базы данных
function selectDatabase(dbName, updateUrl = true) {
    currentDbName = dbName;
    
    // Обновляем селектор в топбаре
    const dbSelector = document.getElementById('sql-db-selector');
    if (dbSelector) {
        dbSelector.value = dbName;
    }
    
    // Показываем кнопку создания таблицы
    const createTableBtn = document.getElementById('create-table-btn');
    if (createTableBtn) {
        createTableBtn.style.display = 'inline-block';
    }
    
    // Загружаем таблицы
    loadTables();
    
    // Обновляем URL если нужно
    if (updateUrl) {
        const url = new URL(window.location);
        url.searchParams.set('db', encodeURIComponent(dbName));
        window.history.replaceState({}, '', url);
    }
}

// Загрузка списка таблиц
async function loadTables() {
    if (!currentDbName) return;
    
    const tablesList = document.getElementById('tables-list');
    if (!tablesList) return;
    
    tablesList.innerHTML = '<div style="color: var(--text-muted); padding: 1rem; text-align: center;"><i class="fas fa-spinner fa-spin"></i> Загрузка...</div>';
    
    try {
        const response = await fetch(`/api/bots/${botId}/sqlite/databases/${encodeURIComponent(currentDbName)}/tables`);
        
        let result;
        try {
            result = await response.json();
        } catch (e) {
            console.error('Error parsing response:', e);
            tablesList.innerHTML = '<div style="color: var(--text-muted); padding: 1rem; text-align: center;">Нет таблиц</div>';
            return;
        }
        
        if (result.success === false) {
            const errorMessage = result.error || result.detail || 'Не удалось загрузить список таблиц';
            tablesList.innerHTML = `<div style="color: var(--text-muted); padding: 1rem; text-align: center;">${escapeHtml(errorMessage)}</div>`;
            return;
        }
        
        const tables = result.tables || [];
        tablesList.innerHTML = '';
        
        if (tables.length === 0) {
            tablesList.innerHTML = '<div style="color: var(--text-muted); padding: 1rem; text-align: center;">Нет таблиц</div>';
            return;
        }
        
        tables.forEach(table => {
            const tableName = table.table_name || table;
            const tableItem = document.createElement('div');
            tableItem.className = 'table-item';
            if (currentTableName === tableName) {
                tableItem.classList.add('active');
            }
            tableItem.innerHTML = `
                <i class="fas fa-table table-item-icon"></i>
                <span class="table-item-name">${escapeHtml(tableName)}</span>
            `;
            tableItem.addEventListener('click', function() {
                selectTable(tableName);
            });
            tablesList.appendChild(tableItem);
        });
    } catch (error) {
        console.error('Error loading tables:', error);
        tablesList.innerHTML = '<div style="color: var(--text-muted); padding: 1rem; text-align: center;">Ошибка загрузки таблиц</div>';
    }
}

// Выбор таблицы
function selectTable(tableName) {
    currentTableName = tableName;
    
    // Обновляем активное состояние в списке
    document.querySelectorAll('.table-item').forEach(item => {
        item.classList.remove('active');
    });
    
    const tableItem = Array.from(document.querySelectorAll('.table-item')).find(item => {
        return item.querySelector('.table-item-name').textContent === tableName;
    });
    
    if (tableItem) {
        tableItem.classList.add('active');
    }
    
    // Показываем вкладки данных и структуры
    document.querySelectorAll('.sql-tab[data-tab="data"], .sql-tab[data-tab="structure"]').forEach(tab => {
        tab.style.display = 'inline-flex';
    });
    
    // Обновляем бейджи
    const tableNameBadge = document.getElementById('current-table-name-badge');
    const structureTableNameBadge = document.getElementById('structure-table-name-badge');
    if (tableNameBadge) tableNameBadge.textContent = tableName;
    if (structureTableNameBadge) structureTableNameBadge.textContent = tableName;
    
    // Переключаемся на вкладку данных и загружаем данные
    switchTab('data');
    loadTableData();
}

// Загрузка данных таблицы
async function loadTableData() {
    if (!currentDbName || !currentTableName) return;
    
    try {
        // Загружаем структуру таблицы
        const structureResponse = await fetch(
            `/api/bots/${botId}/sqlite/databases/${encodeURIComponent(currentDbName)}/tables/${encodeURIComponent(currentTableName)}/structure`
        );
        if (!structureResponse.ok) throw new Error('Failed to load table structure');
        const structureResult = await structureResponse.json();
        currentTableStructure = structureResult.structure || structureResult;
        
        // Определяем primary key
        const pkColumn = currentTableStructure.columns.find(col => col.pk === 1);
        if (pkColumn) {
            primaryKeyColumn = pkColumn.name;
        }
        
        // Загружаем данные таблицы
        const dataResponse = await fetch(
            `/api/bots/${botId}/sqlite/databases/${encodeURIComponent(currentDbName)}/tables/${encodeURIComponent(currentTableName)}/data`
        );
        if (!dataResponse.ok) throw new Error('Failed to load table data');
        const dataResult = await dataResponse.json();
        currentTableData = (dataResult.data && dataResult.data.rows) || dataResult.rows || [];
        
        // Отображаем данные
        displayTableData();
    } catch (error) {
        console.error('Error loading table data:', error);
        showError('Ошибка', 'Не удалось загрузить данные таблицы');
        const placeholder = document.getElementById('table-data-placeholder');
        const dataTable = document.getElementById('data-table');
        if (placeholder) placeholder.style.display = 'flex';
        if (dataTable) dataTable.style.display = 'none';
    }
}

// Отображение данных таблицы
function displayTableData() {
    if (!currentTableStructure || !currentTableData) return;
    
    const placeholder = document.getElementById('table-data-placeholder');
    const dataTable = document.getElementById('data-table');
    const thead = document.getElementById('data-table-head');
    const tbody = document.getElementById('data-table-body');
    
    if (placeholder) placeholder.style.display = 'none';
    if (dataTable) dataTable.style.display = 'table';
    
    // Заголовки
    thead.innerHTML = '<tr><th style="width: 120px;">Действия</th>';
    currentTableStructure.columns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col.name + (col.pk ? ' (PK)' : '');
        thead.querySelector('tr').appendChild(th);
    });
    thead.querySelector('tr').innerHTML += '</tr>';
    
    // Данные
    tbody.innerHTML = '';
    currentTableData.forEach((row, rowIndex) => {
        const tr = document.createElement('tr');
        
        // Кнопки действий
        const actionsTd = document.createElement('td');
        actionsTd.className = 'row-actions';
        actionsTd.innerHTML = `
            <button class="btn btn-sm btn-primary" onclick="editRow(${rowIndex})">
                <i class="fas fa-edit"></i>
            </button>
            <button class="btn btn-sm btn-danger" onclick="deleteRow(${rowIndex})">
                <i class="fas fa-trash"></i>
            </button>
        `;
        tr.appendChild(actionsTd);
        
        // Ячейки данных
        currentTableStructure.columns.forEach(col => {
            const td = document.createElement('td');
            const value = row[col.name] !== null && row[col.name] !== undefined ? row[col.name] : '';
            td.textContent = value;
            td.setAttribute('data-column', col.name);
            td.setAttribute('data-type', col.type);
            tr.appendChild(td);
        });
        
        tbody.appendChild(tr);
    });
}

// Глобальные функции для onclick
window.editRow = function(rowIndex) {
    if (!currentTableData || !currentTableData[rowIndex]) return;
    
    const row = currentTableData[rowIndex];
    editingRowId = row[primaryKeyColumn];
    
    const form = document.getElementById('edit-row-form');
    form.innerHTML = '';
    
    currentTableStructure.columns.forEach(col => {
        const value = row[col.name] !== null && row[col.name] !== undefined ? row[col.name] : '';
        
        const div = document.createElement('div');
        div.className = 'mb-3';
        
        const label = document.createElement('label');
        label.className = 'form-label';
        label.textContent = `${col.name}${col.pk ? ' (PK)' : ''} (${col.type})`;
        label.setAttribute('for', `edit-${col.name}`);
        
        const input = document.createElement('input');
        input.type = col.type.toLowerCase().includes('int') ? 'number' : 'text';
        input.className = 'form-control';
        input.id = `edit-${col.name}`;
        input.name = col.name;
        input.value = value;
        if (col.pk) {
            input.disabled = true;
        }
        
        div.appendChild(label);
        div.appendChild(input);
        form.appendChild(div);
    });
    
    const modal = new bootstrap.Modal(document.getElementById('edit-row-modal'));
    modal.show();
};

window.deleteRow = async function(rowIndex) {
    if (!currentTableData || !currentTableData[rowIndex]) return;
    
    const row = currentTableData[rowIndex];
    const rowId = row[primaryKeyColumn];
    
    if (!confirm(`Вы уверены, что хотите удалить эту строку?`)) {
        return;
    }
    
    try {
        const response = await fetch(
            `/api/bots/${botId}/sqlite/tables/${encodeURIComponent(currentTableName)}/rows/${rowId}`,
            {
                method: 'DELETE',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    primary_key: primaryKeyColumn,
                    db_name: currentDbName
                })
            }
        );
        
        const result = await response.json();
        if (result.success) {
            showSuccess('Успех', 'Строка успешно удалена');
            loadTableData();
        } else {
            showError('Ошибка', result.error || 'Не удалось удалить строку');
        }
    } catch (error) {
        console.error('Error deleting row:', error);
        showError('Ошибка', 'Не удалось удалить строку');
    }
};

// Показать модальное окно добавления строки
function showAddRowModal() {
    if (!currentTableStructure) return;
    
    const form = document.getElementById('add-row-form');
    form.innerHTML = '';
    
    currentTableStructure.columns.forEach(col => {
        if (col.pk && col.type.toLowerCase().includes('int')) {
            // Пропускаем auto-increment primary keys
            return;
        }
        
        const div = document.createElement('div');
        div.className = 'mb-3';
        
        const label = document.createElement('label');
        label.className = 'form-label';
        label.textContent = `${col.name}${col.pk ? ' (PK)' : ''} (${col.type})${col.notnull ? ' *' : ''}`;
        label.setAttribute('for', `add-${col.name}`);
        
        const input = document.createElement('input');
        input.type = col.type.toLowerCase().includes('int') || col.type.toLowerCase().includes('real') ? 'number' : 'text';
        input.className = 'form-control';
        input.id = `add-${col.name}`;
        input.name = col.name;
        if (col.notnull && !col.dflt_value) {
            input.required = true;
        }
        if (col.dflt_value !== null) {
            input.value = col.dflt_value;
        }
        
        div.appendChild(label);
        div.appendChild(input);
        form.appendChild(div);
    });
    
    const modal = new bootstrap.Modal(document.getElementById('add-row-modal'));
    modal.show();
}

// Сохранить новую строку
async function saveNewRow() {
    if (!currentTableStructure) return;
    
    const form = document.getElementById('add-row-form');
    const formData = new FormData(form);
    const rowData = {};
    
    currentTableStructure.columns.forEach(col => {
        const value = formData.get(col.name);
        if (value !== null && value !== '') {
            rowData[col.name] = value;
        }
    });
    
    try {
        const response = await fetch(
            `/api/bots/${botId}/sqlite/tables/${encodeURIComponent(currentTableName)}/rows`,
            {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    data: rowData,
                    db_name: currentDbName
                })
            }
        );
        
        const result = await response.json();
        if (result.success) {
            showSuccess('Успех', 'Строка успешно добавлена');
            const modal = bootstrap.Modal.getInstance(document.getElementById('add-row-modal'));
            modal.hide();
            loadTableData();
        } else {
            showError('Ошибка', result.error || 'Не удалось добавить строку');
        }
    } catch (error) {
        console.error('Error adding row:', error);
        showError('Ошибка', 'Не удалось добавить строку');
    }
}

// Сохранить отредактированную строку
async function saveEditRow() {
    if (!editingRowId || !currentTableStructure) return;
    
    const form = document.getElementById('edit-row-form');
    const formData = new FormData(form);
    const rowData = {};
    
    currentTableStructure.columns.forEach(col => {
        if (!col.pk) {
            const value = formData.get(col.name);
            rowData[col.name] = value !== null ? value : null;
        }
    });
    
    try {
        const response = await fetch(
            `/api/bots/${botId}/sqlite/tables/${encodeURIComponent(currentTableName)}/rows/${editingRowId}`,
            {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    data: rowData,
                    primary_key: primaryKeyColumn,
                    db_name: currentDbName
                })
            }
        );
        
        const result = await response.json();
        if (result.success) {
            showSuccess('Успех', 'Строка успешно обновлена');
            const modal = bootstrap.Modal.getInstance(document.getElementById('edit-row-modal'));
            modal.hide();
            editingRowId = null;
            loadTableData();
        } else {
            showError('Ошибка', result.error || 'Не удалось обновить строку');
        }
    } catch (error) {
        console.error('Error updating row:', error);
        showError('Ошибка', 'Не удалось обновить строку');
    }
}

// Загрузка структуры таблицы
async function loadStructure() {
    if (!currentDbName || !currentTableName) return;
    
    try {
        const response = await fetch(
            `/api/bots/${botId}/sqlite/databases/${encodeURIComponent(currentDbName)}/tables/${encodeURIComponent(currentTableName)}/structure`
        );
        if (!response.ok) throw new Error('Failed to load structure');
        
        const result = await response.json();
        const structure = result.structure || result;
        const content = document.getElementById('structure-content');
        
        let html = '<table class="structure-table"><thead><tr>';
        html += '<th>Имя</th><th>Тип</th><th>NOT NULL</th><th>Значение по умолчанию</th><th>Primary Key</th><th>Действия</th>';
        html += '</tr></thead><tbody>';
        
        structure.columns.forEach(col => {
            html += '<tr>';
            html += `<td>${escapeHtml(col.name)}</td>`;
            html += `<td>${escapeHtml(col.type)}</td>`;
            html += `<td>${col.notnull ? 'Да' : 'Нет'}</td>`;
            html += `<td>${col.dflt_value !== null ? escapeHtml(col.dflt_value) : '-'}</td>`;
            html += `<td>${col.pk ? 'Да' : 'Нет'}</td>`;
            html += `<td>`;
            if (!col.pk) {
                html += `<button class="btn btn-sm btn-danger" onclick="deleteColumn('${escapeHtml(col.name)}')">`;
                html += '<i class="fas fa-trash"></i> Удалить';
                html += '</button>';
            } else {
                html += '<span style="color: var(--text-muted);">-</span>';
            }
            html += `</td>`;
            html += '</tr>';
        });
        
        html += '</tbody></table>';
        content.innerHTML = html;
        
        // Показываем кнопку добавления столбца
        const addColumnBtn = document.getElementById('add-column-btn');
        if (addColumnBtn) {
            addColumnBtn.style.display = 'inline-block';
        }
    } catch (error) {
        console.error('Error loading structure:', error);
        showError('Ошибка', 'Не удалось загрузить структуру таблицы');
        const content = document.getElementById('structure-content');
        if (content) {
            content.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-triangle"></i><p>Ошибка загрузки структуры</p></div>';
        }
    }
}

// Выполнение SQL запроса
async function executeQuery() {
    if (!currentDbName) {
        showWarning('Внимание', 'Выберите базу данных');
        return;
    }
    
    if (!sqlEditor) {
        showError('Ошибка', 'SQL редактор не инициализирован');
        return;
    }
    
    const query = sqlEditor.getValue().trim();
    if (!query) {
        showWarning('Внимание', 'Введите SQL запрос');
        return;
    }
    
    try {
        const response = await fetch(`/api/bots/${botId}/sqlite/execute`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                query: query,
                db_name: currentDbName
            })
        });
        
        const result = await response.json();
        const resultsSection = document.getElementById('query-results-section');
        const contentDiv = document.getElementById('query-results-content');
        
        if (result.success) {
            if (result.type === 'select' && result.rows) {
                let html = '';
                
                if (result.rows.length > 0) {
                    html += '<table class="results-table"><thead><tr>';
                    Object.keys(result.rows[0]).forEach(key => {
                        html += `<th>${escapeHtml(key)}</th>`;
                    });
                    html += '</tr></thead><tbody>';
                    
                    result.rows.forEach(row => {
                        html += '<tr>';
                        Object.values(row).forEach(value => {
                            html += `<td>${value !== null ? escapeHtml(String(value)) : '<em style="color: var(--text-muted);">NULL</em>'}</td>`;
                        });
                        html += '</tr>';
                    });
                    
                    html += '</tbody></table>';
                } else {
                    html = '<div class="results-empty"><i class="fas fa-inbox"></i><p>Нет результатов</p></div>';
                }
                
                contentDiv.innerHTML = html;
            } else {
                contentDiv.innerHTML = `<div class="alert alert-success" style="margin: 0;">Запрос выполнен успешно. Затронуто строк: ${result.affected_rows || 0}</div>`;
            }
            
            resultsSection.style.display = 'block';
        } else {
            contentDiv.innerHTML = `<div class="alert alert-danger" style="margin: 0;">Ошибка: ${escapeHtml(result.error || 'Неизвестная ошибка')}</div>`;
            resultsSection.style.display = 'block';
        }
    } catch (error) {
        console.error('Error executing query:', error);
        showError('Ошибка', 'Не удалось выполнить запрос');
    }
}

// Показать модальное окно создания таблицы
function showCreateTableModal() {
    if (!currentDbName) {
        showWarning('Внимание', 'Выберите базу данных');
        return;
    }
    
    document.getElementById('new-table-name').value = '';
    document.getElementById('columns-list').innerHTML = '';
    
    // Добавляем первый столбец по умолчанию (обычно id)
    addColumnToForm('id', 'INTEGER', false, true, true);
    
    const modal = new bootstrap.Modal(document.getElementById('create-table-modal'));
    modal.show();
}

// Добавить столбец в форму создания таблицы
function addColumnToForm(name = '', type = 'TEXT', notnull = false, pk = false, autoIncrement = false) {
    const columnsList = document.getElementById('columns-list');
    const columnIndex = columnsList.children.length;
    
    const columnItem = document.createElement('div');
    columnItem.className = 'column-item';
    columnItem.setAttribute('data-index', columnIndex);
    
    const sqliteTypes = ['TEXT', 'INTEGER', 'REAL', 'BLOB', 'NUMERIC'];
    
    columnItem.innerHTML = `
        <div class="column-item-header">
            <strong>Столбец #${columnIndex + 1}</strong>
            <button type="button" class="btn btn-sm btn-danger" onclick="removeColumnFromForm(this)">
                <i class="fas fa-trash"></i>
            </button>
        </div>
        <div class="column-item-fields">
            <div>
                <label class="form-label">Имя столбца *</label>
                <input type="text" class="form-control form-control-sm" name="column_name" value="${escapeHtml(name)}" required>
            </div>
            <div>
                <label class="form-label">Тип данных *</label>
                <select class="form-select form-select-sm" name="column_type" required>
                    ${sqliteTypes.map(t => `<option value="${t}" ${t === type ? 'selected' : ''}>${t}</option>`).join('')}
                </select>
            </div>
            <div>
                <label class="form-label">
                    <input type="checkbox" name="column_notnull" ${notnull ? 'checked' : ''}> NOT NULL
                </label>
            </div>
            <div>
                <label class="form-label">
                    <input type="checkbox" name="column_pk" ${pk ? 'checked' : ''} onchange="toggleAutoIncrement(this)"> Primary Key
                </label>
            </div>
            <div>
                <label class="form-label">
                    <input type="checkbox" name="column_autoincrement" ${autoIncrement ? 'checked' : ''} ${!pk ? 'disabled' : ''}> AUTO INCREMENT
                </label>
            </div>
        </div>
        <div class="mt-2">
            <label class="form-label">Значение по умолчанию (опционально)</label>
            <input type="text" class="form-control form-control-sm" name="column_default" placeholder="NULL">
        </div>
    `;
    
    columnsList.appendChild(columnItem);
}

// Глобальные функции для форм
window.removeColumnFromForm = function(button) {
    const columnItem = button.closest('.column-item');
    if (columnItem) {
        columnItem.remove();
        updateColumnNumbers();
    }
};

window.toggleAutoIncrement = function(checkbox) {
    const columnItem = checkbox.closest('.column-item');
    const autoIncrementCheckbox = columnItem.querySelector('input[name="column_autoincrement"]');
    if (autoIncrementCheckbox) {
        autoIncrementCheckbox.disabled = !checkbox.checked;
        if (!checkbox.checked) {
            autoIncrementCheckbox.checked = false;
        }
    }
};

function updateColumnNumbers() {
    const columnsList = document.getElementById('columns-list');
    columnsList.querySelectorAll('.column-item').forEach((item, index) => {
        item.setAttribute('data-index', index);
        const header = item.querySelector('.column-item-header strong');
        if (header) {
            header.textContent = `Столбец #${index + 1}`;
        }
    });
}

// Создать таблицу
async function createTable() {
    if (!currentDbName) {
        showWarning('Внимание', 'Выберите базу данных');
        return;
    }
    
    const tableName = document.getElementById('new-table-name').value.trim();
    if (!tableName) {
        showWarning('Внимание', 'Введите имя таблицы');
        return;
    }
    
    const columns = [];
    const columnItems = document.querySelectorAll('#columns-list .column-item');
    
    if (columnItems.length === 0) {
        showWarning('Внимание', 'Добавьте хотя бы один столбец');
        return;
    }
    
    columnItems.forEach(item => {
        const name = item.querySelector('input[name="column_name"]').value.trim();
        const type = item.querySelector('select[name="column_type"]').value;
        const notnull = item.querySelector('input[name="column_notnull"]').checked;
        const pk = item.querySelector('input[name="column_pk"]').checked;
        const autoIncrement = item.querySelector('input[name="column_autoincrement"]').checked;
        const defaultValue = item.querySelector('input[name="column_default"]').value.trim();
        
        if (!name) {
            showWarning('Внимание', 'Все столбцы должны иметь имя');
            return;
        }
        
        let columnDef = `${name} ${type}`;
        if (pk) {
            columnDef += ' PRIMARY KEY';
            if (autoIncrement) {
                columnDef += ' AUTOINCREMENT';
            }
        }
        if (notnull && !pk) {
            columnDef += ' NOT NULL';
        }
        if (defaultValue && !pk) {
            columnDef += ` DEFAULT ${defaultValue}`;
        }
        
        columns.push({
            name: name,
            definition: columnDef
        });
    });
    
    try {
        const response = await fetch(`/api/bots/${botId}/sqlite/tables`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                table_name: tableName,
                columns: columns.map(c => c.definition),
                db_name: currentDbName
            })
        });
        
        let result;
        try {
            result = await response.json();
        } catch (e) {
            console.error('Error parsing response:', e);
            showError('Ошибка', `Ошибка сервера: ${response.status} ${response.statusText}`);
            return;
        }
        
        if (!response.ok) {
            const errorMessage = result.detail || result.error || `Ошибка ${response.status}: ${response.statusText}`;
            showError('Ошибка', errorMessage);
            return;
        }
        
        if (result.success) {
            showSuccess('Успех', 'Таблица успешно создана');
            const modal = bootstrap.Modal.getInstance(document.getElementById('create-table-modal'));
            modal.hide();
            loadTables();
        } else {
            showError('Ошибка', result.error || 'Не удалось создать таблицу');
        }
    } catch (error) {
        console.error('Error creating table:', error);
        showError('Ошибка', `Не удалось создать таблицу: ${error.message || 'Неизвестная ошибка'}`);
    }
}

// Показать модальное окно добавления столбца
window.showAddColumnModal = function() {
    if (!currentDbName || !currentTableName) {
        showWarning('Внимание', 'Выберите таблицу');
        return;
    }
    
    document.getElementById('new-column-name').value = '';
    document.getElementById('new-column-type').value = 'TEXT';
    document.getElementById('new-column-notnull').checked = false;
    document.getElementById('new-column-default').value = '';
    
    const modal = new bootstrap.Modal(document.getElementById('add-column-modal'));
    modal.show();
};

// Добавить столбец в существующую таблицу
async function addColumnToTable() {
    if (!currentDbName || !currentTableName) {
        showWarning('Внимание', 'Выберите таблицу');
        return;
    }
    
    const columnName = document.getElementById('new-column-name').value.trim();
    const columnType = document.getElementById('new-column-type').value;
    const notnull = document.getElementById('new-column-notnull').checked;
    const defaultValue = document.getElementById('new-column-default').value.trim();
    
    if (!columnName) {
        showWarning('Внимание', 'Введите имя столбца');
        return;
    }
    
    try {
        const response = await fetch(
            `/api/bots/${botId}/sqlite/tables/${encodeURIComponent(currentTableName)}/columns`,
            {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    column_name: columnName,
                    column_type: columnType,
                    notnull: notnull,
                    default_value: defaultValue || null,
                    db_name: currentDbName
                })
            }
        );
        
        const result = await response.json();
        if (result.success) {
            showSuccess('Успех', 'Столбец успешно добавлен');
            const modal = bootstrap.Modal.getInstance(document.getElementById('add-column-modal'));
            modal.hide();
            loadStructure();
            loadTableData();
        } else {
            showError('Ошибка', result.error || 'Не удалось добавить столбец');
        }
    } catch (error) {
        console.error('Error adding column:', error);
        showError('Ошибка', 'Не удалось добавить столбец');
    }
}

// Удалить столбец из таблицы
window.deleteColumn = async function(columnName) {
    if (!currentDbName || !currentTableName) {
        showWarning('Внимание', 'Выберите таблицу');
        return;
    }
    
    if (!confirm(`Вы уверены, что хотите удалить столбец "${columnName}"? Это действие необратимо.`)) {
        return;
    }
    
    try {
        const response = await fetch(
            `/api/bots/${botId}/sqlite/tables/${encodeURIComponent(currentTableName)}/columns/${encodeURIComponent(columnName)}?db_name=${encodeURIComponent(currentDbName)}`,
            {
                method: 'DELETE'
            }
        );
        
        const result = await response.json();
        if (result.success) {
            showSuccess('Успех', 'Столбец успешно удален');
            loadStructure();
            loadTableData();
        } else {
            showError('Ошибка', result.error || 'Не удалось удалить столбец');
        }
    } catch (error) {
        console.error('Error deleting column:', error);
        showError('Ошибка', 'Не удалось удалить столбец');
    }
};

// Утилиты для уведомлений
function showAlert(message, type) {
    const container = document.getElementById('alerts-container');
    if (!container) {
        console.error('Alerts container not found');
        return;
    }
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.role = 'alert';
    alert.style.cssText = 'background: var(--bg-card); border: 1px solid var(--border-color); color: var(--text-primary);';
    alert.innerHTML = `
        ${escapeHtml(message)}
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    container.appendChild(alert);
    
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showSuccess(title, message) {
    showAlert(`${title}: ${message}`, 'success');
}

function showError(title, message) {
    showAlert(`${title}: ${message}`, 'danger');
}

function showWarning(title, message) {
    showAlert(`${title}: ${message}`, 'warning');
}
