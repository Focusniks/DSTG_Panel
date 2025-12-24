-- SQL запросы для создания тестовых таблиц с данными
-- Выполните эти запросы по порядку в SQL редакторе

-- Таблица 1: Пользователи (users)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    age INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

INSERT INTO users (username, email, age, is_active) VALUES
('alice', 'alice@example.com', 25, 1),
('bob', 'bob@example.com', 30, 1),
('charlie', 'charlie@example.com', 28, 0),
('diana', 'diana@example.com', 32, 1),
('eve', 'eve@example.com', 24, 1),
('frank', 'frank@example.com', 29, 1),
('grace', 'grace@example.com', 27, 0),
('henry', 'henry@example.com', 35, 1),
('iris', 'iris@example.com', 26, 1),
('jack', 'jack@example.com', 31, 1),
('kate', 'kate@example.com', 23, 1),
('liam', 'liam@example.com', 33, 1),
('mia', 'mia@example.com', 22, 1),
('noah', 'noah@example.com', 34, 1),
('olivia', 'olivia@example.com', 28, 0);

-- Таблица 2: Продукты (products)
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER DEFAULT 0,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO products (name, category, price, stock, description) VALUES
('Ноутбук', 'Электроника', 59999.99, 15, 'Игровой ноутбук с RTX 4060'),
('Смартфон', 'Электроника', 29999.99, 25, 'Флагманский смартфон'),
('Наушники', 'Электроника', 4999.99, 50, 'Беспроводные наушники'),
('Клавиатура', 'Периферия', 2999.99, 30, 'Механическая клавиатура'),
('Мышь', 'Периферия', 1999.99, 40, 'Игровая мышь'),
('Монитор', 'Электроника', 24999.99, 20, '27 дюймов 4K монитор'),
('Стол', 'Мебель', 8999.99, 10, 'Офисный стол'),
('Стул', 'Мебель', 5999.99, 15, 'Эргономичное кресло'),
('Книга', 'Книги', 599.99, 100, 'Программирование на Python'),
('Рюкзак', 'Аксессуары', 2999.99, 25, 'Рюкзак для ноутбука'),
('Флешка', 'Электроника', 799.99, 60, 'USB 3.0 64GB'),
('Веб-камера', 'Периферия', 3999.99, 20, 'Full HD веб-камера'),
('Колонки', 'Электроника', 8999.99, 12, 'Стерео колонки'),
('Планшет', 'Электроника', 19999.99, 18, '10-дюймовый планшет'),
('Чехол', 'Аксессуары', 1499.99, 35, 'Защитный чехол для смартфона');

-- Таблица 3: Заказы (orders)
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    status TEXT DEFAULT 'pending',
    order_date TEXT DEFAULT CURRENT_TIMESTAMP,
    shipping_address TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

INSERT INTO orders (user_id, total_amount, status, shipping_address) VALUES
(1, 59999.99, 'completed', 'Москва, ул. Ленина, д. 1'),
(2, 29999.99, 'pending', 'СПб, Невский пр., д. 10'),
(1, 4999.99, 'completed', 'Москва, ул. Ленина, д. 1'),
(3, 8999.99, 'shipped', 'Екатеринбург, пр. Мира, д. 5'),
(4, 24999.99, 'completed', 'Новосибирск, ул. Красная, д. 20'),
(5, 2999.99, 'pending', 'Казань, ул. Баумана, д. 15'),
(2, 5999.99, 'completed', 'СПб, Невский пр., д. 10'),
(6, 1999.99, 'cancelled', 'Ростов-на-Дону, пр. Буденновский, д. 30'),
(7, 8999.99, 'completed', 'Уфа, ул. Ленина, д. 50'),
(8, 3999.99, 'shipped', 'Краснодар, ул. Красная, д. 100'),
(9, 19999.99, 'pending', 'Воронеж, пр. Революции, д. 25'),
(10, 1499.99, 'completed', 'Самара, ул. Московская, д. 40'),
(11, 599.99, 'completed', 'Омск, пр. Мира, д. 60'),
(12, 24999.99, 'shipped', 'Челябинск, ул. Кирова, д. 70'),
(1, 799.99, 'pending', 'Москва, ул. Ленина, д. 1');

-- Таблица 4: Статьи блога (posts)
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    author_id INTEGER NOT NULL,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    published INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES users(id)
);

INSERT INTO posts (title, content, author_id, views, likes, published) VALUES
('Введение в Python', 'Python - это высокоуровневый язык программирования...', 1, 1250, 45, 1),
('Основы SQL', 'SQL используется для работы с базами данных...', 2, 980, 32, 1),
('JavaScript для начинающих', 'JavaScript - язык программирования для веба...', 1, 750, 28, 1),
('Git и GitHub', 'Git - система контроля версий...', 3, 650, 25, 1),
('CSS Grid и Flexbox', 'Современные способы верстки...', 4, 520, 20, 1),
('Алгоритмы и структуры данных', 'Важные концепции программирования...', 2, 450, 18, 1),
('REST API разработка', 'Как создавать RESTful API...', 5, 380, 15, 1),
('Docker контейнеры', 'Контейнеризация приложений...', 6, 320, 12, 1),
('Асинхронное программирование', 'Параллельное выполнение задач...', 1, 280, 10, 1),
('Базы данных NoSQL', 'MongoDB, Redis и другие...', 7, 250, 9, 1),
('Машинное обучение', 'Введение в ML и AI...', 8, 220, 8, 1),
('Безопасность веб-приложений', 'Защита от уязвимостей...', 2, 200, 7, 1),
('Микросервисная архитектура', 'Проектирование распределенных систем...', 9, 180, 6, 1),
('Тестирование кода', 'Unit, Integration, E2E тесты...', 10, 150, 5, 1),
('DevOps практики', 'CI/CD и автоматизация...', 11, 130, 4, 0);

-- Таблица 5: Комментарии (comments)
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    likes INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

INSERT INTO comments (post_id, user_id, content, likes) VALUES
(1, 2, 'Отличная статья! Спасибо за подробное объяснение.', 5),
(1, 3, 'Очень полезно для новичков. Жду продолжения!', 3),
(2, 1, 'Хороший материал по SQL. Добавьте больше примеров.', 4),
(2, 4, 'Спасибо, помогло разобраться с JOIN.', 2),
(3, 5, 'JavaScript это мощно! Отличный туториал.', 6),
(3, 2, 'Можно добавить информацию про async/await?', 1),
(4, 6, 'Git это основа работы программиста. Спасибо!', 7),
(4, 1, 'Полезная информация. Рекомендую всем прочитать.', 5),
(5, 7, 'CSS Grid изменил мою жизнь!', 8),
(5, 3, 'Flexbox тоже хорош, но Grid удобнее для сложных макетов.', 4),
(6, 8, 'Алгоритмы - это фундамент. Важная тема!', 6),
(6, 4, 'Хорошо объяснено. Жду про деревья и графы.', 3),
(7, 9, 'REST API это must-know для любого разработчика.', 5),
(7, 2, 'Отличная статья! Когда будет про GraphQL?', 2),
(1, 5, 'Python - лучший язык для начинающих!', 9);

