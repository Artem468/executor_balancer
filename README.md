# Executor Balancer

Сервис для распределения заявок между пользователями с использованием Django, MongoDB, Celery и Redis.

---

## Требования

- Python 3.12+
- Docker & Docker Compose
- MongoDB
- Redis
- RabbitMQ

---

## Установка и запуск через Docker

### 1. Склонировать репозиторий:

```bash
git clone https://github.com/Artem468/executor_balancer
cd executor_balancer
```

### 2. Создать .env файл (пример):

```
DEBUG=True
SECRET_KEY=supersecretkey
ALLOWED_HOSTS=*

MONGO_USER=admin
MONGO_PASS=pass
MONGO_HOST=mongo
MONGO_PORT=27017
MONGO_DB=executor_balancer

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_CHANNELS=1

RABBITMQ_DEFAULT_USER=guest
RABBITMQ_DEFAULT_PASS=guest
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672

CELERY_TASK_ACKS_LATE=True
CELERY_TASK_TRACK_STARTED=True
CELERY_TIMEZONE=UTC
```

### 3. Запустить контейнеры:

```docker-compose up --build -d```

### 4. После успешного запуска всех сервисов станут доступны:

| Сервис     | URL / Порт                                 | Описание                             |
|------------|--------------------------------------------|--------------------------------------|
| Django API | [ТЫК](http://127.0.0.1:8000)               | Основной REST API                    |
| Swagger    | [ЖМЯК](http://127.0.0.1:8000/swagger)      | Удобный просмотр доступных API ручек |
| Health     | [ЩЕЛК](http://127.0.0.1:8000/core/health/) | Проверка доступности контейнеров     |
