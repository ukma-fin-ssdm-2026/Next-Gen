# PostgreSQL Backup та Restore

Інструкція для відтворюваного резервного копіювання та відновлення бази даних
PostgreSQL проєкту Baraholka NaUKMA відповідно до ADR-002 та вимоги REL-001.

## Підготовка

### Змінні середовища

```bash
# Встановіть відповідно до вашого .env
export POSTGRES_USER=baraholka
export POSTGRES_DB=baraholka
export POSTGRES_CONTAINER=next-gen-db-1   # ім'я контейнера з docker ps
export BACKUP_DIR=/var/backups/baraholka  # або зручна локальна директорія
```

---

## Backup (резервна копія)

### 1. Повний дамп через `pg_dump` (рекомендовано)

```bash
mkdir -p "$BACKUP_DIR"
docker exec "$POSTGRES_CONTAINER" \
    pg_dump \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --format=custom \
    --compress=9 \
    --no-password \
> "$BACKUP_DIR/baraholka_$(date +%Y%m%d_%H%M%S).dump"
```

> **Формат `--format=custom`** підтримує паралельне відновлення через `pg_restore -j`
> та вибіркове відновлення окремих таблиць (рекомендовано над `plain` SQL).

### 2. Backup лише схеми (для CI / code review)

```bash
docker exec "$POSTGRES_CONTAINER" \
    pg_dump \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --schema-only \
    --no-password \
> "$BACKUP_DIR/schema_$(date +%Y%m%d).sql"
```

### 3. Backup через Docker volume (cold backup)

```bash
# Зупинити API (не БД!) перед cold backup
docker compose stop api

docker run --rm \
    -v next-gen_postgres_data:/data:ro \
    -v "$BACKUP_DIR":/backup \
    alpine \
    tar czf /backup/volume_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .

docker compose start api
```

---

## Restore (відновлення)

### 1. Відновлення з `pg_dump --format=custom`

```bash
# 1. Зупинити API щоб уникнути конфліктів
docker compose stop api migrate

# 2. Відновлення (з паралельними потоками для швидкості)
docker exec -i "$POSTGRES_CONTAINER" \
    pg_restore \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --no-password \
    --clean \
    --if-exists \
    --jobs=2 \
< "$BACKUP_DIR/baraholka_YYYYMMDD_HHMMSS.dump"

# 3. Запустити API
docker compose start api
```

### 2. Відновлення на чисту базу (disaster recovery)

```bash
# Якщо базу потрібно повністю відновити з нуля:

# 1. Зупинити API
docker compose stop api migrate

# 2. Видалити та відтворити порожню базу
docker exec "$POSTGRES_CONTAINER" \
    psql --username "$POSTGRES_USER" \
    -c "DROP DATABASE IF EXISTS $POSTGRES_DB; CREATE DATABASE $POSTGRES_DB;"

# 3. Накатити Alembic-міграції (схема)
docker compose run --rm migrate

# 4. Відновити дані
docker exec -i "$POSTGRES_CONTAINER" \
    pg_restore \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --no-password \
    --data-only \
    --disable-triggers \
< "$BACKUP_DIR/baraholka_YYYYMMDD_HHMMSS.dump"

# 5. Запустити API
docker compose start api
```

---

## Alembic-міграції

### Розгортання порожньої бази з нуля

```bash
docker compose run --rm migrate
# або безпосередньо:
DATABASE_URL=postgresql+psycopg2://USER:PASS@HOST:5432/DB \
    python -m alembic upgrade head
```

### Rollback до бази до міграцій

```bash
DATABASE_URL=postgresql+psycopg2://USER:PASS@HOST:5432/DB \
    python -m alembic downgrade base
```

### Повторне застосування (upgrade → downgrade → upgrade)

```bash
export DATABASE_URL=postgresql+psycopg2://USER:PASS@HOST:5432/DB
python -m alembic upgrade head
python -m alembic downgrade base
python -m alembic upgrade head
```

---

## Автоматизований backup (cron)

Додайте до crontab на хості або в окремому сервісі:

```cron
# Щоденний backup о 03:00 UTC
0 3 * * * docker exec next-gen-db-1 pg_dump -U baraholka -Fc --no-password baraholka \
  > /var/backups/baraholka/baraholka_$(date +\%Y\%m\%d).dump 2>> /var/log/baraholka-backup.log
```

---

## Вимоги безпеки

- ❌ Не комітити `.env`, dump реальної бази чи приватні ключі.
- ❌ Порт PostgreSQL `5432` не публікується на зовнішньому інтерфейсі (compose.yaml: `expose`, не `ports`).
- ✅ Паролі передаються виключно через змінні середовища.
- ✅ Backup-файли повинні зберігатися поза репозиторієм, в захищеному місці.

---

> ### Нотатка «Використання ШІ»
> - **Інструмент:** Google Gemini (Antigravity).
> - **Етап:** Реалізація блоку PostgreSQL-persistence (ADR-002) — `feature/postgres-persistence`.
> - **Що згенеровано:** Структура розділів, команди `pg_dump`/`pg_restore`, сценарії disaster recovery та cron-приклад.
> - **Що перевірено / відкинуто вручну:** Усі команди звірено з документацією PostgreSQL 16; параметри `--format=custom`, `--jobs`, `--data-only`, `--disable-triggers` та `--clean --if-exists` перевірено на відповідність реальній поведінці `pg_restore`; структура відповідає вимозі ADR-002 та критерію прийняття «відтворювана команда backup і restore».
