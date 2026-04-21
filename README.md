# Airtable Local DB (Windows Desktop)

Полноценное локальное desktop-приложение на **Python 3.12 + PySide6 + SQLite** для замены связки Airtable/Excel при работе с оборудованием, перемещениями и рейсами.

## Возможности

- Импорт CSV/XLSX из Airtable и Excel.
- Слияние старых и новых выгрузок перемещений.
- Локальная SQLite БД с инициализацией при первом запуске.
- Основные сущности:
  - Оборудование
  - Перемещения
  - Рейсы (many-to-many с оборудованием)
- Жёсткая логика `serial_number -> inventory_number` (конфликты пишутся в журнал).
- Автоматический пересчёт `location_current` по последнему перемещению.
- Дедупликация перемещений по source-independent fingerprint.
- Перемещения и связи рейсов теперь сохраняются даже для serial_number, отсутствующих в equipment (как требуется бизнес-правилами импорта).
- Импорт в фоне (QThread) без блокировки UI.
- Фильтры, поиск, сортировка, экспорт текущего представления.
- Справочник статусов с расширением через UI.
- Журнал ошибок и конфликтов импорта.
- Backup/restore файла БД.

## Структура проекта

```text
project_root/
  app/
    main.py
    config.py
    db/
      database.py
      migrations.py
      schema.sql
    services/
      repository.py
      import_service.py
      export_service.py
      backup_service.py
    ui/
      main_window.py
      table_models.py
    utils/
      io_utils.py
  data/
  scripts/
    build_exe.bat
  requirements.txt
  run_app.bat
  README.md
```

## Установка зависимостей (Windows)

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Запуск приложения

Вариант 1 (из консоли):

```bat
.venv\Scripts\activate
python -m app.main
```

Вариант 2 (двойной клик):

- Запустите `run_app.bat`.

## Сборка EXE (PyInstaller)

```bat
scripts\build_exe.bat
```

Скрипт сборки автоматически добавляет `app/db/schema.sql` в дистрибутив, чтобы приложение корректно инициализировало БД после упаковки.

Результат:

```text
dist\AirtableLocalDB\AirtableLocalDB.exe
```

## Импорт ваших CSV/XLSX

1. Запустите приложение.
2. Откройте вкладку **Импорт**.
3. Последовательно загрузите:
   - импорт оборудования,
   - импорт перемещений (новых/старых),
   - импорт рейсов.
4. Для CSV поддержаны:
   - UTF-8,
   - UTF-8 BOM,
   - cp1251,
   - автоопределение разделителя `,` или `;`.

## Логика работы

- `equipment.serial_number` — главный ключ.
- Если у существующего `serial_number` в новом импорте другой `inventory_number`, строка не перезаписывается, создаётся конфликт в `import_errors`.
- Перемещения нормализуются по правилу `1 запись = 1 прибор` (разбор multi-value полей).
- Последнее перемещение по дате обновляет `equipment.location_current`.
- Рейсы и приборы связаны через `trip_equipment`.
- Все импорты пишутся в `import_batches` с агрегированной статистикой.

## База данных

Схема и индексы находятся в `app/db/schema.sql`.

Основные таблицы:

- `equipment`
- `movements`
- `trips`
- `trip_equipment`
- `statuses`
- `locations`
- `import_batches`
- `import_errors`

Инициализация/миграция при старте выполняется автоматически.

## Примечания по установке и SSL

Если в вашей сети появляются SSL-предупреждения при проверке обновлений pip (например, `SSLEOFError` к `https://pypi.org/simple/pip/`), это обычно не мешает установке уже доступных пакетов.

В проекте отключена проверка обновлений pip в `.bat`-скриптах (`PIP_DISABLE_PIP_VERSION_CHECK=1`), чтобы убрать лишние предупреждения во время сборки.

## Примечания по производительности

- SQLite в WAL-режиме.
- Индексы на ключевых полях (`serial_number`, `inventory_number`, `location_current`, `status`, `movement_date`, `trip_name`).
- Импорт выполняется транзакционно.
- UI использует табличную модель Qt и ограничение выборки для быстрого открытия больших таблиц.
