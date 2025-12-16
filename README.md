# Docling OCR Server

FastAPI сервер для конвертации документов в Markdown с использованием Docling и Tesseract OCR.

## Возможности

- **Поддерживаемые форматы**: PDF, DOCX, DOC, XLSX, XLS, JPG, PNG
- **OCR**: Распознавание текста на русском и английском языках (Tesseract)
- **Таблицы и Layout**: Автоматическое распознавание таблиц и структуры документа
- **Гибридный экспорт таблиц**: Автоматический выбор между Markdown и HTML для таблиц
- **Асинхронная обработка**: Задачи обрабатываются в фоновом режиме
- **Автоматическая очистка**: Временные файлы удаляются через заданный TTL

## Быстрый старт

### Docker Compose (рекомендуется)

```bash
# Клонировать репозиторий
git clone <repository-url>
cd DoclingOCRServer

# Запустить сервер
docker-compose up -d

# Проверить статус
curl http://localhost:8000/
```

### Docker

```bash
# Сборка образа
docker build -t docling-ocr-server .

# Запуск контейнера
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/temp_storage:/tmp/docling_storage \
  -e TTL_HOURS=24 \
  -e MAX_FILE_SIZE_MB=50 \
  docling-ocr-server
```

### Локальная разработка

```bash
# Установить системные зависимости (Ubuntu/Debian)
sudo apt-get install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng poppler-utils

# Установить Python зависимости
pip install -r requirements.txt

# Создать .env файл
cp .env.example .env

# Запустить сервер
python main.py
```

## API Endpoints

### 1. Загрузка документа для обработки

```bash
POST /documents/process
```

**Параметры:**
- `file` - файл документа (обязательный)
- `force_ocr` - принудительный OCR всего документа (необязательный, по умолчанию `false`)
- `table_format` - формат экспорта таблиц (необязательный, по умолчанию `auto`)
  - `auto` - автоматический выбор формата на основе сложности таблицы (рекомендуется)
  - `markdown` - все таблицы в Markdown (простой формат)
  - `html` - все таблицы в HTML (сохраняет сложную структуру, объединённые ячейки)

**Пример запроса (стандартная обработка):**

```bash
curl -X POST "http://localhost:8000/documents/process" \
  -F "file=@document.pdf"
```

**Пример запроса (с принудительным OCR):**

```bash
curl -X POST "http://localhost:8000/documents/process" \
  -F "file=@document.pdf" \
  -F "force_ocr=true"
```

**Пример запроса (с таблицами в HTML):**

```bash
curl -X POST "http://localhost:8000/documents/process" \
  -F "file=@document.xlsx" \
  -F "table_format=html"
```

**Ответ:**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Document processing started (with force OCR)"
}
```

### 2. Проверка статуса обработки

```bash
GET /documents/{task_id}/status
```

**Пример запроса:**

```bash
curl "http://localhost:8000/documents/550e8400-e29b-41d4-a716-446655440000/status"
```

**Ответ:**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "message": "Task is completed",
  "error": null
}
```

**Статусы:**
- `pending` - задача в очереди
- `processing` - документ обрабатывается
- `completed` - обработка завершена
- `failed` - произошла ошибка

### 3. Скачивание результата

```bash
GET /documents/{task_id}/download
```

**Пример запроса:**

```bash
curl -O -J "http://localhost:8000/documents/550e8400-e29b-41d4-a716-446655440000/download"
```

Возвращает ZIP-архив со структурой:

```
task_id.zip
├── document.md          # Markdown файл с содержимым документа
└── images/              # Папка с изображениями (имена файлов - GUID)
    ├── a1b2c3d4-e5f6-7890-abcd-ef1234567890.png
    ├── b2c3d4e5-f6a7-8901-bcde-f12345678901.jpg
    └── ...
```

## Конфигурация

Создайте файл `.env` для настройки параметров:

```env
# Сервер
HOST=0.0.0.0
PORT=8000

# Хранилище
TEMP_STORAGE_PATH=/tmp/docling_storage
TTL_HOURS=24

# Загрузка файлов
MAX_FILE_SIZE_MB=50

# Обработка документов
ACCELERATOR_DEVICE=cpu  # cpu, cuda, или mps (Apple Metal)
NUM_THREADS=4           # Количество потоков для CPU
```

### Принудительный OCR для отдельных файлов

Если у вас есть отсканированные документы или документы, где стандартная обработка пропускает контент, используйте параметр `force_ocr=true` в запросе:

```bash
curl -X POST "http://localhost:8000/documents/process" \
  -F "file=@scanned_document.pdf" \
  -F "force_ocr=true"
```

**Когда использовать `force_ocr=true`:**
- ✅ Отсканированные документы (сканы бумаги)
- ✅ PDF с изображениями вместо текста
- ✅ Документы с плохо распознаваемым текстовым слоем
- ✅ Когда стандартная обработка пропускает изображения
- ✅ DOCX, PPTX, XLSX с встроенными изображениями

**Как работает для разных форматов:**
- **PDF** - Применяется полностраничный OCR (игнорирует текстовый слой)
- **DOCX, PPTX, XLSX** - Включается извлечение всех изображений на страницах
- **JPG, PNG** - Применяется OCR к изображениям

**Примечание:** Режим `force_ocr` медленнее стандартной обработки, так как применяет OCR ко всему документу.

### Гибридный экспорт таблиц

Сервер поддерживает три режима экспорта таблиц из документов:

#### `auto` (по умолчанию, рекомендуется)

Автоматически анализирует каждую таблицу и выбирает оптимальный формат:
- **Простые таблицы** → Markdown (удобночитаемый формат)
- **Сложные таблицы** → HTML (сохраняет структуру)

**Критерии сложности:**
- ✅ Таблицы с объединёнными ячейками (colspan/rowspan)
- ✅ Большие таблицы (>10 строк или >6 столбцов)

**Пример:**

```bash
curl -X POST "http://localhost:8000/documents/process" \
  -F "file=@document.xlsx" \
  -F "table_format=auto"
```

#### `markdown`

Все таблицы экспортируются в формате Markdown:
- ✅ Простой и читаемый формат
- ❌ Может потерять сложную структуру (объединённые ячейки)

**Когда использовать:**
- Документы с простыми таблицами
- Нужна максимальная читаемость в текстовом виде

#### `html`

Все таблицы экспортируются в формате HTML:
- ✅ Сохраняет полную структуру таблиц
- ✅ Поддерживает объединённые ячейки
- ✅ Идеально для сложных таблиц

**Когда использовать:**
- Документы со сложными таблицами
- Нужна точная передача структуры для RAG-систем

**Пример:**

```bash
curl -X POST "http://localhost:8000/documents/process" \
  -F "file=@complex_tables.docx" \
  -F "table_format=html"
```

**Совместимость:** HTML таблицы корректно отображаются в Markdown, так как большинство парсеров поддерживают встроенный HTML.

### Поддержка GPU

Сервер поддерживает аппаратное ускорение:

- **CPU** (по умолчанию) - работает везде, настраивается через `NUM_THREADS`
- **CUDA** - для NVIDIA GPU, требует установленный CUDA toolkit
- **MPS** - для Apple Silicon (M1/M2/M3), использует Metal Performance Shaders

#### Использование NVIDIA GPU

Раскомментируйте секцию `docling-ocr-server-gpu` в `docker-compose.yml` и установите `ACCELERATOR_DEVICE=cuda`:

```bash
# Убедитесь, что установлен nvidia-docker
docker-compose up docling-ocr-server-gpu
```

#### Использование Apple Metal (MPS)

Для Mac с Apple Silicon установите `ACCELERATOR_DEVICE=mps` в `.env`:

```env
ACCELERATOR_DEVICE=mps
NUM_THREADS=8
```

## Примеры использования

### Python

```python
import requests
import time

# Загрузка документа (стандартная обработка)
with open("document.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/documents/process",
        files={"file": f}
    )

task_id = response.json()["task_id"]
print(f"Task ID: {task_id}")

# Или с принудительным OCR для проблемных документов
# with open("scanned_document.pdf", "rb") as f:
#     response = requests.post(
#         "http://localhost:8000/documents/process",
#         files={"file": f},
#         data={"force_ocr": "true"}
#     )
#     task_id = response.json()["task_id"]

# Или с таблицами в HTML формате
# with open("complex_tables.xlsx", "rb") as f:
#     response = requests.post(
#         "http://localhost:8000/documents/process",
#         files={"file": f},
#         data={"table_format": "html"}
#     )
#     task_id = response.json()["task_id"]

# Проверка статуса
while True:
    status_response = requests.get(
        f"http://localhost:8000/documents/{task_id}/status"
    )
    status = status_response.json()["status"]
    print(f"Status: {status}")

    if status in ["completed", "failed"]:
        break

    time.sleep(2)

# Скачивание результата
if status == "completed":
    result = requests.get(
        f"http://localhost:8000/documents/{task_id}/download"
    )

    with open(f"{task_id}.zip", "wb") as f:
        f.write(result.content)

    print(f"Result saved to {task_id}.zip")
```

### cURL

```bash
#!/bin/bash

# Загрузка документа
RESPONSE=$(curl -s -X POST "http://localhost:8000/documents/process" \
  -F "file=@document.pdf")

TASK_ID=$(echo $RESPONSE | jq -r '.task_id')
echo "Task ID: $TASK_ID"

# Проверка статуса
while true; do
  STATUS=$(curl -s "http://localhost:8000/documents/$TASK_ID/status" | jq -r '.status')
  echo "Status: $STATUS"

  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi

  sleep 2
done

# Скачивание результата
if [ "$STATUS" = "completed" ]; then
  curl -O -J "http://localhost:8000/documents/$TASK_ID/download"
  echo "Result downloaded"
fi
```

## Версионирование

Проект использует семантическое версионирование (SemVer). Подробную информацию см. в [VERSIONING.md](VERSIONING.md).

### Использование опубликованного образа

```bash
# Использование конкретной версии (рекомендуется для продакшена)
docker pull ghcr.io/empire-tm/doclingocrserver:1.0.0

# Или использование latest
docker pull ghcr.io/empire-tm/doclingocrserver:latest

docker run -d \
  -p 8000:8000 \
  -v $(pwd)/temp_storage:/tmp/docling_storage \
  ghcr.io/empire-tm/doclingocrserver:1.0.0
```

### Создание новой версии

```bash
# Использование скрипта для обновления версии
./bump_version.sh 1.2.3

# Или вручную:
# 1. Обновите версию в version.py
# 2. Создайте тег: git tag v1.2.3
# 3. Отправьте тег: git push origin v1.2.3
```

GitHub Actions автоматически соберет и опубликует Docker образ с правильной версией.

## GitHub Actions

При пуше в `main` ветку или создании тега автоматически:
1. Собирается Docker образ с версией из тега или commit SHA
2. Публикуется в GitHub Container Registry с соответствующими тегами

## Архитектура

```
DoclingOCRServer/
├── main.py                      # FastAPI приложение и endpoints
├── config.py                    # Конфигурация через Pydantic Settings
├── models.py                    # Pydantic модели для API
├── services/
│   ├── document_processor.py   # Обработка документов через Docling
│   └── storage.py              # Управление хранилищем и TTL
├── requirements.txt             # Python зависимости
├── Dockerfile                   # Docker образ
├── docker-compose.yml           # Docker Compose конфигурация
└── .github/
    └── workflows/
        └── docker-publish.yml  # GitHub Actions workflow
```

## Технологии

- **FastAPI** - веб-фреймворк
- **Docling** - конвертация документов в Markdown
- **Tesseract OCR** - распознавание текста
- **Docker** - контейнеризация
- **GitHub Actions** - CI/CD

## Лицензия

MIT
