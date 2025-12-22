// SQL Editor JavaScript
let botId = null;
let currentDbName = null;
let currentTableName = null;
let currentTableStructure = null;
let currentTableData = null;
let editingRowId = null;
let primaryKeyColumn = 'id';

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
    // Обновляем title страницы
    if (document.title.includes('...')) {
        document.title = document.title.replace('...', botId);
    }
    const backToBotLink = document.getElementById('back-to-bot-link');
    if (backToBotLink) {
        backToBotLink.href = `/bot/${botId}`;
    }
    
    // Инициализация CodeMirror для SQL запросов
    const sqlEditor = CodeMirror.fromTextArea(document.getElementById('sql-query'), {
        mode: 'text/x-sql',
        theme: 'monokai',
        lineNumbers: true,
        indentWithTabs: true,
        smartIndent: true,
        lineWrapping: true
    });
    window.sqlEditor = sqlEditor;
    
    // Загрузка данных
    loadBotInfo();
    loadDatabases();
    
    // Обработчики событий
    document.getElementById('db-selector').addEventListener('change', function() {
        currentDbName = this.value;
        const createTableBtn = document.getElementById('create-table-btn');
        if (currentDbName) {
            loadTables();
            if (createTableBtn) {
                createTableBtn.style.display = 'inline-block';
            }
        } else {
            document.getElementById('tables-list').innerHTML = '<li class="text-muted">Выберите базу данных</li>';
            hideTableData();
            if (createTableBtn) {
                createTableBtn.style.display = 'none';
            }
        }
    });
    
    document.getElementById('create-table-btn').addEventListener('click', function() {
        showCreateTableModal();
    });
    
    document.getElementById('add-column-btn').addEventListener('click', function() {
        addColumnToForm();
    });
    
    document.getElementById('save-create-table-btn').addEventListener('click', function() {
        createTable();
    });
    
    document.getElementById('save-add-column-btn').addEventListener('click', function() {
        addColumnToTable();
    });
    
    document.getElementById('refresh-btn').addEventListener('click', function() {
        if (currentDbName) {
            loadTables();
            if (currentTableName) {
                loadTableData();
            }
        } else {
            loadDatabases();
        }
    });
    
    document.getElementById('add-row-btn').addEventListener('click', function() {
        showAddRowForm();
    });
    
    document.getElementById('cancel-add-row-btn').addEventListener('click', function() {
        hideAddRowForm();
    });
    
    document.getElementById('save-new-row-btn').addEventListener('click', function() {
        saveNewRow();
    });
    
    document.getElementById('save-edit-row-btn').addEventListener('click', function() {
        saveEditRow();
    });
    
    document.getElementById('structure-btn').addEventListener('click', function() {
        showStructure();
    });
    
    document.getElementById('back-to-data-btn').addEventListener('click', function() {
        document.getElementById('structure-view').style.display = 'none';
        document.getElementById('table-data-view').style.display = 'block';
        document.getElementById('query-results').style.display = 'none';
    });
    
    document.getElementById('execute-query-btn').addEventListener('click', function() {
        executeQuery();
    });
    
    document.getElementById('clear-query-btn').addEventListener('click', function() {
        sqlEditor.setValue('');
        document.getElementById('query-results').style.display = 'none';
    });
});

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
            // Обновляем title страницы
            document.title = `SQL Редактор - ${botName}`;
        } else {
            // Если запрос не успешен, показываем ID бота
            botNameHeader.textContent = `Бот #${botId}`;
        }
    } catch (error) {
        console.error('Error loading bot info:', error);
        // В случае ошибки показываем ID бота
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
        const selector = document.getElementById('db-selector');
        selector.innerHTML = '<option value="">Выберите базу данных...</option>';
        
        if (!databases || databases.length === 0) {
            return;
        }
        
        databases.forEach(db => {
            const option = document.createElement('option');
            option.value = db.db_name || db;
            option.textContent = db.db_name || db;
            selector.appendChild(option);
        });
        
        if (currentDbName) {
            selector.value = currentDbName;
        }
    } catch (error) {
        console.error('Error loading databases:', error);
        showError('Ошибка', 'Не удалось загрузить список баз данных');
    }
}

// Загрузка списка таблиц
async function loadTables() {
    if (!currentDbName) return;
    
    const tablesList = document.getElementById('tables-list');
    if (!tablesList) return;
    
    // Показываем индикатор загрузки
    tablesList.innerHTML = '<li class="text-muted"><i class="fas fa-spinner fa-spin"></i> Загрузка...</li>';
    
    try {
        const response = await fetch(`/api/bots/${botId}/sqlite/databases/${encodeURIComponent(currentDbName)}/tables`);
        
        let result;
        try {
            result = await response.json();
        } catch (e) {
            // Если не удалось распарсить JSON, считаем что это ошибка
            console.error('Error parsing response:', e);
            tablesList.innerHTML = '<li class="text-muted">Нет таблиц</li>';
            return;
        }
        
        // Проверяем, есть ли success в ответе
        if (result.success === false) {
            // Если success = false, показываем ошибку только если это не просто отсутствие таблиц
            const errorMessage = result.error || result.detail || 'Не удалось загрузить список таблиц';
            if (response.status === 404 || errorMessage.includes('не существует') || errorMessage.includes('not found')) {
                tablesList.innerHTML = '<li class="text-muted">Нет таблиц</li>';
            } else {
                console.error('Error loading tables:', errorMessage);
                tablesList.innerHTML = '<li class="text-muted">Нет таблиц</li>';
                // Не показываем ошибку пользователю, чтобы не раздражать
            }
            return;
        }
        
        // Если response.ok = false, но success = true, все равно обрабатываем
        if (!response.ok && result.success !== true) {
            // Пытаемся получить детали ошибки
            const errorMessage = result.detail || result.error || 'Не удалось загрузить список таблиц';
            // Для любых ошибок просто показываем "Нет таблиц", чтобы не ломать UI
            console.error('Error loading tables:', errorMessage);
            tablesList.innerHTML = '<li class="text-muted">Нет таблиц</li>';
            return;
        }
        
        // Извлекаем список таблиц
        const tables = result.tables || result || [];
        tablesList.innerHTML = '';
        
        if (!tables || tables.length === 0) {
            tablesList.innerHTML = '<li class="text-muted">Нет таблиц</li>';
            return;
        }
        
        tables.forEach(table => {
            const tableName = typeof table === 'string' ? table : (table.name || table);
            const li = document.createElement('li');
            li.textContent = tableName;
            li.addEventListener('click', function() {
                // Убираем активный класс у всех
                tablesList.querySelectorAll('li').forEach(item => item.classList.remove('active'));
                // Добавляем активный класс текущему
                li.classList.add('active');
                currentTableName = tableName;
                loadTableData();
            });
            tablesList.appendChild(li);
        });
    } catch (error) {
        console.error('Error loading tables:', error);
        // В случае любой ошибки просто показываем "Нет таблиц"
        tablesList.innerHTML = '<li class="text-muted">Нет таблиц</li>';
    }
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
        
        // Показываем кнопки управления
        document.getElementById('add-row-btn').style.display = 'inline-block';
        document.getElementById('structure-btn').style.display = 'inline-block';
        document.getElementById('table-data-view').style.display = 'block';
        document.getElementById('empty-state').style.display = 'none';
        document.getElementById('current-table-name').textContent = currentTableName;
    } catch (error) {
        console.error('Error loading table data:', error);
        showError('Ошибка', 'Не удалось загрузить данные таблицы');
    }
}

// Отображение данных таблицы
function displayTableData() {
    if (!currentTableStructure || !currentTableData) return;
    
    const thead = document.getElementById('data-table-head');
    const tbody = document.getElementById('data-table-body');
    
    // Заголовки
    thead.innerHTML = '<tr><th>Действия</th>';
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

// Показать форму добавления строки
function showAddRowForm() {
    if (!currentTableStructure) return;
    
    const form = document.getElementById('add-row-form-content');
    form.innerHTML = '';
    
    currentTableStructure.columns.forEach(col => {
        if (col.pk && col.type === 'INTEGER' && col.notnull) {
            // Пропускаем автоинкрементные primary key
            return;
        }
        
        const formRow = document.createElement('div');
        formRow.className = 'form-row';
        
        const label = document.createElement('label');
        label.textContent = col.name + (col.notnull ? ' *' : '');
        label.className = 'text-white';
        
        let input;
        if (col.type === 'INTEGER') {
            input = document.createElement('input');
            input.type = 'number';
        } else if (col.type === 'REAL') {
            input = document.createElement('input');
            input.type = 'number';
            input.step = 'any';
        } else if (col.type === 'TEXT') {
            input = document.createElement('textarea');
            input.rows = 3;
        } else {
            input = document.createElement('input');
            input.type = 'text';
        }
        
        input.className = 'form-control form-control-sm';
        input.name = col.name;
        input.required = col.notnull;
        if (col.dflt_value !== null && col.dflt_value !== undefined) {
            input.value = col.dflt_value;
        }
        
        formRow.appendChild(label);
        formRow.appendChild(input);
        form.appendChild(formRow);
    });
    
    document.getElementById('add-row-form').style.display = 'block';
}

// Скрыть форму добавления строки
function hideAddRowForm() {
    document.getElementById('add-row-form').style.display = 'none';
    document.getElementById('add-row-form-content').innerHTML = '';
}

// Сохранение новой строки
async function saveNewRow() {
    if (!currentDbName || !currentTableName) return;
    
    const form = document.getElementById('add-row-form-content');
    const formData = new FormData(form);
    const rowData = {};
    
    for (const [key, value] of formData.entries()) {
        if (value.trim() !== '') {
            rowData[key] = value.trim();
        }
    }
    
    try {
        const response = await fetch(
            `/api/bots/${botId}/sqlite/tables/${encodeURIComponent(currentTableName)}/rows`,
            {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    row_data: rowData,
                    db_name: currentDbName
                })
            }
        );
        
        let result;
        try {
            result = await response.json();
        } catch (e) {
            console.error('Error parsing response:', e);
            showError('Ошибка', `Ошибка сервера: ${response.status} ${response.statusText}`);
            return;
        }
        
        if (!response.ok) {
            // Если response.ok = false, проверяем result.detail или result.error
            const errorMessage = result.detail || result.error || `Ошибка ${response.status}: ${response.statusText}`;
            showError('Ошибка', errorMessage);
            return;
        }
        
        if (result.success) {
            showSuccess('Успех', 'Строка успешно добавлена');
            hideAddRowForm();
            loadTableData();
        } else {
            showError('Ошибка', result.error || 'Не удалось добавить строку');
        }
    } catch (error) {
        console.error('Error saving new row:', error);
        showError('Ошибка', `Не удалось добавить строку: ${error.message || 'Неизвестная ошибка'}`);
    }
}

// Редактирование строки
function editRow(rowIndex) {
    if (!currentTableData || !currentTableData[rowIndex]) return;
    
    const row = currentTableData[rowIndex];
    editingRowId = row[primaryKeyColumn];
    
    const form = document.getElementById('edit-row-form');
    form.innerHTML = '';
    
    currentTableStructure.columns.forEach(col => {
        const formRow = document.createElement('div');
        formRow.className = 'form-row mb-3';
        
        const label = document.createElement('label');
        label.textContent = col.name + (col.pk ? ' (PK)' : '') + (col.notnull ? ' *' : '');
        label.className = 'text-white';
        
        let input;
        if (col.type === 'INTEGER') {
            input = document.createElement('input');
            input.type = 'number';
        } else if (col.type === 'REAL') {
            input = document.createElement('input');
            input.type = 'number';
            input.step = 'any';
        } else if (col.type === 'TEXT') {
            input = document.createElement('textarea');
            input.rows = 3;
        } else {
            input = document.createElement('input');
            input.type = 'text';
        }
        
        input.className = 'form-control';
        input.name = col.name;
        input.value = row[col.name] !== null && row[col.name] !== undefined ? row[col.name] : '';
        if (col.pk) {
            input.disabled = true;
            input.style.opacity = '0.6';
        }
        input.required = col.notnull && !col.pk;
        
        formRow.appendChild(label);
        formRow.appendChild(input);
        form.appendChild(formRow);
    });
    
    const modal = new bootstrap.Modal(document.getElementById('edit-row-modal'));
    modal.show();
}

// Сохранение редактируемой строки
async function saveEditRow() {
    if (!currentDbName || !currentTableName || editingRowId === null) return;
    
    const form = document.getElementById('edit-row-form');
    const formData = new FormData(form);
    const rowData = {};
    
    for (const [key, value] of formData.entries()) {
        if (!currentTableStructure.columns.find(col => col.name === key && col.pk)) {
            rowData[key] = value.trim();
        }
    }
    
    try {
        const response = await fetch(
            `/api/bots/${botId}/sqlite/tables/${encodeURIComponent(currentTableName)}/rows/${editingRowId}`,
            {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    row_data: rowData,
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
        console.error('Error saving edited row:', error);
        showError('Ошибка', 'Не удалось обновить строку');
    }
}

// Удаление строки
async function deleteRow(rowIndex) {
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
}

// Показать структуру таблицы
async function showStructure() {
    if (!currentDbName || !currentTableName) return;
    
    try {
        const response = await fetch(
            `/api/bots/${botId}/sqlite/databases/${encodeURIComponent(currentDbName)}/tables/${encodeURIComponent(currentTableName)}/structure`
        );
        if (!response.ok) throw new Error('Failed to load structure');
        
        const result = await response.json();
        const structure = result.structure || result;
        const content = document.getElementById('structure-content');
        
        let html = '<div class="mb-3">';
        html += '<button class="btn btn-sm btn-success" onclick="showAddColumnModal()">';
        html += '<i class="fas fa-plus"></i> Добавить столбец';
        html += '</button>';
        html += '</div>';
        html += '<table class="table table-dark table-striped"><thead><tr>';
        html += '<th>Имя</th><th>Тип</th><th>NOT NULL</th><th>Значение по умолчанию</th><th>Primary Key</th><th>Действия</th>';
        html += '</tr></thead><tbody>';
        
        structure.columns.forEach(col => {
            html += '<tr>';
            html += `<td>${col.name}</td>`;
            html += `<td>${col.type}</td>`;
            html += `<td>${col.notnull ? 'Да' : 'Нет'}</td>`;
            html += `<td>${col.dflt_value !== null ? col.dflt_value : '-'}</td>`;
            html += `<td>${col.pk ? 'Да' : 'Нет'}</td>`;
            html += `<td>`;
            if (!col.pk) {
                html += `<button class="btn btn-sm btn-danger" onclick="deleteColumn('${col.name}')">`;
                html += '<i class="fas fa-trash"></i> Удалить';
                html += '</button>';
            } else {
                html += '<span class="text-muted">-</span>';
            }
            html += `</td>`;
            html += '</tr>';
        });
        
        html += '</tbody></table>';
        content.innerHTML = html;
        
        document.getElementById('structure-view').style.display = 'block';
        document.getElementById('table-data-view').style.display = 'none';
        document.getElementById('query-results').style.display = 'none';
        document.getElementById('structure-table-name').textContent = currentTableName;
    } catch (error) {
        console.error('Error loading structure:', error);
        showError('Ошибка', 'Не удалось загрузить структуру таблицы');
    }
}

// Выполнение SQL запроса
async function executeQuery() {
    if (!currentDbName) {
        showWarning('Внимание', 'Выберите базу данных');
        return;
    }
    
    const query = window.sqlEditor.getValue().trim();
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
        const resultsDiv = document.getElementById('query-results');
        const contentDiv = document.getElementById('query-results-content');
        
        if (result.success) {
            if (result.type === 'select' && result.rows) {
                let html = `<div class="alert alert-success">Запрос выполнен успешно. Найдено строк: ${result.rows.length}</div>`;
                
                if (result.rows.length > 0) {
                    html += '<table class="table table-dark table-striped table-bordered"><thead><tr>';
                    Object.keys(result.rows[0]).forEach(key => {
                        html += `<th>${key}</th>`;
                    });
                    html += '</tr></thead><tbody>';
                    
                    result.rows.forEach(row => {
                        html += '<tr>';
                        Object.values(row).forEach(value => {
                            html += `<td>${value !== null ? value : ''}</td>`;
                        });
                        html += '</tr>';
                    });
                    
                    html += '</tbody></table>';
                }
                
                contentDiv.innerHTML = html;
            } else {
                contentDiv.innerHTML = `<div class="alert alert-success">Запрос выполнен успешно. Затронуто строк: ${result.affected_rows || 0}</div>`;
            }
            
            resultsDiv.style.display = 'block';
            document.getElementById('table-data-view').style.display = 'none';
            document.getElementById('structure-view').style.display = 'none';
        } else {
            contentDiv.innerHTML = `<div class="alert alert-danger">Ошибка: ${result.error || 'Неизвестная ошибка'}</div>`;
            resultsDiv.style.display = 'block';
        }
    } catch (error) {
        console.error('Error executing query:', error);
        showError('Ошибка', 'Не удалось выполнить запрос');
    }
}

// Скрыть данные таблицы
function hideTableData() {
    document.getElementById('table-data-view').style.display = 'none';
    document.getElementById('add-row-btn').style.display = 'none';
    document.getElementById('structure-btn').style.display = 'none';
    document.getElementById('empty-state').style.display = 'block';
}

// Показать модальное окно создания таблицы
function showCreateTableModal() {
    if (!currentDbName) {
        showWarning('Внимание', 'Выберите базу данных');
        return;
    }
    
    // Очищаем форму
    document.getElementById('new-table-name').value = '';
    document.getElementById('columns-list').innerHTML = '';
    
    // Добавляем первый столбец по умолчанию (обычно id)
    addColumnToForm('id', 'INTEGER', true, false, true);
    
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
                <input type="text" class="form-control form-control-sm" name="column_name" value="${name}" required>
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

// Удалить столбец из формы (глобальная функция для onclick)
window.removeColumnFromForm = function(button) {
    const columnItem = button.closest('.column-item');
    if (columnItem) {
        columnItem.remove();
        // Обновляем номера столбцов
        updateColumnNumbers();
    }
}

// Обновить номера столбцов
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

// Переключить AUTO INCREMENT при изменении Primary Key (глобальная функция для onclick)
window.toggleAutoIncrement = function(checkbox) {
    const columnItem = checkbox.closest('.column-item');
    const autoIncrementCheckbox = columnItem.querySelector('input[name="column_autoincrement"]');
    if (autoIncrementCheckbox) {
        autoIncrementCheckbox.disabled = !checkbox.checked;
        if (!checkbox.checked) {
            autoIncrementCheckbox.checked = false;
        }
    }
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
    
    // Собираем данные о столбцах
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
            // Если не удалось распарсить JSON, значит это ошибка сервера
            console.error('Error parsing response:', e);
            showError('Ошибка', `Ошибка сервера: ${response.status} ${response.statusText}`);
            return;
        }
        
        if (!response.ok) {
            // Если response.ok = false, проверяем result.detail или result.error
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

// Показать модальное окно добавления столбца (глобальная функция для onclick)
window.showAddColumnModal = function() {
    if (!currentDbName || !currentTableName) {
        showWarning('Внимание', 'Выберите таблицу');
        return;
    }
    
    // Очищаем форму
    document.getElementById('new-column-name').value = '';
    document.getElementById('new-column-type').value = 'TEXT';
    document.getElementById('new-column-notnull').checked = false;
    document.getElementById('new-column-default').value = '';
    
    const modal = new bootstrap.Modal(document.getElementById('add-column-modal'));
    modal.show();
}

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
            // Обновляем структуру и данные
            showStructure();
            if (document.getElementById('table-data-view').style.display !== 'none') {
                loadTableData();
            }
        } else {
            showError('Ошибка', result.error || 'Не удалось добавить столбец');
        }
    } catch (error) {
        console.error('Error adding column:', error);
        showError('Ошибка', 'Не удалось добавить столбец');
    }
}

// Удалить столбец из таблицы (глобальная функция для onclick)
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
            // Обновляем структуру и данные
            showStructure();
            if (document.getElementById('table-data-view').style.display !== 'none') {
                loadTableData();
            }
        } else {
            showError('Ошибка', result.error || 'Не удалось удалить столбец');
        }
    } catch (error) {
        console.error('Error deleting column:', error);
        showError('Ошибка', 'Не удалось удалить столбец');
    }
}

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


