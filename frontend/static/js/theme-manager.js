// Менеджер тем для панели управления ботами

class ThemeManager {
    constructor() {
        this.currentTheme = 'dark';
        this.customThemes = {};
        this.init();
    }

    init() {
        // Загружаем сохраненную тему
        const savedTheme = localStorage.getItem('panel-theme');
        if (savedTheme) {
            this.setTheme(savedTheme);
        } else {
            this.setTheme('dark');
        }

        // Загружаем пользовательские темы
        this.loadCustomThemes();
    }

    setTheme(themeName) {
        if (themeName === 'custom') {
            // Применяем пользовательскую тему
            const customTheme = this.customThemes[localStorage.getItem('panel-custom-theme-name') || 'custom'];
            if (customTheme) {
                this.applyCustomTheme(customTheme);
            } else {
                console.warn('Пользовательская тема не найдена, используем темную');
                themeName = 'dark';
            }
        }

        // Удаляем все классы тем
        document.documentElement.removeAttribute('data-theme');
        
        // Устанавливаем новую тему
        document.documentElement.setAttribute('data-theme', themeName);
        this.currentTheme = themeName;
        
        // Сохраняем выбор
        localStorage.setItem('panel-theme', themeName);

        // Создаем/удаляем эффекты для новогодней темы
        if (themeName === 'christmas') {
            this.createChristmasEffects();
        } else {
            this.removeChristmasEffects();
        }

        // Вызываем событие изменения темы
        window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: themeName } }));
    }

    createChristmasEffects() {
        // Удаляем старые эффекты, если есть
        this.removeChristmasEffects();

        // Создаем контейнер для снега
        const snowContainer = document.createElement('div');
        snowContainer.className = 'snow-container';
        snowContainer.id = 'snow-container';
        
        // Создаем снежинки
        const snowflakes = ['❄', '❅', '❆'];
        for (let i = 0; i < 50; i++) {
            const snowflake = document.createElement('div');
            snowflake.className = 'snowflake';
            snowflake.textContent = snowflakes[Math.floor(Math.random() * snowflakes.length)];
            snowflake.style.left = Math.random() * 100 + '%';
            snowflake.style.animationDuration = (Math.random() * 3 + 2) + 's';
            snowflake.style.animationDelay = Math.random() * 2 + 's';
            snowflake.style.fontSize = (Math.random() * 10 + 10) + 'px';
            snowContainer.appendChild(snowflake);
        }
        document.body.appendChild(snowContainer);

        // Создаем гирлянду
        const garland = document.createElement('div');
        garland.className = 'garland';
        garland.id = 'garland';
        
        const lightCount = Math.floor(window.innerWidth / 20);
        for (let i = 0; i < lightCount; i++) {
            const light = document.createElement('div');
            light.className = 'garland-light';
            light.style.left = (i * (100 / lightCount)) + '%';
            light.style.top = Math.random() * 30 + 'px';
            light.style.animationDelay = (Math.random() * 1.5) + 's';
            garland.appendChild(light);
        }
        document.body.appendChild(garland);
    }

    removeChristmasEffects() {
        const snowContainer = document.getElementById('snow-container');
        if (snowContainer) {
            snowContainer.remove();
        }
        const garland = document.getElementById('garland');
        if (garland) {
            garland.remove();
        }
    }

    saveCustomTheme(themeName, themeData) {
        this.customThemes[themeName] = themeData;
        localStorage.setItem('panel-custom-themes', JSON.stringify(this.customThemes));
        localStorage.setItem('panel-custom-theme-name', themeName);
    }

    loadCustomThemes() {
        const saved = localStorage.getItem('panel-custom-themes');
        if (saved) {
            try {
                this.customThemes = JSON.parse(saved);
            } catch (e) {
                console.error('Ошибка загрузки пользовательских тем:', e);
                this.customThemes = {};
            }
        }
    }

    applyCustomTheme(themeData) {
        const root = document.documentElement;
        Object.keys(themeData).forEach(key => {
            if (key.startsWith('--')) {
                root.style.setProperty(key, themeData[key]);
            }
        });
    }

    getAvailableThemes() {
        return [
            { id: 'dark', name: 'Темная', icon: '🌙' },
            { id: 'light', name: 'Светлая', icon: '☀️' },
            { id: 'christmas', name: 'Новогодняя', icon: '🎄' },
            { id: 'minimal', name: 'Минималистичная', icon: '⚪' },
            { id: 'neon', name: 'Неоновая', icon: '💡' },
            ...Object.keys(this.customThemes).map(name => ({
                id: 'custom',
                name: name,
                icon: '🎨',
                customName: name
            }))
        ];
    }

    exportTheme(themeName) {
        if (themeName === 'custom') {
            const customName = localStorage.getItem('panel-custom-theme-name');
            return this.customThemes[customName] || null;
        }
        
        // Экспортируем текущие CSS переменные
        const root = document.documentElement;
        const computedStyle = getComputedStyle(root);
        const theme = {};
        
        const cssVars = [
            '--neon-cyan', '--neon-purple', '--neon-pink', '--neon-green',
            '--neon-blue', '--neon-orange', '--neon-yellow',
            '--bg-primary', '--bg-secondary', '--bg-tertiary', '--bg-card',
            '--bg-hover', '--bg-overlay',
            '--text-primary', '--text-secondary', '--text-muted',
            '--border-color', '--border-neon'
        ];
        
        cssVars.forEach(varName => {
            theme[varName] = computedStyle.getPropertyValue(varName).trim();
        });
        
        return theme;
    }

    importTheme(themeName, themeData) {
        this.saveCustomTheme(themeName, themeData);
        if (this.currentTheme === 'custom' && localStorage.getItem('panel-custom-theme-name') === themeName) {
            this.setTheme('custom');
        }
    }

    deleteCustomTheme(themeName) {
        delete this.customThemes[themeName];
        localStorage.setItem('panel-custom-themes', JSON.stringify(this.customThemes));
        if (localStorage.getItem('panel-custom-theme-name') === themeName) {
            this.setTheme('dark');
        }
    }
}

// Создаем глобальный экземпляр менеджера тем
window.themeManager = new ThemeManager();

