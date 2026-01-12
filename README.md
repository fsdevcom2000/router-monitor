# English / # Russian
# **Routers | MikroTik — Web Monitoring & Management System**
<img width="1919" height="1079" alt="image-1" src="https://github.com/user-attachments/assets/1c4067a8-97fb-486d-8349-0bae7e33c603" />

## **About the Project**

Routers | MikroTik is a full-featured web platform for monitoring and administering MikroTik devices. The application provides a centralized dashboard for tracking device status, along with a comprehensive set of management tools — from adding/editing routers to an integrated SSH terminal and Telegram notifications.

## **Features**

### **Architecture**

- **Clean separation of concerns** — a modular structure (router_manager.py, state.py, notifications.py, pages.py) keeps the code maintainable and testable.
    
- **Asynchronous at every level** — from loading routers from the database (asyncio.to_thread) to WebSocket connections and background status update tasks.
    
- **State management system** — RouterManager with internal caching and locks (asyncio.Lock) ensures safe concurrent access.
    
- **Application lifecycle** — FastAPI lifespan is used to properly start and stop background tasks, WebSocket handlers, and Telegram workers.
    

## **Security**

### **Two-level password protection**

- Router passwords are encrypted with **Fernet** (symmetric encryption) before being stored in the database.
    
- User passwords are hashed with **bcrypt** and salt.
    

### **Role-based access control**

Two roles: **admin** and **viewer**, validated on every endpoint.

### **WebSocket tokens**

One-time tokens with TTL to authorize WebSocket connections and prevent unauthorized access.

### **Notification deduplication**

- DOWN alerts only after **3 consecutive failed checks**
    
- Reconnect alerts every **+50 reconnects**
    

## **Monitoring & Notifications**

### **Metric collection from MikroTik**

- Automatic WAN interface detection (via routes, ARP, DHCP, PPPoE, LTE).
    
- Real-time traffic speed calculation (1-second sampling).
    
- Support for RouterOS **v6 and v7** (different paths for temperature/voltage).
    
- Intelligent external IPv4 detection (Cloud, interfaces, gateway).
    

### **Telegram notifications with queue**

Asynchronous worker with retry logic (1–3–5 seconds backoff) and multi-chat delivery.

### **WebSocket real-time updates**

The dashboard updates automatically without page reloads.

### **Log streaming to browser**

A dedicated WebSocket channel streams server logs in real time.

## **User Interface**

- **Built-in SSH terminal** — full xterm.js terminal with MikroTik-specific handling (\r\n, pty resize).
    
- **Responsive design** with light/dark theme (theme.js).
    
- **Custom error pages** (404, 500) with JSON/HTML content detection.
    
- **First login flow** — automatic creation of the initial admin user.
    

## **Administrative Features**

- Full CRUD for routers and users via web interface.
    
- Forced router list reload without restarting the app.
    
- Real-time server logs in a separate window.
    
- Direct WebFig links — automatic protocol and port detection.
    

## **Project Structure**

Код

```
routers-mikrotik/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI entry point, lifespan
│   ├── crypto.py            # Password encryption (Fernet)
│   ├── db.py                # SQLite operations, bcrypt hashing
│   ├── log_stream.py        # WebSocket handler for logs
│   ├── mikrotik.py          # Core logic for MikroTik API interaction
│   ├── models.py            # Data classes
│   ├── models.sql           # Database schema
│   ├── notifications.py     # Telegram worker with queue
│   ├── pages.py             # All endpoints and templates
│   ├── router_manager.py    # Router manager with caching
│   └── state.py             # Background status updates, WebSocket
├── templates/               # HTML templates
├── static/                  # CSS, JS, images
├── requirements.txt         # Dependencies
├── run.py                   # Development run script
└── routers.db               # SQLite database (created automatically)
```

## **Quick Start**

### **1. Install dependencies**

Код

```
pip install -r requirements.txt
```

### **2. Configure environment variables**

Create a `.env` file in the project root.

**Required**

Код

```
FERNET_KEY=your_fernet_key_here
# generate with: from cryptography.fernet import Fernet; Fernet.generate_key()
SESSION_SECRET=your_session_secret_here
```

**Optional (Telegram notifications)**

Код

```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=chat_id1,chat_id2
```

**Optional (application port)**

Код

```
PORT=5000
```

### **3. Initialize the database**

The database is created automatically on first run.

### **4. Run**

**Development:**

Код

```
python3 run.py
```

**Production:**

Код

```
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-5000} --workers 2 --log-level info --access-log
```

### **5. First Login**

- Open: `http://IP:5000`
    
- The system will prompt you to create the first user (assigned the **admin** role).
    
- Log in with the created credentials.
    

## **📊 Dashboard Features**

For each router, the dashboard displays:

- Status (Online/Offline)
    
- Model and ROS version
    
- External IP address
    
- CPU and RAM usage
    
- Temperature and voltage (if supported)
    
- WAN traffic speed (in/out)
    
- Human-readable uptime (e.g., 3d 5h 20min)
    
- Reconnect counter
    
- Direct WebFig link
    

## **Administration**

### **Router Management** (`/admin/routers`)

- Add, edit, delete routers
    
- Enable/disable monitoring
    
- Force reload router list
    

### **User Management** (`/admin/users`)

- Create users with admin/viewer roles
    
- Change passwords and roles
    
- Protection from deleting the last admin
    

### **SSH Terminal** (`/router/{name}/terminal`)

- Full CLI access via browser
    
- Supports all MikroTik commands
    
- Correct handling of special characters and terminal resize
    

### **Server Logs** (`/admin/logs`)

- Real-time uvicorn/FastAPI logs
    
- Useful for debugging and monitoring
    

## **MikroTik Integration**

### **Supported access methods**

- **API (port 8728)** via librouteros — for metrics
    
- **SSH (port 22)** via paramiko — for terminal
    

### **Automatic configuration detection**

- WAN interface (via default route)
    
- Connection type (PPPoE, LTE, DHCP, Static)
    
- Web interface (HTTP/HTTPS, port)
    
- Hardware metrics (temperature, voltage)
    

## **Configuration**

### **Telegram notifications**

1. Create a bot via **@BotFather**
    
2. Add token to `TELEGRAM_BOT_TOKEN`
    
3. Get your chat ID (e.g., via @userinfobot)
    
4. Add it to `TELEGRAM_CHAT_ID` (comma-separated for multiple chats)
    

### **Notification policy**

- **DOWN** — sent only after 3 consecutive failed checks
    
- **UP** — sent immediately after recovery
    
- **Reconnects** — alert every +50 reconnects
    

## **Security**

### **Production recommendations**

- Change default `.env` values
    
- Use HTTPS (via reverse proxy: nginx/Caddy)
    
- Restrict access to the app port via firewall
    
- Regularly update dependencies
    
- Set up backups for `routers.db`
    

## **Debugging**

### **Useful endpoints**

- `/ws-token` — get WebSocket token
    
- `/admin/reload-routers` — force reload router list
    
- `/admin/logs` — live server logs
    

### **Logging**

Logs are printed to console and available via WebSocket `/ws/logs`. Logging level is configured when starting uvicorn.

# Routers | MikroTik - Web Monitoring & Management System

## О проекте

**Routers | MikroTik** — это полнофункциональная веб-платформа для мониторинга и администрирования устройств MikroTik. Приложение предоставляет централизованный дашборд для отслеживания состояния устройств, а также комплексный набор инструментов для управления: от добавления/редактирования роутеров до встроенного терминала SSH и Telegram-уведомлений.

## Особенности

### **Архитектурные решения**

1. **Чистое разделение ответственности** — модульная структура (`router_manager.py`, `state.py`, `notifications.py`, `pages.py`) делает код поддерживаемым и тестируемым.
    
2. **Асинхронность на всех уровнях** — от загрузки роутеров из БД (`asyncio.to_thread`) до WebSocket-соединений и фоновых задач обновления статуса.
    
3. Система управления состоянием** — `RouterManager` с внутренним кэшированием и блокировками (`asyncio.Lock`) для безопасного доступа из множества корутин.
    
4. Жизненный цикл приложения** — использование `lifespan` в FastAPI для корректного запуска и остановки фоновых задач, WebSocket-соединений и воркеров Telegram.

### **Безопасность**

1. **Двухуровневое шифрование паролей**:
    
    - Пароли роутеров шифруются `Fernet` (симметричное шифрование) перед сохранением в БД.
        
    - Пароли пользователей хешируются `bcrypt` с солью.
        
2. **Ролевая модель доступа** — разделение на `admin` и `viewer` с проверкой на каждом эндпоинте.
    
3. **Токены для WebSocket** — одноразовые токены с TTL для авторизации WebSocket-соединений, предотвращающие несанкционированный доступ к потоку данных.
    
4. **Защита от повторной отправки уведомлений** — логика "только после 3 проверок подряд" для DOWN и порог в 50 переподключений для алертов.

### **Мониторинг и уведомления**

1. **Сбор метрик с MikroTik**:
    
    - Автоопределение WAN-интерфейса (через анализ маршрутов, ARP, DHCP, PPPoE, LTE).
        
    - Расчет скорости трафика в реальном времени (задержка 1 секунда между замерами).
        
    - Поддержка как RouterOS v6, так и v7 (разные пути для получения температуры/напряжения).
        
    - Интеллектуальный поиск внешнего IPv4 (через Cloud, интерфейсы, шлюз).
        
2. **Telegram-уведомления с очередью сообщений** — асинхронный воркер с retry-логикой (backoff 1-3-5 секунд) и отправкой в несколько чатов.
    
3. **WebSocket для real-time обновлений** — дашборд автоматически обновляется без перезагрузки страницы.
    
4. **Стриминг логов в браузер** — отдельный WebSocket-канал для мониторинга логов сервера в реальном времени.

###  **Пользовательский интерфейс**

1. **Встроенный терминал SSH** — полноценный терминал на базе xterm.js с поддержкой специфики MikroTik (отправка `\r\n`, изменение размера pty).
    
2. **Адаптивный дизайн** с поддержкой светлой/темной темы (через `theme.js`).
    
3. **Кастомные страницы ошибок** (404, 500) с определением типа контента (JSON/HTML).
    
4. **"Первый вход"** — автоматическое создание администратора при первом запуске приложения.

### **Административные функции**

1. **Полный CRUD для роутеров и пользователей** через веб-интерфейс.
    
2. **Принудительная перезагрузка списка роутеров** без перезапуска приложения.
    
3. **Просмотр логов сервера** в реальном времени в отдельном окне.
    
4. **Прямые ссылки на WebFig** — автоматическое определение протокола и порта веб-интерфейса роутера.

## Структура проекта

```
routers-mikrotik/
├── app/
│   ├── __init__.py
│   ├── main.py              # Точка входа FastAPI, lifespan
│   ├── crypto.py            # Шифрование паролей (Fernet)
│   ├── db.py                # Работа с SQLite, хеширование bcrypt
│   ├── log_stream.py        # WebSocket-хендлер для логов
│   ├── mikrotik.py          # Основная логика работы с API MikroTik
│   ├── models.py            # Data-классы
│   ├── models.sql           # Схема БД
│   ├── notifications.py     # Telegram-воркер с очередью
│   ├── pages.py             # Все эндпоинты и шаблоны
│   ├── router_manager.py    # Менеджер роутеров с кэшированием
│   └── state.py             # Фоновое обновление статуса, WebSocket
├── templates/               # HTML-шаблоны
├── static/                  # CSS, JS, изображения
├── requirements.txt         # Зависимости
├── run.py                   # Скрипт запуска для разработки
└── routers.db               # База данных SQLite (создается автоматически)
```
##  Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте файл `.env` в корне проекта:

# Обязательные

```
FERNET_KEY=your_fernet_key_here  
# сгенерировать: from cryptography.fernet import Fernet; Fernet.generate_key()
SESSION_SECRET=your_session_secret_here
```

# Опционально (для Telegram уведомлений)

```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=chat_id1,chat_id2
```

# Опционально (порт приложения)

```
PORT=5000
```

### 3. Инициализация базы данных

База данных создается автоматически при первом запуске.

### 4. Запуск

#### Для разработки:

```
python3 run.py
```

#### Для production:

```
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-5000} --workers 2 --log-level info --access-log
```

### 5. Первый вход

1. Откройте `http://IP:5000`
    
2. Система предложит создать первого пользователя (автоматически получает роль `admin`)
    
3. Войдите с созданными учетными данными
    

## 📊 Возможности дашборда

Для каждого роутера отображается:

- **Статус** (Online/Offline)
    
- **Модель и версия ROS**
    
- **Внешний IP-адрес**
    
- **Загрузка CPU и памяти**
    
- **Температура и напряжение** (если поддерживается)
    
- **Скорость WAN-трафика** (вход/выход)
    
- **Аптайм** в удобном формате (3d 5h 20min)
    
- **Счетчик переподключений** (для диагностики проблемных роутеров)
    
- **Прямая ссылка** на WebFig роутера
    

## Администрирование

### Управление роутерами (`/admin/routers`)

- Добавление, редактирование, удаление роутеров
    
- Включение/отключение мониторинга
    
- Принудительная перезагрузка списка
    

### Управление пользователями (`/admin/users`)

- Создание пользователей с ролями `admin` или `viewer`
    
- Смена паролей и ролей
    
- Защита от удаления последнего администратора
    

### Терминал SSH (`/router/{name}/terminal`)

- Полноценный доступ к CLI роутера через браузер
    
- Поддержка всех команд MikroTik
    
- Корректная обработка спецсимволов и resize терминала
    

### Логи сервера (`/admin/logs`)

- Real-time просмотр логов uvicorn/FastAPI
    
- Полезно для отладки и мониторинга работы приложения
    

## Интеграция с MikroTik

### Поддерживаемые методы доступа:

1. **API на порту 8728** (основной, через librouteros) — для сбора метрик
    
2. **SSH на порту 22** (через paramiko) — для терминала
    

### Автоопределение конфигурации:

- WAN-интерфейс (через default route)
    
- Тип подключения (PPPoE, LTE, DHCP, Static)
    
- Веб-интерфейс (HTTP/HTTPS, порт)
    
- Метрики оборудования (температура, напряжение)
    

## Конфигурация

### Настройка уведомлений в Telegram

1. Создайте бота через [@BotFather](https://t.me/botfather)
    
2. Получите токен и добавьте в `TELEGRAM_BOT_TOKEN`
    
3. Узнайте свой ID чата (можно через [@userinfobot](https://t.me/userinfobot))
    
4. Добавьте ID в `TELEGRAM_CHAT_ID` (можно несколько через запятую)
    

### Политика уведомлений

- **DOWN** — отправляется только после 3 последовательных неудачных проверок
    
- **UP** — отправляется сразу при восстановлении после DOWN
    
- **Переподключения** — алерт каждые +50 переподключений (индикатор нестабильности)
    

## Безопасность

### Рекомендации для production:

1. **Измените значения по умолчанию** в `.env`
    
2. **Используйте HTTPS** (через reverse proxy: nginx/Caddy)
    
3. **Ограничьте доступ** к порту приложения firewall
    
4. **Регулярно обновляйте** зависимости
    
5. **Настройте резервное копирование** `routers.db`
    

## Отладка

### Полезные эндпоинты:

- `/ws-token` — получение токена для WebSocket (для отладки)
    
- `/admin/reload-routers` — принудительная перезагрузка списка роутеров
    
- `/admin/logs` — live-логи сервера
    

### Логирование:

Логи пишутся в консоль и доступны через WebSocket `/ws/logs`. Уровень логирования настраивается при запуске uvicorn.
