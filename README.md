# Docling OCR Server

FastAPI сервер для конвертации документов в Markdown с использованием Docling и Tesseract OCR.

## Возможности

- **Поддерживаемые форматы**: PDF, DOCX, DOC, XLSX, XLS, JPG, PNG
- **OCR**: Распознавание текста на русском и английском языках (Tesseract)
- **Таблицы и Layout**: Автоматическое распознавание таблиц и структуры документа
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

**Пример запроса:**

```bash
curl -X POST "http://localhost:8000/documents/process" \
  -F "file=@document.pdf"
```

**Ответ:**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Document processing started"
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
└── images/              # Папка с изображениями
    ├── image_1.png
    ├── image_2.jpg
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

# Загрузка документа
with open("document.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/documents/process",
        files={"file": f}
    )

task_id = response.json()["task_id"]
print(f"Task ID: {task_id}")

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

## GitHub Actions

При пуше в `main` ветку или создании тега автоматически:
1. Собирается Docker образ
2. Публикуется в GitHub Container Registry

### Использование опубликованного образа

```bash
docker pull ghcr.io/<your-username>/doclingocrserver:latest

docker run -d \
  -p 8000:8000 \
  -v $(pwd)/temp_storage:/tmp/docling_storage \
  ghcr.io/<your-username>/doclingocrserver:latest
```

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
